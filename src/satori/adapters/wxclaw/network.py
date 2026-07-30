from __future__ import annotations

import asyncio
import mimetypes
from base64 import b64encode
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import md5
from os import urandom
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlparse

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from loguru import logger
from starlette.requests import Request as StarletteRequest

from satori.exception import NetworkError, NotFoundException
from satori.utils import decode

from .cdn import aes_ecb_decrypt, aes_ecb_encrypt, calculate_ciphertext_size, parse_aes_key
from .exception import HTTPStatusError, SessionExpiredError, WxClawActionFailed
from .models import (
    CDNMedia,
    FileItem,
    GetConfigResponse,
    GetUpdatesResponse,
    GetUploadUrlResponse,
    ImageItem,
    MessageItem,
    MessageItemType,
    MessageState,
    MessageType,
    TypingStatus,
    UploadMediaType,
    VideoItem,
    WeixinMessage,
)
from .utils import build_base_info, build_headers, decode_data_uri, generate_client_id, parse_file_uri

if TYPE_CHECKING:
    from .main import WxClawAdapter


@dataclass(slots=True)
class UploadResult:
    filekey: str
    download_encrypted_query_param: str
    aeskey: str
    aes_key_b64: str
    file_size: int
    file_size_ciphertext: int
    file_md5: str


@dataclass(slots=True)
class MediaResource:
    kind: MessageItemType
    media: CDNMedia
    item: MessageItem | None = None
    title: str | None = None
    content_type: str | None = None


