from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar

from launart import Service
from loguru import logger

from satori.config import Config as Config
from satori.model import Event

if TYPE_CHECKING:
    from .. import App

TConfig = TypeVar("TConfig", bound=Config)


class BaseNetwork(Generic[TConfig], Service):
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

    def post_event(self, body: dict):
        async def event_parse_task(raw: dict):
            try:
                event = Event.parse(raw)
            except Exception as e:
                logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")
            else:
                self.sequence = event.id
                await self.app.post(event)

        return asyncio.create_task(event_parse_task(body))
