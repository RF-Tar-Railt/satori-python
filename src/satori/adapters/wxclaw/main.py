from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from launart import Launart
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response

from satori import EventType
from satori.exception import NetworkError
from satori.model import Event, Login, LoginStatus, User
from satori.reconnect import RECONNECT_STABLE_SECONDS, ReconnectPolicy
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter
from satori.utils import decode

from .api import apply
from .events import event_handlers, resolve_event_type
from .exception import HTTPStatusError, SessionExpiredError, WxClawActionFailed
from .login import (
    DEFAULT_BASE_URL,
    DEFAULT_BOT_TYPE,
    MAX_QR_REFRESH_COUNT,
    QrLoginSession,
    VerifyCodeCallback,
    WxClawLoginResult,
)
from .models import MessageType, QRCodeResponse, QRStatusResponse, WeixinMessage
from .network import WxClawNetwork
from .utils import build_get_headers, build_headers

WXCLAW_FEATURES = [
    "message.create",
    "channel.get",
    "login.get",
    "upload.create",
    "user.channel.create",
    "user.get",
]

QrRefreshCallback = Callable[[str, str], Awaitable[None]]


@dataclass
class WxClawConfig:
    account_id: str = ""
    """WxClaw 机器人的 iLink Bot ID；留空时仅启用二维码登录"""
    token: str = ""
    """WxClaw 机器人的访问令牌；留空时不会启动静态账号"""
    base_url: str = DEFAULT_BASE_URL
    """WxClaw API 基础地址"""
    ilink_app_id: str = "bot"
    """iLink App ID，默认为 bot"""
    channel_version: str = "2.4.1"
    """iLink 通道版本号，默认为 2.4.1"""
    long_poll_timeout: float = 35.0
    """长轮询请求的超时时间，单位为秒"""
    api_timeout: float = 15.0
    """普通 API 请求的超时时间，单位为秒"""
    cdn_base_url: str = "https://novac2c.cdn.weixin.qq.com/c2c"
    """微信 CDN 基础地址"""
    bot_agent: str = ""
    """Bot 标识；留空时使用 OpenClaw"""
    media_cache_size: int = 1024
    """接收媒体内部链接的最大缓存数量"""


