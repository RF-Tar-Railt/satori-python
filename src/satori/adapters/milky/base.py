from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing_extensions import TypeVar

import aiohttp
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
from .utils import decode_login_user

DEFAULT_FEATURES = ["guild.plain", "reaction"]


@dataclass
class MilkyBaseConfig:
    endpoint: str
    """连接 Milky 协议端的路径"""
    token: str | None = None
    """Milky 协议的访问令牌, 默认为空"""
    token_in_query: bool = False
    """是否将 token 放在查询参数中, 默认为 False"""
    headers: dict[str, str] = field(default_factory=dict)
    """连接时使用的自定义请求头, 默认为空字典"""
    fetch_forward_message: bool = False
    """是否在事件中获取转发消息, 默认为 False"""


TMilkyBaseConfig = TypeVar("TMilkyBaseConfig", bound=MilkyBaseConfig, default=MilkyBaseConfig)


class MilkyBaseAdapter(BaseAdapter[TMilkyBaseConfig], ABC):
    """Base adapter for Milky protocol with common functionality."""

    session: aiohttp.ClientSession | None

    def __init__(
        self,
        config: TMilkyBaseConfig,
    ):
        super().__init__()
        self.config = config
        self.base_url = URL(self.config.endpoint)
        base_path = self.base_url.path.rstrip("/")
        self.api_base = self.base_url.with_path(f"{base_path}/api")
        self.token = config.token
        self.headers = config.headers.copy()
        self.session = None
        self.logins: dict[str, Login] = {}
        self.fetch_forward_message = config.fetch_forward_message
        self.features: list[str] = list(DEFAULT_FEATURES)
        apply(self, lambda _: self, self._get_login)

    def get_platform(self) -> str:
        return "milky"

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
        event = None
        if handler:
            try:
                event = await handler(login, self, payload)
            except Exception as e:
                logger.exception(f"failed to handle event {event_type}: {e!r}")
                event = None
        if not event:
            event = Event(
                EventType.INTERNAL,
                datetime.fromtimestamp(payload.get("time", datetime.now().timestamp())),
                login,
            )
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
        login = Login(
            sn=0,
            status=LoginStatus.ONLINE,
            adapter="milky",
            platform="qq-client",
            user=user,
            features=self.features.copy(),
        )
        self_id = login.id
        previous = self.logins.get(self_id)
        self.logins[self_id] = login
        event_type = EventType.LOGIN_ADDED if previous is None else EventType.LOGIN_UPDATED
        await self.server.post(Event(event_type, datetime.now(), login))

    async def _mark_reconnecting(self):
        for login in self.logins.values():
            if login.status != LoginStatus.RECONNECT:
                login.status = LoginStatus.RECONNECT
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def _mark_offline(self):
        for login in self.logins.values():
            if login.status != LoginStatus.OFFLINE:
                login.status = LoginStatus.OFFLINE
                await self.server.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login))

    async def _handle_disconnect(self):
        for self_id, login in list(self.logins.items()):
            login.status = LoginStatus.OFFLINE
            await self.server.post(Event(EventType.LOGIN_REMOVED, datetime.now(), login))
            self.logins.pop(self_id, None)

    def _get_login(self, self_id: str) -> Login:
        return self.logins[self_id]


__all__ = ["MilkyBaseAdapter", "DEFAULT_FEATURES", "MilkyBaseConfig"]
