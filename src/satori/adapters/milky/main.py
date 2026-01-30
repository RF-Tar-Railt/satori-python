from __future__ import annotations

import asyncio
from datetime import datetime

import aiohttp
from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
from yarl import URL

from satori import EventType
from satori.exception import ActionFailed
from satori.model import Event, Login, LoginStatus
from satori.server.adapter import Adapter as BaseAdapter
from satori.server.model import Request
from satori.utils import decode, encode

from .api import apply
from .events import event_handlers
from .utils import MilkyNetwork, decode_login_user

DEFAULT_FEATURES = ["guild.plain", "reaction"]


class _MilkyNetwork:
    def __init__(self, adapter: MilkyAdapter):  # type: ignore[name-defined]
        self.adapter = adapter

    async def call_api(self, action: str, params: dict | None = None):
        return await self.adapter.call_api(action, params or {})


class MilkyAdapter(BaseAdapter):

    session: aiohttp.ClientSession | None
    connection: aiohttp.ClientWebSocketResponse | None

    def __init__(
        self,
        endpoint: str | URL,
        *,
        token: str | None = None,
        token_in_query: bool = False,
        headers: dict[str, str] | None = None,
    ):
        super().__init__()
        self.base_url = URL(str(endpoint))
        base_path = self.base_url.path.rstrip("/")
        self.api_base = self.base_url.with_path(f"{base_path}/api")
        ws_scheme = "wss" if self.base_url.scheme == "https" else "ws"
        self.event_url = self.base_url.with_scheme(ws_scheme).with_path(f"{base_path}/event")
        if token_in_query and token:
            self.event_url = self.event_url.update_query(access_token=token)
        self.token = token
        self.headers = headers.copy() if headers else {}
        self.session = None
        self.connection = None
        self.close_signal = asyncio.Event()
        self.logins: dict[str, Login] = {}
        self.networks: dict[str, MilkyNetwork] = {}
        self.features = list(DEFAULT_FEATURES)
        apply(self, self._get_network, self._get_login)

    def get_platform(self) -> str:
        return "milky"

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "milky" and self_id in self.logins

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

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.connection_daemon(manager, self.session)

        async with self.stage("cleanup"):
            if self.connection and not self.connection.closed:
                await self.connection.close()
            if self.session:
                await self.session.close()
            self.connection = None
            self.session = None
            await self._handle_disconnect()

    def proxy_urls(self) -> list[str]:
        return []

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            data = await request.origin.json()
            return JSONResponse(await self.call_api(path[5:], data))
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        url = self.base_url.with_path(path)
        headers = self.headers.copy()
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        async with self.session.get(url, headers=headers) as resp:
            content = await resp.read()
            return Response(content=content, media_type=resp.headers.get("Content-Type"))

    async def call_api(self, action: str, params: dict | None = None) -> dict:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")
        url = self.api_base.with_path(f"{self.api_base.path.rstrip('/')}/{action}")
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        async with self.session.post(url, data=encode(params or {}), headers=headers) as resp:
            resp.raise_for_status()
            data = decode(await resp.text())
        if data.get("status") == "failed" or data.get("retcode", 0) != 0:
            raise ActionFailed(f"{data.get('retcode')}: {data.get('message')}", data)
        return data.get("data")

    async def connection_daemon(self, manager: Launart, session: aiohttp.ClientSession):
        while not manager.status.exiting:
            headers = self.headers.copy()
            if self.token:
                headers.setdefault("Authorization", f"Bearer {self.token}")
            try:
                self.connection = await session.ws_connect(self.event_url, headers=headers)
            except Exception as e:
                logger.error(f"Milky adapter websocket connect failed: {e}")
                await asyncio.sleep(5)
                continue
            logger.info("Milky adapter websocket connected")
            self.close_signal.clear()
            await self.refresh_login()
            receiver_task = asyncio.create_task(self.message_handle())
            close_task = asyncio.create_task(self.close_signal.wait())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())

            done, pending = await any_completed(receiver_task, close_task, sigexit_task)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if sigexit_task in done:
                break
            logger.warning("Milky adapter websocket closed, retrying in 5 seconds")
            await self._handle_disconnect()
            await asyncio.sleep(5)
        await self._handle_disconnect()

    async def message_handle(self):
        assert self.connection is not None
        async for msg in self.connection:
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                self.close_signal.set()
                break
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                data = decode(msg.data)
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"Failed to decode milky event: {e}")
                continue
            if not isinstance(data, dict):
                continue
            await self.handle_event(data)

    async def handle_event(self, payload: dict):
        event_type = payload.get("event_type")
        self_id = str(payload.get("self_id"))
        if not event_type or not self_id:
            return
        if self_id not in self.logins:
            await self.refresh_login()
        if self_id not in self.logins:
            logger.warning(f"Ignoring event for unknown self_id {self_id}")
            return
        login = self.logins[self_id]
        handler = event_handlers.get(event_type)
        network = self.networks.get(self_id)
        if not network:
            network = _MilkyNetwork(self)
            self.networks[self_id] = network
        if handler:
            event = await handler(login, network, payload)
        else:
            event = Event(
                EventType.INTERNAL,
                datetime.fromtimestamp(payload.get("time", datetime.now().timestamp())),
                login,
            )
        if event:
            event._type = event_type
            event._data = payload.get("data", {})
            await self.server.post(event)

    async def refresh_login(self):
        try:
            data = await self.call_api("get_login_info", {})
        except Exception as e:
            logger.error(f"Failed to fetch milky login info: {e}")
            return
        if not data:
            return
        user = decode_login_user(data)
        login = Login(0, LoginStatus.ONLINE, "milky", platform="milky", user=user, features=self.features.copy())
        self_id = login.id
        previous = self.logins.get(self_id)
        self.logins[self_id] = login
        self.networks[self_id] = _MilkyNetwork(self)
        event_type = EventType.LOGIN_ADDED if previous is None else EventType.LOGIN_UPDATED
        await self.server.post(Event(event_type, datetime.now(), login))

    async def _handle_disconnect(self):
        for self_id, login in list(self.logins.items()):
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
            self.logins.pop(self_id, None)
            self.networks.pop(self_id, None)
        if self.connection and not self.connection.closed:
            await self.connection.close()
        self.close_signal.set()

    def _get_network(self, self_id: str) -> MilkyNetwork:
        network = self.networks.get(self_id)
        if not network:
            network = _MilkyNetwork(self)
            self.networks[self_id] = network
        return network

    def _get_login(self, self_id: str) -> Login:
        return self.logins[self_id]


__all__ = ["MilkyAdapter"]
