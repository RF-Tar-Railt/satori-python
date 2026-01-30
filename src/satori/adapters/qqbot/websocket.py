from __future__ import annotations

import asyncio
import sys
from contextlib import suppress
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import cast

import aiohttp
from aiohttp import FormData
from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
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


QQ_FEATURES = ['message.create', 'message.delete', 'upload.create', 'login.get', 'user.channel.create']
QQ_GUILD_FEATURES = ['channel.get', 'channel.list', 'channel.create', 'message.create', 'message.delete', 'message.get', 'reaction.create', 'reaction.delete', 'reaction.list', 'upload.create', 'guild.get', 'guild.list', 'guild.member.get', 'guild.member.list', 'guild.member.kick', 'guild.member.mute', 'login.get', 'user.get', 'user.channel.create']


@dataclass
class Intents:
    guilds: bool = True
    guild_members: bool = True
    guild_messages: bool = False
    """GUILD_MESSAGES"""
    guild_message_reactions: bool = True
    direct_message: bool = False
    """DIRECT_MESSAGES"""
    open_forum_event: bool = False
    audio_live_member: bool = False
    c2c_group_at_messages: bool = False
    interaction: bool = False
    message_audit: bool = True
    forum_event: bool = False
    audio_action: bool = False
    at_messages: bool = True
    """PUBLIC_GUILD_MESSAGES"""

    def __post_init__(self):
        if self.at_messages and self.guild_messages:
            logger.warning("at_messages and guild_messages are both enabled, which is not recommended.")

    def to_int(self) -> int:
        return (
            self.guilds << 0
            | self.guild_members << 1
            | self.guild_messages << 9
            | self.guild_message_reactions << 10
            | self.direct_message << 12
            | self.open_forum_event << 18
            | self.audio_live_member << 19
            | self.c2c_group_at_messages << 25
            | self.interaction << 26
            | self.message_audit << 27
            | self.forum_event << 28
            | self.audio_action << 29
            | self.at_messages << 30
        )

    @property
    def is_group_enabled(self) -> bool:
        """是否开启群聊功能"""
        return self.c2c_group_at_messages is True