class WxClawAdapter(BaseAdapter[WxClawConfig]):
    session: ClientSession | None

    def __init__(self, config: WxClawConfig):
        super().__init__()
        self.config = config
        self.session = None
        self.networks: dict[str, WxClawNetwork] = {}
        self.logins: dict[str, Login] = {}
        self._poll_tasks: dict[str, asyncio.Task[None]] = {}
        self._qr_login_task: asyncio.Task[None] | None = None
        apply(self, lambda self_id: self.networks[self_id], lambda self_id: self.logins[self_id])

    def get_platform(self) -> str:
        return "wxclaw"

    def ensure(self, platform: str, self_id: str) -> bool:
        return (
            platform == "wxclaw"
            and self_id in self.logins
            and self.logins[self_id].status not in (LoginStatus.OFFLINE, LoginStatus.DISCONNECT)
        )

    async def get_logins(self) -> list[Login]:
        logins = list(self.logins.values())
        for index, login in enumerate(logins):
            login.sn = index
        return logins

    @property
    def required(self) -> set[str]:
        return {"satori-python.server"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    def proxy_urls(self) -> list[str]:
        return []

    async def handle_internal(self, request: Request, path: str) -> Response:
        network = self.networks.get(request.self_id)
        if network is None:
            return Response("WxClaw login not found", status_code=404)
        if path.startswith("_api"):
            action = path[5:].lstrip("/")
            params = await request.origin.json()
            return JSONResponse(await network.call_internal(action, params))
        if path.startswith("media/"):
            resource, content = await network.read_cached_media(path.removeprefix("media/"))
            return Response(content, media_type=network.infer_content_type(resource))
        return Response("WxClaw internal resource not found", status_code=404)

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = ClientSession()
            if self.config.account_id and self.config.token:
                network = WxClawNetwork(
                    self,
                    self.session,
                    self.config.account_id,
                    self.config.token,
                    self.config.base_url,
                )
                self.networks[network.self_id] = network
            elif self.config.account_id or self.config.token:
                logger.warning("WxClaw account_id and token must both be configured; static login was skipped")

        async with self.stage("blocking"):
            for network in list(self.networks.values()):
                self._spawn_polling(network)
            if not self.config.account_id and not self.config.token:
                self._spawn_auto_qr_login()
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            await self._shutdown()

    def _spawn_auto_qr_login(self):
        if self._qr_login_task and not self._qr_login_task.done():
            return
        task = asyncio.create_task(self._auto_qr_login())
        self._qr_login_task = task

        def discard(done: asyncio.Task[None]):
            if self._qr_login_task is done:
                self._qr_login_task = None
            if not done.cancelled() and (error := done.exception()) is not None:
                logger.error(f"WxClaw automatic QR login failed: {error!r}")

        task.add_done_callback(discard)

    async def _auto_qr_login(self):
        async def on_refresh(_qrcode: str, qrcode_url: str):
            await self._publish_qr_code(qrcode_url, refreshed=True)

        qrcode, qrcode_url = await self.start_qr_login(base_url=self.config.base_url)
        if not qrcode:
            raise NetworkError("fetchQRCode: qrcode is missing")
        await self._publish_qr_code(qrcode_url)
        result = await self.wait_qr_login(
            qrcode=qrcode,
            base_url=self.config.base_url,
            on_refresh=on_refresh,
        )
        if not result.connected:
            logger.error(f"WxClaw automatic QR login did not connect: {result.message}")
            return
        self.connect_login_result(result, self.config.base_url)

    async def _publish_qr_code(self, qrcode_url: str, *, refreshed: bool = False):
        action = "refreshed" if refreshed else "created"
        logger.info(f"WxClaw QR code {action}: {qrcode_url}")

    def _spawn_polling(self, network: WxClawNetwork):
        current = self._poll_tasks.get(network.self_id)
        if current and not current.done():
            raise RuntimeError(f"WxClaw account {network.self_id} is already polling")
        task = asyncio.create_task(self._poll_account(network))
        self._poll_tasks[network.self_id] = task

        def discard(done: asyncio.Task[None]):
            if self._poll_tasks.get(network.self_id) is done:
                self._poll_tasks.pop(network.self_id, None)
            if not done.cancelled() and (error := done.exception()) is not None:
                logger.error(f"WxClaw polling task for {network.self_id} failed: {error!r}")

        task.add_done_callback(discard)

    async def _shutdown(self):
        qr_login_task = self._qr_login_task
        if qr_login_task:
            if not qr_login_task.done():
                qr_login_task.cancel()
            await asyncio.gather(qr_login_task, return_exceptions=True)
        self._qr_login_task = None

        tasks = list(self._poll_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._poll_tasks.clear()

        for network in self.networks.values():
            try:
                await network.notify_stop()
            except Exception as exc:
                logger.warning(f"WxClaw notifyStop failed for {network.self_id}: {exc}")
        for self_id in list(self.logins):
            await self._remove_login(self_id)
        self.networks.clear()

        if self.session:
            await self.session.close()
        self.session = None

    async def _mark_online(self, network: WxClawNetwork):
        login = self.logins.get(network.self_id)
        if login is None:
            login = Login(
                status=LoginStatus.ONLINE,
                adapter="wxclaw",
                platform="wxclaw",
                user=User(network.self_id, network.self_id, is_bot=True),
                features=WXCLAW_FEATURES.copy(),
            )
            self.logins[network.self_id] = login
            await self.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
        elif login.status != LoginStatus.ONLINE:
            login.status = LoginStatus.ONLINE
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def _mark_reconnecting(self, network: WxClawNetwork):
        login = self.logins.get(network.self_id)
        if login and login.status != LoginStatus.RECONNECT:
            login.status = LoginStatus.RECONNECT
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def _mark_offline(self, network: WxClawNetwork):
        login = self.logins.get(network.self_id)
        if login and login.status != LoginStatus.OFFLINE:
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def _remove_login(self, self_id: str):
        login = self.logins.pop(self_id, None)
        if login:
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))

    async def _poll_account(self, network: WxClawNetwork):
        try:
            await network.notify_start()
        except Exception as exc:
            logger.warning(f"WxClaw notifyStart failed for {network.self_id}: {exc}")

        policy = ReconnectPolicy()
        connected_since: float | None = None
        while True:
            try:
                response = await network.get_updates()
                await self._mark_online(network)
                now = asyncio.get_running_loop().time()
                if connected_since is None:
                    connected_since = now
                elif now - connected_since >= RECONNECT_STABLE_SECONDS:
                    policy.reset()
                if response.get_updates_buf is not None:
                    network.get_updates_buf = response.get_updates_buf
                for msg in response.msgs or []:
                    if msg.message_type != MessageType.USER:
                        continue
                    try:
                        await self.handle_event(network, msg)
                    except Exception as exc:
                        logger.exception(f"Failed to handle WxClaw message {msg.message_id!r}: {exc}")
            except asyncio.CancelledError:
                return
            except SessionExpiredError:
                logger.error(f"WxClaw session expired for {network.self_id}; QR login is required again")
                await self._remove_login(network.self_id)
                self.networks.pop(network.self_id, None)
                return
            except HTTPStatusError as exc:
                if exc.status_code in {401, 403}:
                    logger.error(f"WxClaw authorization failed for {network.self_id}: HTTP {exc.status_code}")
                    await self._remove_login(network.self_id)
                    self.networks.pop(network.self_id, None)
                    return
                logger.error(f"WxClaw polling HTTP error for {network.self_id}: {exc}")
                connected_since = None
                await self._mark_reconnecting(network)
                if not await policy.sleep():
                    logger.error(f"WxClaw reconnect attempts exhausted for {network.self_id}")
                    await self._mark_offline(network)
                    return
            except (NetworkError, WxClawActionFailed) as exc:
                logger.error(f"WxClaw polling error for {network.self_id}: {exc}")
                connected_since = None
                await self._mark_reconnecting(network)
                if not await policy.sleep():
                    logger.error(f"WxClaw reconnect attempts exhausted for {network.self_id}")
                    await self._mark_offline(network)
                    return
            except Exception as exc:
                logger.exception(f"Unexpected WxClaw polling error for {network.self_id}: {exc}")
                connected_since = None
                await self._mark_reconnecting(network)
                if not await policy.sleep():
                    logger.error(f"WxClaw reconnect attempts exhausted for {network.self_id}")
                    await self._mark_offline(network)
                    return

    async def handle_event(self, network: WxClawNetwork, msg: WeixinMessage):
        login = self.logins.get(network.self_id)
        if login is None:
            return
        event_type = resolve_event_type(msg)
        event = None
        if handler := event_handlers.get(event_type):
            try:
                event = await handler(login, network, msg)
            except Exception as exc:
                logger.exception(f"Failed to parse WxClaw event {event_type}: {exc!r}")
        if event is None:
            event = Event(EventType.INTERNAL, datetime.now(), login)
        event._type = event_type
        event._data = msg.dump()
        await self.server.post(event)

    def _require_session(self) -> ClientSession:
        if self.session is None:
            raise RuntimeError("WxClaw adapter must be running before QR login can be used")
        return self.session

    async def _fetch_qr_code(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        bot_type: str = DEFAULT_BOT_TYPE,
    ) -> QRCodeResponse:
        session = self._require_session()
        url = f"{base_url.rstrip('/')}/ilink/bot/get_bot_qrcode?bot_type={quote(bot_type)}"
        headers = build_headers(token="", app_id=self.config.ilink_app_id, channel_version=self.config.channel_version)
        local_tokens: list[str] = []
        for token in [*(network.token for network in self.networks.values()), self.config.token]:
            token = token.strip()
            if token and token not in local_tokens:
                local_tokens.append(token)
            if len(local_tokens) >= 10:
                break
        try:
            async with session.post(
                url,
                json={"local_token_list": local_tokens},
                headers=headers,
                timeout=ClientTimeout(total=self.config.api_timeout),
            ) as response:
                content = await response.read()
                if response.status != 200:
                    raise HTTPStatusError(response.status, "fetchQRCode")
        except asyncio.TimeoutError as exc:
            raise NetworkError("fetchQRCode: request timed out") from exc
        except aiohttp.ClientError as exc:
            raise NetworkError(f"fetchQRCode: {exc}") from exc
        data = decode(content or b"{}")
        if not isinstance(data, dict):
            raise NetworkError("fetchQRCode: expected a JSON object")
        return QRCodeResponse.parse(data)

    async def _poll_qr_status(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        qrcode: str,
        verify_code: str = "",
    ) -> QRStatusResponse:
        session = self._require_session()
        endpoint = f"ilink/bot/get_qrcode_status?qrcode={quote(qrcode)}"
        if verify_code:
            endpoint += f"&verify_code={quote(verify_code)}"
        url = f"{base_url.rstrip('/')}/{endpoint}"
        headers = build_get_headers(app_id=self.config.ilink_app_id, channel_version=self.config.channel_version)
        try:
            async with session.get(url, headers=headers, timeout=ClientTimeout(total=35)) as response:
                if response.status != 200:
                    return QRStatusResponse()
                data = decode(await response.read() or b"{}")
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return QRStatusResponse()
        return QRStatusResponse.parse(data) if isinstance(data, dict) else QRStatusResponse()

    async def start_qr_login(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        bot_type: str = DEFAULT_BOT_TYPE,
    ) -> tuple[str, str]:
        response = await self._fetch_qr_code(base_url=base_url, bot_type=bot_type)
        return response.qrcode, response.qrcode_img_content

    async def wait_qr_login(
        self,
        *,
        qrcode: str,
        base_url: str = DEFAULT_BASE_URL,
        bot_type: str = DEFAULT_BOT_TYPE,
        timeout: float = 480,
        on_refresh: QrRefreshCallback | None = None,
        verify_code_callback: VerifyCodeCallback | None = None,
    ) -> WxClawLoginResult:
        try:
            return await asyncio.wait_for(
                self._poll_qr_until_done(
                    qrcode=qrcode,
                    base_url=base_url,
                    bot_type=bot_type,
                    on_refresh=on_refresh,
                    verify_code_callback=verify_code_callback,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return WxClawLoginResult(message="Login timed out")

    async def _poll_qr_until_done(
        self,
        *,
        qrcode: str,
        base_url: str,
        bot_type: str,
        on_refresh: QrRefreshCallback | None,
        verify_code_callback: VerifyCodeCallback | None,
    ) -> WxClawLoginResult:
        current_base_url = base_url
        current_qrcode = qrcode
        qrcode_url = ""
        refresh_count = 0
        pending_verify_code = ""

        while True:
            response = await self._poll_qr_status(
                base_url=current_base_url,
                qrcode=current_qrcode,
                verify_code=pending_verify_code,
            )
            status = response.status
            if status == "wait":
                await asyncio.sleep(1)
                continue
            if status == "scaned":
                pending_verify_code = ""
                await asyncio.sleep(1)
                continue
            if status == "confirmed":
                if not response.ilink_bot_id:
                    return WxClawLoginResult(message="Login confirmed but ilink_bot_id is missing")
                return WxClawLoginResult(
                    connected=True,
                    account_id=response.ilink_bot_id,
                    token=response.bot_token or "",
                    base_url=response.baseurl or base_url,
                    user_id=response.ilink_user_id or "",
                    qrcode_url=qrcode_url,
                    message="Login successful",
                )
            if status == "expired":
                refresh_count += 1
                if refresh_count >= MAX_QR_REFRESH_COUNT:
                    return WxClawLoginResult(message="QR code expired too many times")
                pending_verify_code = ""
                current_base_url = base_url
                current_qrcode, qrcode_url = await self.start_qr_login(base_url=base_url, bot_type=bot_type)
                if on_refresh:
                    await on_refresh(current_qrcode, qrcode_url)
                continue
            if status == "scaned_but_redirect":
                if response.redirect_host:
                    current_base_url = f"https://{response.redirect_host}"
                await asyncio.sleep(1)
                continue
            if status == "need_verifycode":
                if verify_code_callback is None:
                    return WxClawLoginResult(
                        need_verify_code=True,
                        message="A pairing code is required, but verify_code_callback was not provided",
                    )
                code = (await verify_code_callback()).strip()
                if not code:
                    return WxClawLoginResult(
                        need_verify_code=True,
                        message="verify_code_callback returned an empty value",
                    )
                pending_verify_code = code
                continue
            if status == "verify_code_blocked":
                pending_verify_code = ""
                current_base_url = base_url
                refresh_count += 1
                if refresh_count >= MAX_QR_REFRESH_COUNT:
                    return WxClawLoginResult(message="Pairing code failed too many times")
                current_qrcode, qrcode_url = await self.start_qr_login(base_url=base_url, bot_type=bot_type)
                if on_refresh:
                    await on_refresh(current_qrcode, qrcode_url)
                continue
            if status == "binded_redirect":
                return WxClawLoginResult(message="This WeChat account is already bound to the instance")
            await asyncio.sleep(1)

    def qr_login(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        bot_type: str = DEFAULT_BOT_TYPE,
        timeout: float = 480,
        auto_connect: bool = False,
        verify_code_callback: VerifyCodeCallback | None = None,
    ) -> QrLoginSession:
        return QrLoginSession(
            _adapter=self,
            _base_url=base_url,
            _bot_type=bot_type,
            _timeout=timeout,
            _auto_connect=auto_connect,
            _verify_code_callback=verify_code_callback,
        )

    def connect_login_result(self, result: WxClawLoginResult, base_url: str = DEFAULT_BASE_URL):
        if not result.connected:
            raise ValueError("Cannot connect an unsuccessful WxClaw login result")
        if not result.account_id or not result.token:
            raise ValueError("WxClaw login result is missing account_id or token")
        session = self._require_session()
        if result.account_id in self.networks:
            raise ValueError(f"WxClaw account {result.account_id} is already configured")
        network = WxClawNetwork(
            self,
            session,
            result.account_id,
            result.token,
            result.base_url or base_url,
        )
        self.networks[network.self_id] = network
        self._spawn_polling(network)
        logger.warning(
            "WxClaw QR login succeeded. The token below is sensitive. Save these values in WxClawConfig "
            f"WxClawConfig(account_id={result.account_id!r}, token={result.token!r})"
        )

    def __str__(self):
        return self.id


__all__ = ["WxClawConfig", "WxClawAdapter"]
