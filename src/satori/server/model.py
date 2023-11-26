from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Generic, Protocol, TypeVar, runtime_checkable

from satori.const import Api
from satori.model import Event, Login

TA = TypeVar("TA", str, Api)


@dataclass
class Request(Generic[TA]):
    headers: dict[str, Any]
    action: TA
    params: Any


@runtime_checkable
class Provider(Protocol):
    def publisher(self) -> AsyncIterator[Event]:
        ...

    def authenticate(self, token: str) -> bool:
        ...

    async def get_logins(self) -> list[Login]:
        ...


@runtime_checkable
class Router(Protocol):
    def validate_headers(self, headers: dict[str, Any]) -> bool:
        ...

    async def call_api(self, request: Request[Api]) -> Any:
        ...

    async def call_internal_api(self, request: Request[str]) -> Any:
        ...
