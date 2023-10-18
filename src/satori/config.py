from dataclasses import dataclass
from typing import Optional

from yarl import URL


class Config:
    @property
    def token(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def api_base(self) -> URL:
        raise NotImplementedError


@dataclass
class ClientInfo(Config):
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None

    @property
    def identity(self):
        return f"{self.host}:{self.port}#{self.token}"

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}") / "v1"

    @property
    def ws_base(self):
        return URL(f"ws://{self.host}:{self.port}") / "v1"


@dataclass
class WebhookInfo(Config):
    self_host: str = "127.0.0.1"
    self_port: int = 8080
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None

    @property
    def identity(self):
        return f"{self.self_host}:{self.self_port}&&{self.host}:{self.port}"

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}") / "v1"
