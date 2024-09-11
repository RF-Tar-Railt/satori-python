from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Optional, Protocol, TypeVar, Union, runtime_checkable

from satori.const import Api
from satori.model import Event, Login

if TYPE_CHECKING:
    from .route import RouteCall

JsonType = Union[list, dict, str, int, bool, float, None]
TA = TypeVar("TA", str, Api)
TP = TypeVar("TP")


@dataclass
class Request(Generic[TP]):
    headers: dict[str, Any]
    action: str
    params: TP


@runtime_checkable
class Provider(Protocol):
    @property
    def id(self) -> str: ...

    def publisher(self) -> AsyncIterator[Event]: ...

    def authenticate(self, token: Optional[str]) -> bool: ...

    async def get_logins(self) -> list[Login]: ...

    @staticmethod
    def proxy_urls() -> list[str]: ...

    def ensure(self, platform: str, self_id: str) -> bool: ...

    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes: ...

    async def download_proxied(self, prefix: str, url: str) -> bytes: ...


@runtime_checkable
class Router(Protocol):
    routes: dict[str, "RouteCall[Any, Any]"]
