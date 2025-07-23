from __future__ import annotations

import asyncio
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
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter

from .api import apply
from .events.base import events
from .utils import USER_AVATAR_URL, onebot11_event_type


class _Connection:
    def __init__(self, adapter: OneBot11ReverseAdapter, ws: WebSocket):
        self.adapter = adapter
        self.ws = ws
        self.close_signal = asyncio.Event()
        self.response_waiters: dict[str, asyncio.Future] = {}

    async def message_receive(self):
        async for msg in self.ws.iter_json():
            yield self, msg
        else:
            self.close_signal.set()

    async def message_handle(self):
        async for connection, data in self.message_receive():
            if echo := data.get("echo"):
                if future := self.response_waiters.get(echo):
                    future.set_result(data)
                continue

            async def event_parse_task(data: dict):
                event_type = onebot11_event_type(data)
                if event_type == "meta_event.lifecycle.connect":
                    self_id = str(data["self_id"])
                    if self_id not in self.adapter.logins:
                        self_info = await self.call_api("get_login_info")
                        login = Login(
                            0,
                            LoginStatus.ONLINE,
                            "onebot",
                            platform="onebot",
                            user=User(
                                self_id,
                                (self_info or {})["nickname"],
                                avatar=USER_AVATAR_URL.format(uin=self_id),
                            ),
                            features=["guild.plain"],
                        )
                        self.adapter.logins[self_id] = login
                        self.adapter.queue.put_nowait(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                elif event_type == "meta_event.lifecycle.enable":
                    logger.warning(
                        f"received lifecycle.enable event that is only supported in http adapter: {data}"
                    )
                    return
                elif event_type == "meta_event.lifecycle.disable":
                    logger.warning(
                        f"received lifecycle.disable event that is only supported in http adapter: {data}"
                    )
                    return
                elif event_type == "meta_event.heartbeat":
                    self_id = str(data["self_id"])
                    if self_id not in self.adapter.logins:
                        self_info = await self.call_api("get_login_info")
                        login = Login(
                            0,
                            LoginStatus.ONLINE,
                            "onebot",
                            platform="onebot",
                            user=User(
                                self_id,
                                (self_info or {})["nickname"],
                                avatar=USER_AVATAR_URL.format(uin=self_id),
                            ),
                            features=["guild.plain"],
                        )
                        self.adapter.logins[self_id] = login
                        self.adapter.queue.put_nowait(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                    logger.trace(f"received heartbeat from {self_id}")
                else:
                    self_id = str(data["self_id"])
                    if self_id not in self.adapter.logins:
                        logger.warning(f"received event from unknown self_id: {data}")
                        return
                    login = self.adapter.logins[self_id]
                    handler = events.get(event_type)
                    if not handler:
                        event = Event(EventType.INTERNAL, datetime.now(), login, _type=event_type, _data=data)
                    else:
                        event = await handler(login, self, data)
                    if event:
                        self.adapter.queue.put_nowait(event)

            asyncio.create_task(event_parse_task(data))

    async def call_api(self, action: str, params: dict | None = None) -> dict | None:
        if not self.ws:
            raise RuntimeError("connection is not established")

        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        echo = str(hash(future))
        self.response_waiters[echo] = future

        try:
            await self.ws.send_json({"action": action, "params": params or {}, "echo": echo})
            result = await future
        finally:
            del self.response_waiters[echo]

        if result["status"] != "ok":
            raise ActionFailed(f"{result['retcode']}: {result}", result)

        return result.get("data")


class OneBot11ReverseAdapter(BaseAdapter):

    def __init__(
        self,
        prefix: str = "/",
        path: str = "onebot/v11",
        endpoint: str = "ws",
        access_token: str | None = None,
    ):
        super().__init__()
        self.endpoint = URL(prefix) / path / endpoint
        self.access_token = access_token
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.logins: dict[str, Login] = {}
        self.connections: dict[str, _Connection] = {}

        apply(self, lambda _: self.connections[_], lambda _: self.logins[_])

    async def publisher(self):
        while True:
            event = await self.queue.get()
            yield event

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "onebot" and self_id in self.logins

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

    async def websocket_server_handler(self, ws: WebSocket):
        if ws.headers.get("Authorization", "")[7:] != (self.access_token or ""):
            return await ws.close(1008, "Authorization Header is invalid")

        if "X-Self-ID" not in ws.headers:
            return await ws.close(1008, "Missing X-Self-ID Header")

        account_id = ws.headers["X-Self-ID"]
        if account_id in self.connections:
            return await ws.close(1008, "Duplicate X-Self-ID")

        await ws.accept()
        connection = _Connection(self, ws)
        self.connections[account_id] = connection

        try:
            await any_completed(connection.message_handle(), connection.close_signal.wait())
        finally:
            del self.connections[account_id]
            logger.info(f"Websocket {ws} closed")
            self.logins[account_id].status = LoginStatus.OFFLINE
            self.queue.put_nowait(Event(EventType.LOGIN_REMOVED, datetime.now(), self.logins[account_id]))
            await asyncio.sleep(1)

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            pass

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            pass

    def get_routes(self):
        return [
            WebSocketRoute(str(self.endpoint), self.websocket_server_handler),
        ]

    def get_platform(self) -> str:
        return "onebot"

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            self_id = request.self_id
            return JSONResponse(
                await self.connections[self_id].call_api(path[5:], await request.origin.json())
            )
        async with self.server.session.get(path) as resp:
            return Response(await resp.read())

    def __str__(self):
        return self.id


Adapter = OneBot11ReverseAdapter
