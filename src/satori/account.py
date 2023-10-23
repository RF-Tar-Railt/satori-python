from __future__ import annotations

import asyncio

from .api import Session
from .config import ApiInfo, Config


class Account:
    def __init__(self, platform: str, self_id: str, config: Config):
        self.platform = platform
        self.self_id = self_id
        self.config = config
        self.session = Session(self)
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
