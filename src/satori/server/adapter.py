from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Optional, Union

from launart import Service
from starlette.responses import Response
from starlette.routing import BaseRoute

from satori.model import Event, Login, LoginPartial

from .model import Request
from .route import RouterMixin
from .utils import ctx

if TYPE_CHECKING:
    from . import Server


LoginType = Union[Login, LoginPartial]


class Adapter(Service, RouterMixin):
    server: "Server"

    @abstractmethod
    def get_platform(self) -> str: ...

    @abstractmethod
    def publisher(self) -> AsyncIterator[Event]: ...

    @abstractmethod
    def ensure(self, platform: str, self_id: str) -> bool: ...

    @staticmethod
    def proxy_urls() -> list[str]:
        return []

    @abstractmethod
    async def handle_internal(self, request: Request, path: str) -> Response: ...

    async def handle_proxied(self, prefix: str, url: str) -> Optional[Response]:
        async with self.server.session.get(url, ssl=ctx) as resp:
            return Response(await resp.read())

    @abstractmethod
    async def get_logins(self) -> list[LoginType]: ...

    def __init__(self):
        super().__init__()
        self.routes = {}

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"

    def ensure_server(self, server: "Server"):
        self.server = server

    def get_routes(self) -> list[BaseRoute]:
        """return extra routes that will mount to the server root"""
        return []
