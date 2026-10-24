from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import cast

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse
from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
from yarl import URL

from satori import Event, EventType, LoginStatus
from satori.exception import ActionFailed
from satori.model import Login, User
from satori.reconnect import RECONNECT_STABLE_SECONDS, ReconnectPolicy, is_normal_close, is_server_shutdown
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter
from satori.utils import decode, encode

from .api import apply
from .events.base import events
from .utils import USER_AVATAR_URL, onebot11_event_type


@dataclass
class OneBot11ForwardConfig:
    endpoint: str
    """连接 OneBot V11协议端的路径"""
    access_token: str | None = None
    """OneBot V11协议的访问令牌, 默认为空"""
    timeout: float = 60
    """连接超时时间, 默认为 60 秒"""


class OneBot11ForwardAdapter(BaseAdapter[OneBot11ForwardConfig]):

    session: ClientSession
    connection: ClientWebSocketResponse | None

    def __init__(
        self,
        config: OneBot11ForwardConfig,
    ):
        super().__init__()
        self.config = config
        self.endpoint = URL(config.endpoint)
        self.timeout = config.timeout
        self.access_token = config.access_token
        self.close_signal = asyncio.Event()
        self.response_waiters: dict[str, asyncio.Future] = {}
        self.logins: dict[str, Login] = {}

        apply(self, lambda _: self, lambda _: self.logins[_])

    def ensure(self, platform: str, self_id: str) -> bool:
        return (
            platform == "qq-client"
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

    async def message_handle(self):
        async def _login_update(add=True):
            self_info = await self.call_api("get_login_info")
            login = Login(
                sn=0,
                status=LoginStatus.ONLINE,
                adapter="onebot",
                platform="qq-client",
                user=User(
                    self_id,
                    (self_info or {})["nickname"],
                    avatar=USER_AVATAR_URL.format(uin=self_id),
                ),
                features=["guild.plain"],
            )
            self.logins[self_id] = login
            if add:
                await self.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
            else:
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

        async for connection, data in self.message_receive():
            if echo := data.get("echo"):
                if future := self.response_waiters.get(echo):
                    future.set_result(data)
                continue

            event_type = onebot11_event_type(data)
            if event_type == "meta_event.lifecycle.connect":
                self_id = str(data["self_id"])
                if self_id not in self.logins:
                    asyncio.create_task(_login_update())
                else:
                    asyncio.create_task(_login_update(add=False))
            elif event_type == "meta_event.lifecycle.enable":
                logger.warning(f"received lifecycle.enable event that is only supported in http adapter: {data}")
                continue
            elif event_type == "meta_event.lifecycle.disable":
                logger.warning(f"received lifecycle.disable event that is only supported in http adapter: {data}")
                continue
            elif event_type == "meta_event.heartbeat":
                self_id = str(data["self_id"])
                if self_id not in self.logins:
                    asyncio.create_task(_login_update())
                logger.trace(f"received heartbeat from {self_id}")
            else:
                self_id = str(data["self_id"])
                if self_id not in self.logins:
                    logger.warning(f"received event from unknown self_id: {data}")
                    continue
                login = self.logins[self_id]
                handler = events.get(event_type)

                async def _event_parse(
                    _login=login,
                    _handler=handler,
                    _data=data,
                    _event_type=event_type,
                ):
                    event = None
                    if _handler:
                        try:
                            event = await _handler(_login, self, _data)
                        except Exception as e:
                            logger.exception(f"failed to handle event {event_type}: {e!r}")
                            event = None
                    if not event:
                        event = Event(EventType.INTERNAL, datetime.now(), _login)
                    event._type = _event_type
                    event._data = _data
                    await self.server.post(event)

                asyncio.create_task(_event_parse())

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        async for msg in self.connection:
            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = decode(cast(str, msg.data))
                yield self, data
        else:
            self.close_signal.set()

    async def connection_daemon(self, manager: Launart, session: ClientSession):
        policy = ReconnectPolicy()
        while not manager.status.exiting:
            ctx = session.ws_connect(
                self.endpoint,
                headers=(
                    {"Authorization": f"Bearer {access_token}"}
                    if (access_token := self.access_token) is not None
                    else None
                ),
                timeout=self.timeout,
            )
            for login in self.logins.values():
                login.status = LoginStatus.RECONNECT
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
            try:
                self.connection = await ctx.__aenter__()
            except Exception as e:
                logger.error(f"{self} Websocket client connection failed: {e}")
                with suppress(AttributeError):
                    await ctx.__aexit__(None, None, None)
                if not await policy.sleep():
                    logger.error(f"{self} Reconnect attempts exhausted, marking logins offline")
                    for login in self.logins.values():
                        login.status = LoginStatus.OFFLINE
                        await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
                    return
                logger.info(f"{self} Reconnecting...")
                continue
            logger.info(f"{self} Websocket client connected")
            connected_at = asyncio.get_running_loop().time()
            for login in self.logins.values():
                login.status = LoginStatus.CONNECT
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
            self.close_signal.clear()
            close_task = asyncio.create_task(self.close_signal.wait())
            receiver_task = asyncio.create_task(self.message_handle())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())

            done, pending = await any_completed(
                sigexit_task,
                close_task,
                receiver_task,
            )
            if sigexit_task in done:
                logger.info(f"{self} Websocket client exiting...")
                await self.connection.close()
                self.close_signal.set()
                self.connection = None
                for login in self.logins.values():
                    login.status = LoginStatus.OFFLINE
                    await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
                self.logins.clear()
                for fut in self.response_waiters.values():
                    fut.cancel()
                await asyncio.sleep(1)
                return

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for fut in self.response_waiters.values():
                fut.cancel()
            code = self.connection.close_code if self.connection else None
            if self.connection and not self.connection.closed:
                await self.connection.close()
            self.connection = None
            if is_normal_close(code):
                logger.info(f"{self} Connection closed by server (code={code}), login removed")
                for login in self.logins.values():
                    login.status = LoginStatus.OFFLINE
                    await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
                self.logins.clear()
                if not is_server_shutdown(code):
                    return
            if asyncio.get_running_loop().time() - connected_at >= RECONNECT_STABLE_SECONDS:
                policy.reset()
            for login in self.logins.values():
                login.status = LoginStatus.RECONNECT
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
            if not await policy.sleep():
                logger.error(f"{self} Reconnect attempts exhausted, marking logins offline")
                for login in self.logins.values():
                    login.status = LoginStatus.OFFLINE
                    await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
                return
            logger.info(f"{self} Reconnecting...")

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = ClientSession()

        async with self.stage("blocking"):
            await self.connection_daemon(manager, self.session)

        async with self.stage("cleanup"):
            await self.session.close()
            self.connection = None

    def get_platform(self) -> str:
        return "onebot"

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            return JSONResponse(await self.call_api(path[5:], await request.origin.json()))
        async with self.session.get(path) as resp:
            return Response(await resp.read())

    async def call_api(self, action: str, params: dict | None = None) -> dict:
        if not self.connection:
            raise RuntimeError("connection is not established")

        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        echo = str(hash(future))
        self.response_waiters[echo] = future

        try:
            await self.connection.send_str(encode({"action": action, "params": params or {}, "echo": echo}))
            result = await asyncio.wait_for(future, timeout=self.timeout)
        finally:
            del self.response_waiters[echo]

        if result["status"] != "ok":
            raise ActionFailed(f"{result['retcode']}: {result}", result)

        return result.get("data", {})

    def __str__(self):
        return self.id


Adapter = OneBot11ForwardAdapter
