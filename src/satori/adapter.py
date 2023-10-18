from __future__ import annotations

from abc import abstractmethod
from typing import Any, Awaitable, Callable

from launart import Service
from starlette.datastructures import Headers

from .model import Event, Login


class Adapter(Service):
    @abstractmethod
    def get_platform(self) -> str:
        ...

    @abstractmethod
    def bind_event_callback(self, callback: Callable[[Event], Awaitable[Any]]):
        ...

    @abstractmethod
    def validate_headers(self, headers: Headers) -> bool:
        ...

    @abstractmethod
    def authenticate(self, token: str) -> bool:
        ...

    @abstractmethod
    async def get_logins(self) -> list[Login]:
        ...

    @abstractmethod
    async def call_api(self, headers: Headers, action: str, params: Any) -> Any:
        ...

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"
