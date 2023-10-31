from __future__ import annotations

import asyncio
from dataclasses import dataclass

from yarl import URL

from .session import Session


@dataclass
class ApiInfo:
    host: str = "localhost"
    port: int = 5140
    path: str = ""
    token: str | None = None

    def __post_init__(self):
        if self.path and not self.path.startswith("/"):
            self.path = f"/{self.path}"

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}{self.path}") / "v1"


class Account:
    def __init__(self, platform: str, self_id: str, config: ApiInfo):
        self.platform = platform
        self.self_id = self_id
        self.config = config
        self.session = Session(self)  # type: ignore
        self.connected = asyncio.Event()

    def custom(self, config: ApiInfo | None = None, **kwargs):
        return Account(self.platform, self.self_id, config or ApiInfo(**kwargs)).session

    @property
    def identity(self):
        return f"{self.platform}/{self.self_id}"

    def __repr__(self):
        return f"<Account {self.self_id} ({self.platform})>"

    def __getattr__(self, item):
        return getattr(self.session, item)
