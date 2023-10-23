from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar

from satori.config import Config

if TYPE_CHECKING:
    from satori.client import App

TConfig = TypeVar("TConfig", bound=Config)


class BaseNetwork(Generic[TConfig]):
    close_signal: asyncio.Event
    sequence: int

    def __init__(self, app: App, config: TConfig):
        super().__init__()
        self.app = app
        self.config = config
        self.accounts = {}
        self.close_signal = asyncio.Event()
        self.sequence = -1

    async def wait_for_available(self):
        ...

    @property
    def alive(self) -> bool:
        ...

    async def connection_closed(self):
        self.close_signal.set()
