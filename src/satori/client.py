from __future__ import annotations

import asyncio
import signal
from typing import Any, Awaitable, Callable, Iterable

from launart import Launart, Service, any_completed
from loguru import logger

from .account import Account
from .config import ClientInfo, Config, WebhookInfo
from .model import Event, LoginStatus
from .network.webhook import WebhookNetwork
from .network.ws_client import WsNetwork


class App(Service):
    id = "satori-python.client"
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    accounts: dict[str, Account]
    connections: list[WsNetwork | WebhookNetwork]
    event_callbacks: list[Callable[[Account, Event], Awaitable[Any]]]
    lifecycle_callbacks: list[Callable[[Account, LoginStatus], Awaitable[Any]]]

    def __init__(self, *configs: Config):
        self.accounts = {}
        self.connections = []
        self.event_callbacks = []
        self.lifecycle_callbacks = []
        super().__init__()
        for config in configs:
            self.apply(config)

    def apply(self, config: Config):
        if isinstance(config, ClientInfo):
            connection = WsNetwork(self, config)
        elif isinstance(config, WebhookInfo):
            connection = WebhookNetwork(self, config)
        else:
            raise TypeError(f"Unknown config type: {config}")
        self.connections.append(connection)

    def get_account(self, self_id: str) -> Account:
        return self.accounts[self_id]

    def register(self, callback: Callable[[Account, Event], Awaitable[Any]]):
        self.event_callbacks.append(callback)

    def lifecycle(self, callback: Callable[[Account, LoginStatus], Awaitable[Any]]):
        self.lifecycle_callbacks.append(callback)

    async def account_update(self, account: Account, state: LoginStatus):
        if self.lifecycle_callbacks:
            await asyncio.gather(*(callback(account, state) for callback in self.lifecycle_callbacks))

    async def post(self, event: Event):
        if not self.event_callbacks:
            return
        identity = f"{event.platform}/{event.self_id}"
        if identity not in self.accounts:
            logger.warning(f"Received event for unknown account: {event}")
            return
        account = self.accounts[identity]
        await asyncio.gather(*(callback(account, event) for callback in self.event_callbacks))

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
            for account in self.accounts.values():
                await self.account_update(account, LoginStatus.OFFLINE)
            self.accounts.clear()

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