class WxClawNetwork:
    def __init__(
        self,
        adapter: WxClawAdapter,
        session: ClientSession,
        account_id: str,
        token: str,
        base_url: str,
    ):
        self.adapter = adapter
        self.session = session
        self.self_id = account_id
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.get_updates_buf = ""
        self.context_tokens: dict[str, str] = {}
        self.session_ids: dict[str, str] = {}
        self.media_resources: OrderedDict[str, MediaResource] = OrderedDict()

    def update_context(self, user_id: str, context_token: str = "", session_id: str = ""):
        if context_token:
            self.context_tokens[user_id] = context_token
        if session_id:
            self.session_ids[user_id] = session_id

    def get_authorization_header(self) -> dict[str, str]:
        config = self.adapter.config
        return build_headers(
            token=self.token,
            app_id=config.ilink_app_id,
            channel_version=config.channel_version,
        )

    def get_api_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint}"

    def base_info(self) -> dict[str, str]:
        return build_base_info(self.adapter.config.channel_version, self.adapter.config.bot_agent)

    async def _request_json(
        self,
        endpoint: str,
        body: dict[str, Any],
        *,
        label: str,
        timeout: float,
        propagate_timeout: bool = False,
    ) -> dict[str, Any]:
        try:
            async with self.session.post(
                self.get_api_url(endpoint),
                json=body,
                headers=self.get_authorization_header(),
                timeout=ClientTimeout(total=timeout),
            ) as response:
                content = await response.read()
                status = response.status
        except asyncio.TimeoutError as exc:
            if propagate_timeout:
                raise
            raise NetworkError(f"{label}: request timed out") from exc
        except aiohttp.ClientError as exc:
            raise NetworkError(f"{label}: {exc}") from exc

        if status != 200:
            raise HTTPStatusError(status, label)
        if not content:
            return {}
        try:
            data = decode(content)
        except Exception as exc:
            raise NetworkError(f"{label}: invalid JSON response") from exc
        if not isinstance(data, dict):
            raise NetworkError(f"{label}: expected a JSON object")

        errcode = data.get("errcode")
        if errcode == -14:
            raise SessionExpiredError(ret=data.get("ret"), errcode=errcode, errmsg=data.get("errmsg"))
        ret = data.get("ret")
        if ret is not None and ret != 0:
            raise WxClawActionFailed(ret=ret, errcode=errcode, errmsg=data.get("errmsg"))
        return data

    async def get_updates(self) -> GetUpdatesResponse:
        body = {
            "get_updates_buf": self.get_updates_buf,
            "base_info": self.base_info(),
        }
        try:
            data = await self._request_json(
                "ilink/bot/getupdates",
                body,
                label="getUpdates",
                timeout=self.adapter.config.long_poll_timeout,
                propagate_timeout=True,
            )
        except asyncio.TimeoutError:
            return GetUpdatesResponse(ret=0, msgs=[], get_updates_buf=self.get_updates_buf)
        return GetUpdatesResponse.parse(data)

    async def send_message(self, msg: WeixinMessage) -> None:
        await self._request_json(
            "ilink/bot/sendmessage",
            {"msg": msg.dump(), "base_info": self.base_info()},
            label="sendMessage",
            timeout=self.adapter.config.api_timeout,
        )

    async def send_items(
        self,
        to_user_id: str,
        items: list[MessageItem],
        *,
        session_id: str = "",
        context_token: str = "",
    ) -> str:
        client_id = generate_client_id()
        msg = WeixinMessage(
            from_user_id="",
            to_user_id=to_user_id,
            client_id=client_id,
            session_id=session_id or self.session_ids.get(to_user_id) or to_user_id,
            message_type=MessageType.BOT,
            message_state=MessageState.FINISH,
            item_list=items,
            context_token=context_token or self.context_tokens.get(to_user_id, ""),
        )
        await self.send_message(msg)
        return client_id

    async def send_typing(
        self,
        to_user_id: str,
        *,
        typing_ticket: str = "",
        status: int = TypingStatus.TYPING,
    ) -> None:
        await self._request_json(
            "ilink/bot/sendtyping",
            {
                "ilink_user_id": to_user_id,
                "typing_ticket": typing_ticket,
                "status": int(status),
                "base_info": self.base_info(),
            },
            label="sendTyping",
            timeout=self.adapter.config.api_timeout,
        )

    async def get_config(self, user_id: str, *, context_token: str = "") -> GetConfigResponse:
        data = await self._request_json(
            "ilink/bot/getconfig",
            {
                "ilink_user_id": user_id,
                "context_token": context_token or self.context_tokens.get(user_id, ""),
                "base_info": self.base_info(),
            },
            label="getConfig",
            timeout=self.adapter.config.api_timeout,
        )
        return GetConfigResponse.parse(data)

    async def notify_start(self) -> None:
        await self._request_json(
            "ilink/bot/msg/notifystart",
            {"base_info": self.base_info()},
            label="notifyStart",
            timeout=self.adapter.config.api_timeout,
        )

    async def notify_stop(self) -> None:
        await self._request_json(
            "ilink/bot/msg/notifystop",
            {"base_info": self.base_info()},
            label="notifyStop",
            timeout=self.adapter.config.api_timeout,
        )

    async def get_upload_url(self, **params: Any) -> GetUploadUrlResponse:
        data = await self._request_json(
            "ilink/bot/getuploadurl",
            {**params, "base_info": self.base_info()},
            label="getUploadUrl",
            timeout=self.adapter.config.api_timeout,
        )
        return GetUploadUrlResponse.parse(data)

    async def upload_to_cdn(
        self,
        upload_url: str,
        encrypted_data: bytes,
        *,
        label: str = "cdnUpload",
        max_retries: int = 3,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                async with self.session.post(
                    upload_url,
                    data=encrypted_data,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=ClientTimeout(total=120),
                ) as response:
                    await response.read()
                    if 400 <= response.status < 500:
                        raise NetworkError(f"{label}: CDN client error {response.status}")
                    if response.status != 200:
                        raise NetworkError(f"{label}: CDN server error {response.status}")
                    download_param = response.headers.get("x-encrypted-param", "")
                    if not download_param:
                        raise NetworkError(f"{label}: CDN response missing x-encrypted-param")
                    return download_param
            except NetworkError as exc:
                if "client error" in str(exc):
                    raise
                last_error = exc
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = NetworkError(f"{label}: {exc}")

            if attempt < max_retries:
                logger.warning(f"{label}: attempt {attempt} failed, retrying")

        raise last_error or NetworkError(f"{label}: upload failed after {max_retries} attempts")

    async def prepare_and_upload_file(
        self,
        file_data: bytes,
        media_type: UploadMediaType,
        to_user_id: str,
    ) -> UploadResult:
        raw_size = len(file_data)
        raw_md5 = md5(file_data).hexdigest()
        ciphertext_size = calculate_ciphertext_size(raw_size)
        filekey = urandom(16).hex()
        aeskey = urandom(16)

        upload = await self.get_upload_url(
            filekey=filekey,
            media_type=int(media_type),
            to_user_id=to_user_id,
            rawsize=raw_size,
            rawfilemd5=raw_md5,
            filesize=ciphertext_size,
            no_need_thumb=True,
            aeskey=aeskey.hex(),
        )
        upload_url = (upload.upload_full_url or "").strip()
        if not upload_url and upload.upload_param:
            upload_url = (
                f"{self.adapter.config.cdn_base_url}/upload?"
                f"encrypted_query_param={quote(upload.upload_param, safe='')}&filekey={quote(filekey, safe='')}"
            )
        if not upload_url:
            raise NetworkError("getUploadUrl returned no upload URL")

        download_param = await self.upload_to_cdn(
            upload_url,
            aes_ecb_encrypt(file_data, aeskey),
            label=f"cdnUpload[{filekey}]",
        )
        aeskey_hex = aeskey.hex()
        return UploadResult(
            filekey=filekey,
            download_encrypted_query_param=download_param,
            aeskey=aeskey_hex,
            aes_key_b64=b64encode(aeskey_hex.encode("ascii")).decode("ascii"),
            file_size=raw_size,
            file_size_ciphertext=ciphertext_size,
            file_md5=raw_md5,
        )

    def build_cdn_download_url(self, media: CDNMedia) -> str:
        if media.full_url:
            return media.full_url
        return (
            f"{self.adapter.config.cdn_base_url}/download?"
            f"encrypted_query_param={quote(media.encrypt_query_param or '', safe='')}"
        )

    async def download_media(self, media: CDNMedia) -> bytes:
        if not media.aes_key:
            raise ValueError("WxClaw media is missing aes_key")
        url = self.build_cdn_download_url(media)
        try:
            async with self.session.get(url, timeout=ClientTimeout(total=60)) as response:
                content = await response.read()
                if response.status != 200:
                    raise NetworkError(f"cdnDownload: HTTP {response.status}")
        except asyncio.TimeoutError as exc:
            raise NetworkError("cdnDownload: request timed out") from exc
        except aiohttp.ClientError as exc:
            raise NetworkError(f"cdnDownload: {exc}") from exc
        return aes_ecb_decrypt(content, parse_aes_key(media.aes_key))

    def cache_media(self, resource: MediaResource) -> str:
        token = token_urlsafe(18)
        self.media_resources[token] = resource
        self.media_resources.move_to_end(token)
        while len(self.media_resources) > self.adapter.config.media_cache_size:
            self.media_resources.popitem(last=False)
        return f"internal:wxclaw/{self.self_id}/media/{token}"

    def get_cached_media(self, src: str) -> MediaResource | None:
        prefix = f"internal:wxclaw/{self.self_id}/media/"
        if not src.startswith(prefix):
            return None
        token = src.removeprefix(prefix)
        resource = self.media_resources.get(token)
        if resource is not None:
            self.media_resources.move_to_end(token)
        return resource

    async def read_cached_media(self, token: str) -> tuple[MediaResource, bytes]:
        resource = self.media_resources.get(token)
        if resource is None:
            raise FileNotFoundError(f"WxClaw media resource {token!r} not found")
        self.media_resources.move_to_end(token)
        return resource, await self.download_media(resource.media)

    async def _read_proxy_resource(self, src: str) -> bytes:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 80),
        }
        response = await self.adapter.server.fetch_proxy(src, StarletteRequest(scope))
        body = getattr(response, "body", None)
        if body is not None:
            return bytes(body)
        path = getattr(response, "path", None)
        if path is not None:
            return Path(path).read_bytes()
        raise NetworkError(f"Cannot read proxied resource {src!r}")

    async def read_resource(self, src: str, *, timeout_ms: int | None = None) -> bytes:
        if src.startswith("data:"):
            return decode_data_uri(src)[1]
        if src.startswith("file:"):
            return parse_file_uri(src).read_bytes()
        if src.startswith("internal:"):
            cached = self.get_cached_media(src)
            if cached is not None:
                return await self.download_media(cached.media)
            if content := self.adapter.server.get_local_file(src):
                return content
            return await self._read_proxy_resource(src)

        parsed = urlparse(src)
        if parsed.scheme in {"http", "https"}:
            should_proxy = any(
                src.startswith(prefix) for provider in self.adapter.server.providers for prefix in provider.proxy_urls()
            )
            if should_proxy:
                return await self._read_proxy_resource(src)
            timeout = (timeout_ms / 1000) if timeout_ms is not None else 60
            try:
                async with self.session.get(src, timeout=ClientTimeout(total=timeout)) as response:
                    content = await response.read()
                    if response.status != 200:
                        raise NetworkError(f"Resource download HTTP {response.status}: {src}")
                    return content
            except asyncio.TimeoutError as exc:
                raise NetworkError(f"Resource download timed out: {src}") from exc
            except aiohttp.ClientError as exc:
                raise NetworkError(f"Resource download failed: {src}: {exc}") from exc

        path = Path(src)
        if path.exists():
            return path.read_bytes()
        raise ValueError(f"Unsupported resource URL: {src}")

    async def call_internal(self, action: str, params: dict[str, Any]) -> Any:
        if action == "send_typing":
            await self.send_typing(**params)
            return None
        if action == "get_config":
            return (await self.get_config(**params)).dump()
        if action == "get_upload_url":
            return (await self.get_upload_url(**params)).dump()
        if action == "send_message":
            raw = params.get("msg")
            if not isinstance(raw, dict):
                raise TypeError("send_message requires a msg object")
            await self.send_message(WeixinMessage.parse(raw))
            return None
        if action == "notify_start":
            await self.notify_start()
            return None
        if action == "notify_stop":
            await self.notify_stop()
            return None
        raise NotFoundException(f"Unknown WxClaw internal action: {action}")

    @staticmethod
    def infer_content_type(resource: MediaResource) -> str:
        if resource.content_type:
            return resource.content_type
        if resource.title:
            guessed = mimetypes.guess_type(resource.title)[0]
            if guessed:
                return guessed
        return "application/octet-stream"

    def build_uploaded_item(
        self,
        kind: MessageItemType,
        result: UploadResult,
        *,
        title: str | None = None,
    ) -> MessageItem:
        media = CDNMedia(
            encrypt_query_param=result.download_encrypted_query_param,
            aes_key=result.aes_key_b64,
            encrypt_type=1,
        )
        if kind == MessageItemType.IMAGE:
            return MessageItem(
                type=kind,
                image_item=ImageItem(media=media, mid_size=result.file_size_ciphertext),
            )
        if kind == MessageItemType.FILE:
            return MessageItem(
                type=kind,
                file_item=FileItem(
                    media=media,
                    file_name=title or "file",
                    md5=result.file_md5,
                    len=str(result.file_size),
                ),
            )
        if kind == MessageItemType.VIDEO:
            return MessageItem(
                type=kind,
                video_item=VideoItem(media=media, video_size=result.file_size_ciphertext),
            )
        raise ValueError(f"Unsupported WxClaw upload kind: {kind}")
