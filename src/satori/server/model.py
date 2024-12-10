from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Optional, Protocol, TypeVar, Union, runtime_checkable

from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from satori.const import Api
from satori.model import Event, Login

if TYPE_CHECKING:
    from .route import RouteCall

JsonType = Union[list, dict, str, int, bool, float, None]
TA = TypeVar("TA", str, Api)
TP = TypeVar("TP")


@dataclass
class Request(Generic[TP]):
    origin: StarletteRequest
    action: str
    params: TP
    platform: str
    self_id: str


@runtime_checkable
class Provider(Protocol):
    def publisher(self) -> AsyncIterator[Event]: ...

    async def get_logins(self) -> list[Login]: ...

    @staticmethod
    def proxy_urls() -> list[str]: ...

    def ensure(self, platform: str, self_id: str) -> bool: ...

    async def handle_internal(self, request: Request, path: str) -> Response: ...

    async def handle_proxied(self, prefix: str, url: str) -> Optional[Response]: ...


@runtime_checkable
class Router(Protocol):
    routes: dict[str, "RouteCall[Any, Any]"]


@dataclass
class WebhookEndpoint:
    url: str
    token: Optional[str] = None
