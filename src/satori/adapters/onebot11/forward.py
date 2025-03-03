from __future__ import annotations

import asyncio
import json
from contextlib import suppress
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
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter

from .api import apply
from .events.base import events
from .utils import USER_AVATAR_URL, onebot11_event_type


class OneBot11ForwardAdapter(BaseAdapter):

    session: ClientSession
    connection: ClientWebSocketResponse | None

    def __init__(
        self,
        endpoint: str | URL,
        access_token: str | None = None,
    ):
        super().__init__()
        self.endpoint = URL(endpoint)
        self.access_token = access_token
        self.close_signal = asyncio.Event()
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.response_waiters: dict[str, asyncio.Future] = {}
        self.logins: dict[str, Login] = {}

        apply(self, lambda _: self, lambda _: self.logins[_])

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
        return {"satori-python.server"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

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
                    if self_id not in self.logins:
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
                        self.logins[self_id] = login
                        self.queue.put_nowait(Event(EventType.LOGIN_ADDED, datetime.now(), login))
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
                    if self_id not in self.logins:
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
                        self.logins[self_id] = login
                        self.queue.put_nowait(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                    logger.trace(f"received heartbeat from {self_id}")
                else:
                    self_id = str(data["self_id"])
                    if self_id not in self.logins:
                        logger.warning(f"received event from unknown self_id: {data}")
                        return
                    login = self.logins[self_id]
                    handler = events.get(event_type)
                    if not handler:
                        event = Event(EventType.INTERNAL, datetime.now(), login, _type=event_type, _data=data)
                    else:
                        event = await handler(login, self, data)
                    if event:
                        self.queue.put_nowait(event)

            asyncio.create_task(event_parse_task(data))

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        async for msg in self.connection:
            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = json.loads(cast(str, msg.data))
                yield self, data
        else:
            self.close_signal.set()

    async def connection_daemon(self, manager: Launart, session: ClientSession):
        while not manager.status.exiting:
            ctx = session.ws_connect(
                self.endpoint,
                headers=(
                    {"Authorization": f"Bearer {access_token}"}
                    if (access_token := self.access_token) is not None
                    else None
                ),
            )
            try:
                self.connection = await ctx.__aenter__()
            except Exception as e:
                logger.error(f"{self} Websocket client connection failed: {e}")
                logger.debug(f"{self} Will retry in 5 seconds...")
                with suppress(AttributeError):
                    await ctx.__aexit__(None, None, None)
                await asyncio.sleep(5)
                continue
            logger.info(f"{self} Websocket client connected")
            self.close_signal.clear()
            if self.logins:
                for login in self.logins.values():
                    login.status = LoginStatus.ONLINE
                    self.queue.put_nowait(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
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
                    self.queue.put_nowait(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
                await asyncio.sleep(1)
                return
            if close_task in done:
                receiver_task.cancel()
                logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")
                for login in self.logins.values():
                    login.status = LoginStatus.RECONNECT
                    self.queue.put_nowait(Event(EventType.LOGIN_UPDATED, datetime.now(), login))
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")
                continue

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

    async def call_api(self, action: str, params: dict | None = None) -> dict | None:
        if not self.connection:
            raise RuntimeError("connection is not established")

        future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        echo = str(hash(future))
        self.response_waiters[echo] = future

        try:
            await self.connection.send_json({"action": action, "params": params or {}, "echo": echo})
            result = await future
        finally:
            del self.response_waiters[echo]

        if result["status"] != "ok":
            raise ActionFailed(f"{result['retcode']}: {result}", result)

        return result.get("data")

    def __str__(self):
        return self.id


Adapter = OneBot11ForwardAdapter
