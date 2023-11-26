from abc import abstractmethod
from typing import Any, AsyncIterator, Dict, List

from launart import Service

from satori.const import Api

from ..model import Event, Login
from .model import Request


class Adapter(Service):
    @abstractmethod
    def get_platform(self) -> str:
        ...

    @abstractmethod
    def publisher(self) -> AsyncIterator[Event]:
        ...

    @abstractmethod
    def validate_headers(self, headers: Dict[str, Any]) -> bool:
        ...

    @abstractmethod
    def authenticate(self, token: str) -> bool:
        ...

    @abstractmethod
    async def get_logins(self) -> List[Login]:
        ...

    @abstractmethod
    async def call_api(self, request: Request[Api]) -> Any:
        ...

    @abstractmethod
    async def call_internal_api(self, request: Request[str]) -> Any:
        ...

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"
