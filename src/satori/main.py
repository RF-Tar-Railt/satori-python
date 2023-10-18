from __future__ import annotations

import signal
from typing import Callable, Awaitable, Any, Iterable
from loguru import logger
from launart import Launart, Service, any_completed

from .account import Account
from .model import Event
from .network import Connection
from .config import ClientInfo

import asyncio


class App(Service):
    id = "satori-python.main"
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    accounts: dict[str, Account]
    connections: list[Connection]
    callbacks: list[Callable[[Account, Event], Awaitable[Any]]]

    def __init__(self, *configs: ClientInfo):
        self.accounts = {}
        self.connections = []
        self.callbacks = []
        super().__init__()
        for config in configs:
            self.apply(config)

    def apply(self, config: ClientInfo):
        connection = Connection(self, config)
        self.connections.append(connection)

    def get_account(self, self_id: str) -> Account:
        return self.accounts[self_id]

    def register(self, callback: Callable[[Account, Event], Awaitable[Any]]):
        self.callbacks.append(callback)

    async def post(self, event: Event):
        identity = f"{event.platform}/{event.self_id}"
        if identity not in self.accounts:
            logger.warning(f"Received event for unknown account: {event}")
            return
        account = self.accounts[identity]
        await asyncio.gather(*(callback(account, event) for callback in self.callbacks))

    async def launch(self, manager: Launart):
        for conn in self.connections:
            manager.add_component(conn)

        async with self.stage("preparing"):
            ...

        async with self.stage("blocking"):
            await any_completed(
                manager.status.wait_for_sigexit(),
                *(conn.status.wait_for("blocking-completed") for conn in self.connections),
            )

        async with self.stage("cleanup"):
            pass

    def run(
        self,
        manager: Launart | None = None,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        if manager is None:
            manager = Launart()
        manager.add_component(self)
        manager.launch_blocking(loop=loop, stop_signal=stop_signal)
