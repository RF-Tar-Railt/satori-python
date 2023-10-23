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
class ApiInfo(Config):
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}") / "v1"


@dataclass
class WebsocketsInfo(Config):
    host: str = "localhost"
    port: int = 5140
    token: Optional[str] = None

    @property
    def identity(self):
        return f"{self.host}:{self.port}"

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}") / "v1"

    @property
    def ws_base(self):
        return URL(f"ws://{self.host}:{self.port}") / "v1"


@dataclass
class WebhookInfo(Config):
    path: str = "v1/events"
    host: str = "127.0.0.1"
    port: int = 8080
    token: Optional[str] = None
    server_host: str = "localhost"
    server_port: int = 5140

    def __post_init__(self):
        if self.path and not self.path.startswith("/"):
            self.path = f"/{self.path}"

    @property
    def identity(self):
        return f"{self.host}:{self.port}{self.path}"

    @property
    def api_base(self):
        return URL(f"http://{self.server_host}:{self.server_port}") / "v1"
