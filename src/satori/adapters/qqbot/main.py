from __future__ import annotations

import binascii
import os
import ssl
from datetime import datetime, timezone, timedelta
from typing import cast

import aiohttp
from aiohttp import FormData
from launart import Launart
from launart.status import Phase
from loguru import logger
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from yarl import URL

from satori import EventType
from satori.exception import NetworkError
from satori.model import Event, Login, LoginStatus
from satori.server.adapter import Adapter as BaseAdapter
from satori.server.model import Request
from satori.utils import decode

# from .api import apply
from .events import event_handlers
from .exception import UnauthorizedException
from .utils import CallMethod, validate_response, Payload, Opcode, decode_user
from .audit_store import audit_result

DEFAULT_FEATURES = ["reaction"]


class _QQNetwork:

    _access_token: str | None
    _expires_in: datetime | None

    def __init__(
        self,
        adapter: QQBotWebhookAdapter,
        session: aiohttp.ClientSession,
        app_id: str,
        secret: str,
    ):
        self.adapter = adapter
        self.session = session
        self.app_id = app_id
        self.secret = secret
        self._access_token = None
        self._expires_in = None

    async def _call_http(
        self, method: CallMethod, action: str, headers: dict[str, str] | None = None, params: dict | None = None
    ) -> dict:
        params = params or {}
        params = {k: v for k, v in params.items() if v is not None}
        if method in {"get", "fetch"}:
            async with self.session.get(
                (self.adapter.api_base / action).with_query(params),
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "patch":
            async with self.session.patch(
                (self.adapter.api_base / action),
                json=params,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "put":
            async with self.session.put(
                (self.adapter.api_base / action),
                json=params,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "delete":
            async with self.session.delete(
                (self.adapter.api_base / action).with_query(params),
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method in {"post", "update"}:
            async with self.session.post(
                (self.adapter.api_base / action),
                json=params,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "multipart":
            if params is None:
                raise TypeError("multipart requires params")
            data = FormData(params["data"], quote_fields=False)
            for k, v in params["files"].items():
                if isinstance(v, dict):
                    data.add_field(k, v["value"], filename=v.get("filename"), content_type=v.get("content_type"))
                else:
                    data.add_field(k, v)

            async with self.session.post(
                (self.adapter.api_base / action),
                data=data,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        raise ValueError(f"unknown method {method}")

    async def call_api(self, method: CallMethod, action: str, params: dict | None = None) -> dict:
        headers = await self.get_authorization_header()
        try:
            return await self._call_http(method, action, headers, params)
        except UnauthorizedException as e:
            self._access_token = None
            try:
                headers = await self.get_authorization_header()
            except Exception:
                raise e from None
            try:
                return await self._call_http(method, action, headers, params)
            except Exception as e1:
                raise e1 from None

    async def get_access_token(self) -> str:
        if self._access_token is None or (
            self._expires_in and datetime.now(timezone.utc) > self._expires_in - timedelta(seconds=30)
        ):
            async with self.session.post(
                self.adapter.auth_base,
                json={
                    "appId": self.app_id,
                    "clientSecret": self.secret,
                },
            ) as resp:
                if resp.status != 200 or not resp.content:
                    raise NetworkError(
                        f"Get authorization failed with status code {resp.status}." " Please check your config."
                    )
                data = await resp.json()
            self._access_token = cast(str, data["access_token"])
            self._expires_in = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
        return self._access_token

    async def _get_authorization_header(self) -> str:
        """获取当前 Bot 的鉴权信息"""
        # if self.config.is_group_bot:
        return f"QQBot {await self.get_access_token()}"
        # return f"Bot {self.config.id}.{self.config.token}"

    async def get_authorization_header(self) -> dict[str, str]:
        """获取当前 Bot 的鉴权信息"""
        return {"Authorization": await self._get_authorization_header()}


class QQBotWebhookAdapter(BaseAdapter):

    session: aiohttp.ClientSession | None

    def __init__(
        self,
        secrets: dict[str, str],  # app_id 对应的 secret
        *,
        path: str = "/qqbot",
        certfile: str | os.PathLike[str] | None = None,
        keyfile: str | os.PathLike[str] | None = None,
        verify_payload: bool = True,
        is_sandbox: bool = False,
        api_base: str | URL = URL("https://api.sgroup.qq.com/"),
        sandbox_api_base: str | URL = URL("https://sandbox.api.sgroup.qq.com"),
        auth_base: str | URL = URL("https://bots.qq.com/app/getAppAccessToken"),
    ):
        super().__init__()
        self.api_base = URL(str(api_base if not is_sandbox else sandbox_api_base))
        self.auth_base = URL(str(auth_base))
        self.ssl_context = None
        if certfile and keyfile:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile, keyfile)
        else:
            logger.warning("SSL is not enabled. You may need to use a reverse proxy to apply SSL.")
            self.ssl_context = None
        self.verify_payload = verify_payload
        self.secrets = secrets
        self.path = path
        self.session = None
        self.logins: list[Login] = []
        self.bot_id_mapping: dict[str, str] = {}  # login.id -> bot app_id
        self.networks: dict[str, _QQNetwork] = {}
        self.features = list(DEFAULT_FEATURES)
        # apply(self, self._get_network, self._get_login)

    def get_platform(self) -> str:
        return "qq"

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform in ("qq", "qqguild") and any(lg.id == self_id for lg in self.logins)

    async def get_logins(self) -> list[Login]:
        for index, login in enumerate(self.logins):
            login.sn = index
        return self.logins

    @property
    def required(self) -> set[str]:
        return {"satori-python.server"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            if self.session:
                await self.session.close()
            self.session = None
            await self._handle_disconnect()

    def proxy_urls(self) -> list[str]:
        return []

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            data = await request.origin.json()
            self_id = request.self_id
            action = path[5:]
            method: CallMethod = request.origin.method  # type: ignore
            net = self._get_network(self.bot_id_mapping[self_id])
            return JSONResponse(await net.call_api(method, action, data))
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        return Response(status_code=404, content="Not Found")

    def get_routes(self) -> list[Route]:
        return [Route(path, self.webhook_endpoint, methods=["POST"]) for path in self._normalize_webhook_paths(self.path)]

    async def handle_event(self, app_id: str, payload: Payload):
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        event_type = payload.type
        if not event_type:
            return
        network = self.networks.get(app_id)
        if not network:
            network = _QQNetwork(self, self.session, app_id, self.secrets[app_id])
            self.networks[app_id] = network
        login, guild_login = await self.refresh_login(app_id)
        if event_type.startswith("MESSAGE_AUDIT_"):
            audit_result.add_result(payload.data)
        handler = event_handlers.get(event_type)

        if handler:
            event = await handler(login, guild_login, network, payload)
        else:
            event = Event(
                EventType.INTERNAL,
                datetime.now(),
                login,
            )
        if event:
            event._type = event_type
            event._data = payload.data
            await self.server.post(event)

    async def refresh_login(self, app_id: str):
        network = self.networks[app_id]
        bot_info = await network.call_api("get", "users/@me")
        user = decode_user(bot_info)
        user.is_bot = True
        login = Login(0, LoginStatus.ONLINE, "qqbot", platform="qq", user=user, features=self.features.copy())
        previous = next((lg for lg in self.logins if lg.id == login.id and lg.platform == "qq"), None)
        if previous:
            previous.user = login.user
            previous.status = LoginStatus.ONLINE
            login = previous
            event_type = EventType.LOGIN_UPDATED
        else:
            self.logins.append(login)
            self.bot_id_mapping[login.id] = app_id
            event_type = EventType.LOGIN_ADDED
        await self.server.post(Event(event_type, datetime.now(), login))
        guild_login = Login(0, LoginStatus.ONLINE, "qqbot", platform="qqguild", user=user, features=self.features.copy())
        previous = next((lg for lg in self.logins if lg.id == guild_login.id and lg.platform == "qqguild"), None)
        if previous:
            previous.user = guild_login.user
            previous.status = LoginStatus.ONLINE
            guild_login = previous
            event_type = EventType.LOGIN_UPDATED
        else:
            self.logins.append(guild_login)
            self.bot_id_mapping[guild_login.id] = app_id
            event_type = EventType.LOGIN_ADDED
        await self.server.post(Event(event_type, datetime.now(), guild_login))
        return login, guild_login

    async def _handle_disconnect(self):
        for login in self.logins:
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
            self.networks.pop(self.bot_id_mapping[login.id], None)
        self.logins.clear()

    def _normalize_webhook_paths(self, webhook_path: str) -> tuple[str, ...]:
        path = webhook_path or "/"
        normalized = path if path.startswith("/") else f"/{path}"
        paths: set[str] = {normalized}
        stripped = normalized.rstrip("/")
        if stripped and stripped != normalized:
            paths.add(stripped)
        return tuple(sorted(paths))

    def _get_network(self, app_id: str) -> _QQNetwork:
        network = self.networks.get(app_id)
        if not network:
            network = _QQNetwork(self, self.session, app_id, self.secrets[app_id])  # type: ignore
            self.networks[app_id] = network
        return network

    async def webhook_endpoint(self, request: StarletteRequest) -> Response:
        header = request.headers
        data = decode(await request.body())
        payload = Payload(**data)
        app_id = str(header["X-Bot-Appid"])
        if app_id not in self.secrets:
            logger.error(f"Unauthorized bot id: {app_id}")
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        secret = self.secrets[app_id]
        if payload.opcode == Opcode.SERVER_VERIFY:
            logger.info("QQBot Verifying current server...")
            plain_token = payload.data["plain_token"]
            event_ts = payload.data["event_ts"]
            seed = secret.encode()
            while len(seed) < 32:
                seed += secret.encode()
            seed = seed[:32]
            try:
                private_key = Ed25519PrivateKey.from_private_bytes(seed)
            except Exception as e:
                logger.exception(f"Failed to generate ed25519 private key: {e}")
                return Response(status_code=500, content=f"Failed to generate ed25519 private key: {e}")
            msg = f"{event_ts}{plain_token}".encode()
            try:
                signature = private_key.sign(msg)
                signature_hex = binascii.hexlify(signature).decode()
            except Exception as e:
                logger.exception(f"Failed to sign message: {e}")
                return Response(status_code=500, content=f"Failed to sign message: {e}")
            return JSONResponse({"plain_token": plain_token, "signature": signature_hex})

        if self.verify_payload:
            ed25519 = header["X-Signature-Ed25519"]
            timestamp = header["X-Signature-Timestamp"]

            seed = secret.encode()
            while len(seed) < 32:
                seed *= 2
            seed = seed[:32]
            try:
                private_key = Ed25519PrivateKey.from_private_bytes(seed)
                public_key = private_key.public_key()
            except Exception as e:
                logger.exception(f"Failed to generate ed25519 public key: {e}")
                return Response(status_code=500, content=f"Failed to generate ed25519 public key: {e}")
            if not ed25519:
                logger.warning(f"Missing ed25519 signature")
                return Response(status_code=401, content="Missing ed25519 signature")
            sig = binascii.unhexlify(ed25519)
            if len(sig) != 64 or sig[63] & 224 != 0:
                logger.warning(f"Invalid ed25519 signature")
                return Response(status_code=401, content="Invalid ed25519 signature")
            if not timestamp:
                logger.warning(f"Missing timestamp")
                return Response(status_code=401, content="Missing timestamp")
            msg = timestamp.encode() + await request.body()
            try:
                public_key.verify(sig, msg)
            except InvalidSignature:
                logger.warning(f"Invalid payload: {payload}")
                return Response(status_code=401, content="Invalid payload")
            except Exception as e:
                logger.exception(f"Failed to verify ed25519 signature: {e}")
                return Response(status_code=401, content=f"Failed to verify ed25519 signature: {e}")

        await self.handle_event(app_id, payload)
        return Response(status_code=200)


__all__ = ["QQBotWebhookAdapter"]
