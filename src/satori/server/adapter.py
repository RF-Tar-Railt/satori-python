from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Optional

from launart import Service

from ..model import Event, Login
from .route import RouterMixin


class Adapter(Service, RouterMixin):
    server_url: str

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

    def ensure_net(self, url: str):
        self.server_url = url
