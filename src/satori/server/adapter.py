from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Optional

from launart import Service

from ..model import Event, Login
from .route import RouterMixin

if TYPE_CHECKING:
    from . import Server


class Adapter(Service, RouterMixin):
    server: "Server"

    @abstractmethod
    def get_platform(self) -> str: ...

    @abstractmethod
    def publisher(self) -> AsyncIterator[Event]: ...

    @abstractmethod
    def ensure(self, platform: str, self_id: str) -> bool: ...

    @abstractmethod
    def authenticate(self, token: Optional[str]) -> bool: ...

    @staticmethod
    def proxy_urls() -> list[str]:
        return []

    @abstractmethod
    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes: ...

    @abstractmethod
    async def get_logins(self) -> list[Login]: ...

    def __init__(self):
        super().__init__()
        self.routes = {}

    @property
    def id(self):
        return f"satori-python.adapter.{self.get_platform()}#{id(self)}"

    def ensure_server(self, server: "Server"):
        self.server = server
