from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator

from launart import Service

from ..model import Event, Login


@dataclass
class Request:
    headers: dict[str, Any]
    action: str
    params: Any


class Adapter(Service):
    @abstractmethod
    def get_platform(self) -> str:
        ...

    @abstractmethod
    def publisher(self) -> AsyncIterator[Event]:
        ...

    @abstractmethod
    def validate_headers(self, headers: dict[str, Any]) -> bool:
        ...

    @abstractmethod
    def authenticate(self, token: str) -> bool:
        ...

    @abstractmethod
    async def get_logins(self) -> list[Login]:
        ...

    @abstractmethod
    async def call_api(self, request: Request) -> Any:
        ...

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"
