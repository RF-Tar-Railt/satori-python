from typing import Optional
from dataclasses import dataclass

from yarl import URL


@dataclass
class ClientInfo:
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
