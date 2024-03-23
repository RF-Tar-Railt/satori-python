from __future__ import annotations

import asyncio
import signal
from functools import wraps
from typing import Any, Awaitable, Callable, Iterable, Literal, TypeVar, overload

from creart import it
from launart import Launart, Service, any_completed
from loguru import logger

from satori import event
from satori.config import Config, WebhookInfo, WebsocketsInfo
from satori.const import EventType
from satori.model import Event, LoginStatus

from .account import Account as Account
from .account import ApiInfo as ApiInfo
from .network.base import BaseNetwork as BaseNetwork
from .network.webhook import WebhookNetwork
from .network.websocket import WsNetwork

TConfig = TypeVar("TConfig", bound=Config)
TE = TypeVar("TE", bound=Event, contravariant=True)

MAPPING: dict[type[Config], type[BaseNetwork]] = {
    WebhookInfo: WebhookNetwork,
    WebsocketsInfo: WsNetwork,
}


class App(Service):
    id = "satori-python.client"
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    accounts: dict[str, Account]
    connections: list[BaseNetwork]
    event_callbacks: list[Callable[[Account, Event], Awaitable[Any]]]
    lifecycle_callbacks: list[Callable[[Account, LoginStatus], Awaitable[Any]]]

    @classmethod
    def register_config(cls, tc: type[TConfig], tn: type[BaseNetwork[TConfig]]):
        MAPPING[tc] = tn

    def __init__(self, *configs: Config):
        self.accounts = {}
        self.connections = []
        self.event_callbacks = []
        self.lifecycle_callbacks = []
        super().__init__()
        for config in configs:
            self.apply(config)

    def apply(self, config: Config):
        try:
            connection = MAPPING[config.__class__](self, config)
        except KeyError:
            raise TypeError(f"Unknown config type: {config}")
        self.connections.append(connection)

    def get_account(self, self_id: str) -> Account:
        return self.accounts[self_id]

    def register(self, callback: Callable[[Account, Event], Awaitable[Any]]):
        self.event_callbacks.append(callback)

    @overload
    def register_on(self, event_type: Literal[EventType.FRIEND_REQUEST]) -> Callable[
        [Callable[[Account, event.UserEvent], Awaitable[Any]]],
        Callable[[Account, event.UserEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[
            EventType.GUILD_ADDED, EventType.GUILD_REMOVED, EventType.GUILD_REQUEST, EventType.GUILD_UPDATED
        ],
    ) -> Callable[
        [Callable[[Account, event.GuildEvent], Awaitable[Any]]],
        Callable[[Account, event.GuildEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[
            EventType.GUILD_MEMBER_ADDED,
            EventType.GUILD_MEMBER_REMOVED,
            EventType.GUILD_MEMBER_UPDATED,
            EventType.GUILD_MEMBER_REQUEST,
        ],
    ) -> Callable[
        [Callable[[Account, event.GuildMemberEvent], Awaitable[Any]]],
        Callable[[Account, event.GuildMemberEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[
            EventType.GUILD_ROLE_CREATED, EventType.GUILD_ROLE_DELETED, EventType.GUILD_ROLE_UPDATED
        ],
    ) -> Callable[
        [Callable[[Account, event.GuildRoleEvent], Awaitable[Any]]],
        Callable[[Account, event.GuildRoleEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self, event_type: Literal[EventType.LOGIN_ADDED, EventType.LOGIN_REMOVED, EventType.LOGIN_UPDATED]
    ) -> Callable[
        [Callable[[Account, event.LoginEvent], Awaitable[Any]]],
        Callable[[Account, event.LoginEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[EventType.MESSAGE_CREATED, EventType.MESSAGE_DELETED, EventType.MESSAGE_UPDATED],
    ) -> Callable[
        [Callable[[Account, event.MessageEvent], Awaitable[Any]]],
        Callable[[Account, event.MessageEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self, event_type: Literal[EventType.REACTION_ADDED, EventType.REACTION_REMOVED]
    ) -> Callable[
        [Callable[[Account, event.ReactionEvent], Awaitable[Any]]],
        Callable[[Account, event.ReactionEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERACTION_BUTTON]) -> Callable[
        [Callable[[Account, event.ButtonInteractionEvent], Awaitable[Any]]],
        Callable[[Account, event.ButtonInteractionEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERACTION_COMMAND]) -> Callable[
        [Callable[[Account, event.ArgvInteractionEvent | event.MessageEvent], Awaitable[Any]]],
        Callable[[Account, event.ArgvInteractionEvent | event.MessageEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERNAL]) -> Callable[
        [Callable[[Account, event.InternalEvent], Awaitable[Any]]],
        Callable[[Account, event.InternalEvent], Awaitable[Any]],
    ]: ...

    def register_on(self, event_type: EventType):
        def decorator(
            func: Callable[[Account, Any], Awaitable[Any]], /
        ) -> Callable[[Account, Any], Awaitable[Any]]:
            @wraps(func)
            async def wrapper(account: Account, event: Event) -> Any:
                if event.type == event_type.value:
                    return await func(account, event)

            self.register(wrapper)
            return wrapper

        return decorator

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
            manager = it(Launart)
        manager.add_component(self)
        manager.launch_blocking(loop=loop, stop_signal=stop_signal)

    async def run_async(self, manager: Launart | None = None):
        if manager is None:
            manager = it(Launart)
        manager.add_component(self)
        await manager.launch()
