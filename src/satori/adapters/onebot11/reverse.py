from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from yarl import URL

from satori import Event, EventType, LoginStatus
from satori.exception import ActionFailed
from satori.model import Login, User
from satori.reconnect import RECONNECT_TOTAL_SECONDS, is_normal_close
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter
from satori.utils import decode, encode

from .api import apply
from .events.base import events
from .utils import USER_AVATAR_URL, onebot11_event_type


class _Connection:
    def __init__(self, adapter: OneBot11ReverseAdapter, ws: WebSocket):
        self.adapter = adapter
        self.ws = ws
        self.close_signal = asyncio.Event()
        self.close_code: int | None = None
        self.response_waiters: dict[str, asyncio.Future] = {}

    async def message_receive(self):

        while True:
            message = await self.ws.receive()

            if message["type"] == "websocket.disconnect":
                self.close_code = message.get("code")
                break
            yield self, decode(message["text"])
        # async for msg in self.ws.iter_text():
        #     yield self, decode(msg)
        # else:
        self.close_signal.set()

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
            self.adapter.logins[self_id] = login
            if add:
                await self.adapter.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
            else:
                await self.adapter.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

        async for connection, data in self.message_receive():
            if echo := data.get("echo"):
                if future := self.response_waiters.get(echo):
                    future.set_result(data)
                continue

            event_type = onebot11_event_type(data)
            if event_type == "meta_event.lifecycle.connect":
                self_id = str(data["self_id"])
                if self_id not in self.adapter.logins:
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
                if self_id not in self.adapter.logins:
                    asyncio.create_task(_login_update())
                logger.trace(f"received heartbeat from {self_id}")
            else:
                self_id = str(data["self_id"])
                if self_id not in self.adapter.logins:
                    logger.warning(f"received event from unknown self_id: {data}")
                    continue
                login = self.adapter.logins[self_id]
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
                            logger.exception(f"failed to handle event {_event_type}: {e!r}")
                            event = None
                    if not event:
                        event = Event(EventType.INTERNAL, datetime.now(), _login)
                    event._type = _event_type
                    event._data = _data
                    await self.adapter.server.post(event)

                asyncio.create_task(_event_parse())

    async def call_api(self, action: str, params: dict | None = None) -> dict:
        if not self.ws:
            raise RuntimeError("connection is not established")

        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        echo = str(hash(future))
        self.response_waiters[echo] = future

        try:
            await self.ws.send_text(encode({"action": action, "params": params or {}, "echo": echo}))
            result = await asyncio.wait_for(future, timeout=self.adapter.timeout)
        finally:
            del self.response_waiters[echo]

        if result["status"] != "ok":
            raise ActionFailed(f"{result['retcode']}: {result}", result)

        return result.get("data", {})


@dataclass
class OneBot11ReverseConfig:
    prefix: str = "/"
    """反向适配器于 Server 的路径前缀, 默认为 /"""
    path: str = "onebot/v11"
    """反向适配器于 Server 的路径, 默认为 onebot/v11"""
    endpoint: str = "ws"
    """反向适配器于 Server 的路径端点, 默认为 ws (完整路径即为 /onebot/v11/ws)"""
    access_token: str | None = None
    """反向适配器的访问令牌, 默认为空"""
    timeout: int = 60
    """发送请求的超时时间，默认为 60 秒"""


class OneBot11ReverseAdapter(BaseAdapter[OneBot11ReverseConfig]):

    def __init__(
        self,
        config: OneBot11ReverseConfig,
    ):
        super().__init__()
        self.config = config
        self.endpoint = URL(config.prefix) / config.path / config.endpoint
        self.access_token = config.access_token
        self.logins: dict[str, Login] = {}
        self.connections: dict[str, _Connection] = {}
        self.offline_tasks: dict[str, asyncio.Task] = {}
        self.timeout = config.timeout

        apply(self, lambda _: self.connections[_], lambda _: self.logins[_])

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "qq-client" and self_id in self.connections

    async def get_logins(self) -> list[Login]:
        logins = list(self.logins.values())
        for index, login in enumerate(logins):
            login.sn = index
        return logins

    @property
    def required(self) -> set[str]:
        return {"satori-python.server", "asgi.service/uvicorn"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    def _cancel_offline_task(self, account_id: str):
        task = self.offline_tasks.pop(account_id, None)
        if task:
            task.cancel()

    async def _mark_offline_later(self, account_id: str):
        try:
            await asyncio.sleep(RECONNECT_TOTAL_SECONDS)
        except asyncio.CancelledError:
            return
        self.offline_tasks.pop(account_id, None)
        if account_id in self.connections:
            return
        login = self.logins.get(account_id)
        if login and login.status == LoginStatus.RECONNECT:
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def websocket_server_handler(self, ws: WebSocket):
        if ws.headers.get("Authorization", "")[7:] != (self.access_token or ""):
            return await ws.close(1008, "Authorization Header is invalid")

        if "X-Self-ID" not in ws.headers:
            return await ws.close(1008, "Missing X-Self-ID Header")

        account_id = ws.headers["X-Self-ID"]
        if account_id in self.connections:
            return await ws.close(1008, "Duplicate X-Self-ID")
        self._cancel_offline_task(account_id)
        login = self.logins.get(account_id)
        if login:
            login.status = LoginStatus.RECONNECT
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
        await ws.accept()
        login = self.logins.get(account_id)
        if login:
            login.status = LoginStatus.CONNECT
            await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
        connection = _Connection(self, ws)
        self.connections[account_id] = connection
        close_task = asyncio.create_task(connection.close_signal.wait())
        receiver_task = asyncio.create_task(
            connection.message_handle(),
        )
        sigexit_task = asyncio.create_task(self.manager.status.wait_for_sigexit())  # type: ignore
        done, pending = await any_completed(
            sigexit_task,
            close_task,
            receiver_task,
        )
        if sigexit_task in done:
            logger.info(f"{self} Websocket server exiting...")
            await connection.ws.close(reason="Server exiting")
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            del self.connections[account_id]
            for fut in connection.response_waiters.values():
                fut.cancel()
            self._cancel_offline_task(account_id)
            login = self.logins.get(account_id)
            if login:
                login.status = LoginStatus.OFFLINE
                await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
            self.logins.pop(account_id, None)
            await asyncio.sleep(1)
            return

        if close_task in done or receiver_task in done:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self.connections.pop(account_id, None)
            logger.warning(f"Websocket {ws} closed (code={connection.close_code})")
            for fut in connection.response_waiters.values():
                fut.cancel()
            self._cancel_offline_task(account_id)
            login = self.logins.get(account_id)
            if login:
                if is_normal_close(connection.close_code):
                    login.status = LoginStatus.OFFLINE
                    await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
                    self.logins.pop(account_id, None)
                else:
                    login.status = LoginStatus.RECONNECT
                    await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
                    self.offline_tasks[account_id] = asyncio.create_task(self._mark_offline_later(account_id))
            await asyncio.sleep(1)

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            pass

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            for task in self.offline_tasks.values():
                task.cancel()
            self.offline_tasks.clear()

    def get_routes(self):
        return [
            WebSocketRoute(str(self.endpoint), self.websocket_server_handler),
        ]

    def get_platform(self) -> str:
        return "onebot"

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            self_id = request.self_id
            return JSONResponse(await self.connections[self_id].call_api(path[5:], await request.origin.json()))
        async with self.server.session.get(path) as resp:
            return Response(await resp.read())

    def __str__(self):
        return self.id


Adapter = OneBot11ReverseAdapter
