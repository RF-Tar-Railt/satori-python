from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Generic, Protocol, TypeVar, Union, runtime_checkable

from satori.const import Api
from satori.model import Event, Login

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
    def publisher(self) -> AsyncIterator[Event]: ...

    def authenticate(self, token: str) -> bool: ...

    async def get_logins(self) -> list[Login]: ...


@runtime_checkable
class Router(Protocol):
    def validate_headers(self, headers: dict[str, Any]) -> bool: ...

    async def call_api(self, request: Request[Any]) -> Any: ...

    async def call_internal_api(self, request: Request[Any]) -> Any: ...