class QQBotWebsocketAdapter(BaseAdapter):

    connections: dict[tuple[int, int], aiohttp.ClientWebSocketResponse]
    response_waiters: dict[str, asyncio.Future]
    session: aiohttp.ClientSession | None
    sequence: int | None
    session_id: str | None
    _access_token: str | None
    _expires_in: datetime | None

    def __init__(
        self,
        app_id: str,
        token: str,
        secret: str,
        shard: tuple[int, int] | None = None,
        intent: Intents = Intents(),
        *,
        is_sandbox: bool = False,
        api_base: str | URL = URL("https://api.sgroup.qq.com/"),
        sandbox_api_base: str | URL = URL("https://sandbox.api.sgroup.qq.com"),
        auth_base: str | URL = URL("https://bots.qq.com/app/getAppAccessToken"),
    ):
        super().__init__()
        self.app_id = app_id
        self.token = token
        self.secret = secret
        self.shard = shard
        self.intent = intent
        self.api_base = URL(str(api_base if not is_sandbox else sandbox_api_base))
        self.auth_base = URL(str(auth_base))
        self.session = None
        self.logins: list[Login] = []
        self.bot_id_mapping: dict[str, str] = {}  # login.id -> bot app_id
        self.close_signal = asyncio.Event()
        self.connections = {}
        self.response_waiters = {}
        self.sequence = None
        self.session_id = None
        self._access_token = None
        self._expires_in = None
        # apply(self, self._get_network, self._get_login)

    def get_platform(self) -> str:
        return "qq"

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform in ("qq", "qqguild") and any(lg.id == self_id for lg in self.logins)

    async def get_logins(self) -> list[Login]:
        for index, lg in enumerate(self.logins):
            lg.sn = index
        return self.logins

    @property
    def required(self) -> set[str]:
        return {"satori-python.server"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    def proxy_urls(self) -> list[str]:
        return []

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            data = await request.origin.json()
            action = path[5:]
            method: CallMethod = request.origin.method  # type: ignore
            return JSONResponse(await self.call_api(method, action, data))
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        return Response(status_code=404, content="Not Found")

    async def send(self, payload: dict, shard: tuple[int, int]):
        if (connection := self.connections.get(shard)) is None:
            raise RuntimeError("connection is not established")

        await connection.send_json(payload)

    async def message_receive(self, shard: tuple[int, int]):
        if (connection := self.connections.get(shard)) is None:
            raise RuntimeError("connection is not established")

        async for msg in connection:
            # logger.debug(f"{msg=}")

            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = decode(cast(str, msg.data))
                if data["op"] == Opcode.RECONNECT:
                    logger.warning("Received reconnect event from server, will reconnect in 5 seconds...")
                    break
                if data["op"] == Opcode.INVALID_SESSION:
                    self.session_id = None
                    self.sequence = None
                    logger.warning("Received invalid session event from server, will try to resume")
                    break
                if data["op"] == Opcode.HEARTBEAT_ACK:
                    continue
                yield self, data
        else:
            await self.connection_closed()

    async def message_handle(self, shard: tuple[int, int]):
        async for connection, data in self.message_receive(shard):
            if data["op"] != Opcode.DISPATCH:
                logger.debug(f"received other payload: {data}")
                continue
            payload = Payload(**data)
            connection.sequence = payload.sequence  # type: ignore

            async def event_parse_task(_data: Payload):
                event_type = _data.type
                if not event_type:
                    return
                login, guild_login = self.logins[:2]
                if event_type.startswith("MESSAGE_AUDIT_"):
                    audit_result.add_result(_data.data)
                handler = event_handlers.get(event_type)
                if handler:
                    event = await handler(login, guild_login, self, _data)
                else:
                    event = Event(
                        EventType.INTERNAL,
                        datetime.now(),
                        guild_login,
                    )
                if event:
                    event._type = event_type
                    event._data = _data.data
                    await self.server.post(event)

            asyncio.create_task(event_parse_task(payload))

    async def connection_closed(self):
        self.session_id = None
        self.sequence = None
        self.close_signal.set()

    async def _heartbeat(self, heartbeat_interval: int, shard: tuple[int, int]):
        """心跳"""
        while True:
            if self.session_id:
                with suppress(Exception):
                    await self.send({"op": 1, "d": self.sequence}, shard=shard)
            await asyncio.sleep(heartbeat_interval / 1000)

    async def _hello(self, shard: tuple[int, int]) -> int | None:
        """接收并处理服务器的 Hello 事件"""
        if not (connection := self.connections.get(shard)):
            raise RuntimeError("connection is not established")
        try:
            payload = Payload(**await connection.receive_json())
            assert payload.opcode == Opcode.HELLO, f"Received unexpected payload: {payload!r}"
            return payload.data["heartbeat_interval"]
        except Exception as e:
            logger.error(
                "Error while receiving server hello event",
                e,
            )

    async def _authenticate(self, shard: tuple[int, int]):
        """鉴权连接"""
        if not (connection := self.connections.get(shard)):
            raise RuntimeError("connection is not established")
        if not self.session_id:
            payload = Payload(
                op=Opcode.IDENTIFY,
                d={
                    "token": await self._get_authorization_header(),
                    "intents": self.intent.to_int(),
                    "shard": list(shard),
                    "properties": {
                        "$os": sys.platform,
                        "$language": f"python {sys.version}",
                        "$sdk": "Satori Python",
                    },
                },
            )
        else:
            payload = Payload(
                op=Opcode.RESUME,
                d={
                    "token": await self._get_authorization_header(),
                    "session_id": self.session_id,
                    "seq": self.sequence,
                },
            )

        try:
            await self.send(asdict(payload), shard)
        except Exception as e:
            logger.error(f"Error while sending {payload.opcode.name.title()} event: {e}")
            return False

        if not self.session_id:
            # https://bot.q.qq.com/wiki/develop/api/gateway/reference.html#_2-%E9%89%B4%E6%9D%83%E8%BF%9E%E6%8E%A5
            # 鉴权成功之后，后台会下发一个 Ready Event
            payload = Payload(**await connection.receive_json())
            if payload.opcode == Opcode.INVALID_SESSION:
                logger.warning("Received invalid session event from server, will try to resume")
                return False
            if not (payload.opcode == Opcode.DISPATCH and payload.type == "READY" and payload.data):
                logger.error(f"Received unexpected payload: {payload}")
                return False
            self.sequence = payload.sequence
            self.session_id = payload.data["session_id"]
            profile = payload.data["user"]
        else:
            profile = await self.call_api("get", "users/@me")
        await self.refresh_login(profile)
        return True

    async def refresh_login(self, profile: dict):
        user = decode_user(profile)
        user.is_bot = True
        login = Login(0, LoginStatus.ONLINE, "qqbot", platform="qq", user=user, features=QQ_FEATURES.copy())
        previous = next((lg for lg in self.logins if lg.id == login.id and lg.platform == "qq"), None)
        if previous:
            previous.user = login.user
            previous.status = LoginStatus.ONLINE
            login = previous
            event_type = EventType.LOGIN_UPDATED
        else:
            self.logins.append(login)
            self.bot_id_mapping[login.id] = self.app_id
            event_type = EventType.LOGIN_ADDED
        await self.server.post(Event(event_type, datetime.now(), login))
        guild_login = Login(0, LoginStatus.ONLINE, "qqbot", platform="qqguild", user=user, features=QQ_GUILD_FEATURES.copy())
        previous = next((lg for lg in self.logins if lg.id == guild_login.id and lg.platform == "qqguild"), None)
        if previous:
            previous.user = guild_login.user
            previous.status = LoginStatus.ONLINE
            guild_login = previous
            event_type = EventType.LOGIN_UPDATED
        else:
            self.logins.append(guild_login)
            self.bot_id_mapping[guild_login.id] = self.app_id
            event_type = EventType.LOGIN_ADDED
        await self.server.post(Event(event_type, datetime.now(), guild_login))
        return login, guild_login

    async def _call_http(
        self, method: CallMethod, action: str, headers: dict[str, str] | None = None, params: dict | None = None
    ) -> dict:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        params = params or {}
        params = {k: v for k, v in params.items() if v is not None}
        if method in {"get", "fetch"}:
            async with self.session.get(
                (self.api_base / action).with_query(params),
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "patch":
            async with self.session.patch(
                (self.api_base / action),
                json=params,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "put":
            async with self.session.put(
                (self.api_base / action),
                json=params,
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method == "delete":
            async with self.session.delete(
                (self.api_base / action).with_query(params),
                headers=headers,
            ) as resp:
                return await validate_response(resp)

        if method in {"post", "update"}:
            async with self.session.post(
                (self.api_base / action),
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
                (self.api_base / action),
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
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        if self._access_token is None or (
            self._expires_in and datetime.now(timezone.utc) > self._expires_in - timedelta(seconds=30)
        ):
            async with self.session.post(
                self.auth_base,
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
        headers = {"Authorization": await self._get_authorization_header()}
        if self.intent.is_group_enabled:
            headers["X-Union-Appid"] = self.app_id
        return headers

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()
            gateway_info = await self.call_api("get", "gateway/bot")
            ws_url = gateway_info["url"]
            remain = gateway_info.get("session_start_limit", {}).get("remaining")
            if remain is not None and remain <= 0:
                logger.error("Session start limit reached, please wait for a while")
                return
        tasks = []
        async with self.stage("blocking"):
            if self.shard:
                tasks.append(
                    asyncio.create_task(self.connection_daemon(manager, self.session, ws_url, self.shard))
                )
            else:
                shards = gateway_info.get("shards") or 1
                logger.debug(f"Get Shards: {shards}")
                for i in range(shards):
                    tasks.append(
                        asyncio.create_task(self.connection_daemon(manager, self.session, ws_url, (i, shards)))
                    )
                    await asyncio.sleep(gateway_info.get("session_start_limit", {}).get("max_concurrency", 1))
            await any_completed(*tasks)

        async with self.stage("cleanup"):
            if self.session:
                await self.session.close()
            self.session = None
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    async def connection_daemon(
        self, manager: Launart, session: aiohttp.ClientSession, url: str, shard: tuple[int, int]
    ):
        while not manager.status.exiting:
            # try:
            #     async with session.ws_connect(url, timeout=30) as conn:
            ctx = session.ws_connect(url, timeout=30)
            try:
                conn = await ctx.__aenter__()
            except Exception as e:
                logger.error(f"{self} Websocket client connection failed: {e}")
                logger.debug(f"{self} Will retry in 5 seconds...")
                with suppress(AttributeError):
                    await ctx.__aexit__(None, None, None)
                await asyncio.sleep(5)
                continue

            self.connections[shard] = conn
            logger.info(f"{self.id} Websocket client connected")
            heartbeat_interval = await self._hello(shard)
            if not heartbeat_interval:
                await asyncio.sleep(3)
                continue
            result = await self._authenticate(shard)
            if not result:
                await asyncio.sleep(3)
                continue
            self.close_signal.clear()
            close_task = asyncio.create_task(self.close_signal.wait())
            receiver_task = asyncio.create_task(self.message_handle(shard))
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            heartbeat_task = asyncio.create_task(self._heartbeat(heartbeat_interval, shard))
            done, pending = await any_completed(
                sigexit_task,
                close_task,
                receiver_task,
                heartbeat_task,
            )
            if sigexit_task in done:
                logger.info(f"{self} Websocket client exiting...")
                await conn.close()
                self.close_signal.set()
                receiver_task.cancel()
                heartbeat_task.cancel()
                for login in self.logins:
                    login.status = LoginStatus.OFFLINE
                    await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
                self.logins.clear()
                await asyncio.sleep(1)
                return
            if close_task in done:
                receiver_task.cancel()
                heartbeat_task.cancel()
                logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")

                for login in self.logins:
                    login.status = LoginStatus.RECONNECT
                    await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")
                continue


__all__ = ["QQBotWebsocketAdapter", "Intents"]
