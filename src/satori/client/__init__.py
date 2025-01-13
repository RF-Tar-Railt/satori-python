from __future__ import annotations

import asyncio
import functools
import signal
import threading
from collections.abc import Awaitable, Iterable
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar, overload

from creart import it
from graia.amnesia.builtins.aiohttp import AiohttpClientService
from launart import Launart, Service, any_completed
from loguru import logger

from satori import event as events
from satori.const import EventType
from satori.model import Event, LoginStatus

from .account import Account as Account
from .account import ApiInfo as ApiInfo
from .config import Config
from .config import WebhookInfo as WebhookInfo
from .config import WebsocketsInfo as WebsocketsInfo
from .network.base import BaseNetwork as BaseNetwork
from .network.webhook import WebhookNetwork
from .network.websocket import WsNetwork
from .protocol import ApiProtocol as ApiProtocol

TConfig = TypeVar("TConfig", bound=Config)
TE = TypeVar("TE", bound=Event, contravariant=True)

MAPPING: dict[type[Config], type[BaseNetwork]] = {
    WebhookInfo: WebhookNetwork,
    WebsocketsInfo: WsNetwork,
}


class App(Service):
    id = "satori-python.client"
    required: set[str] = {"http.client/aiohttp"}
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    accounts: dict[str, Account]
    connections: list[BaseNetwork]
    event_callbacks: list[Callable[[Account, Event], Awaitable[Any]]]
    lifecycle_callbacks: list[Callable[[Account, LoginStatus], Awaitable[Any]]]

    @classmethod
    def register_config(cls, tc: type[TConfig], tn: type[BaseNetwork[TConfig]]):
        MAPPING[tc] = tn

    def __init__(self, *configs: Config, default_api_cls: type[ApiProtocol] = ApiProtocol):
        self.accounts = {}
        self.connections = []
        self.event_callbacks = []
        self.lifecycle_callbacks = []
        super().__init__()
        for config in configs:
            self.apply(config)
        self.default_api_cls = default_api_cls

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
        [Callable[[Account, events.UserEvent], Awaitable[Any]]],
        Callable[[Account, events.UserEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[
            EventType.GUILD_ADDED, EventType.GUILD_REMOVED, EventType.GUILD_REQUEST, EventType.GUILD_UPDATED
        ],
    ) -> Callable[
        [Callable[[Account, events.GuildEvent], Awaitable[Any]]],
        Callable[[Account, events.GuildEvent], Awaitable[Any]],
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
        [Callable[[Account, events.GuildMemberEvent], Awaitable[Any]]],
        Callable[[Account, events.GuildMemberEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[
            EventType.GUILD_ROLE_CREATED, EventType.GUILD_ROLE_DELETED, EventType.GUILD_ROLE_UPDATED
        ],
    ) -> Callable[
        [Callable[[Account, events.GuildRoleEvent], Awaitable[Any]]],
        Callable[[Account, events.GuildRoleEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self, event_type: Literal[EventType.LOGIN_ADDED, EventType.LOGIN_REMOVED, EventType.LOGIN_UPDATED]
    ) -> Callable[
        [Callable[[Account, events.LoginEvent], Awaitable[Any]]],
        Callable[[Account, events.LoginEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self,
        event_type: Literal[EventType.MESSAGE_CREATED, EventType.MESSAGE_DELETED, EventType.MESSAGE_UPDATED],
    ) -> Callable[
        [Callable[[Account, events.MessageEvent], Awaitable[Any]]],
        Callable[[Account, events.MessageEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self, event_type: Literal[EventType.REACTION_ADDED, EventType.REACTION_REMOVED]
    ) -> Callable[
        [Callable[[Account, events.ReactionEvent], Awaitable[Any]]],
        Callable[[Account, events.ReactionEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERACTION_BUTTON]) -> Callable[
        [Callable[[Account, events.ButtonInteractionEvent], Awaitable[Any]]],
        Callable[[Account, events.ButtonInteractionEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERACTION_COMMAND]) -> Callable[
        [Callable[[Account, events.ArgvInteractionEvent | events.MessageEvent], Awaitable[Any]]],
        Callable[[Account, events.ArgvInteractionEvent | events.MessageEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(self, event_type: Literal[EventType.INTERNAL]) -> Callable[
        [Callable[[Account, events.InternalEvent], Awaitable[Any]]],
        Callable[[Account, events.InternalEvent], Awaitable[Any]],
    ]: ...

    @overload
    def register_on(
        self, event_type: str
    ) -> Callable[
        [Callable[[Account, Event], Awaitable[Any]]], Callable[[Account, Event], Awaitable[Any]]
    ]: ...

    def register_on(self, event_type: str | EventType):
        def decorator(
            func: Callable[[Account, Any], Awaitable[Any]], /
        ) -> Callable[[Account, Any], Awaitable[Any]]:
            @wraps(func)
            async def wrapper(account: Account, event: Event) -> Any:
                if event.type == event_type:
                    return await func(account, event)

            self.register(wrapper)
            return wrapper

        return decorator

    def lifecycle(self, callback: Callable[[Account, LoginStatus], Awaitable[Any]]):
        self.lifecycle_callbacks.append(callback)

    async def account_update(self, account: Account, state: LoginStatus):
        if self.lifecycle_callbacks:
            await asyncio.gather(*(callback(account, state) for callback in self.lifecycle_callbacks))

    async def post(self, event: Event, conn: BaseNetwork):
        if not self.event_callbacks:
            return
        if event.type == EventType.LOGIN_ADDED:
            if TYPE_CHECKING:
                assert isinstance(event, events.LoginEvent)
            login = event.login
            if not login.user:
                logger.warning(f"Received login-added event without user info: {login}")
                return
            login_sn = f"{login.user.id}@{id(conn)}"
            account = Account(
                login,
                conn.config,
                conn.proxy_urls,
                self.default_api_cls,
            )
            logger.info(f"account added: {account}")
            (account.connected.set() if login.status == LoginStatus.ONLINE else account.connected.clear())
            self.accounts[login_sn] = account
            conn.accounts[login_sn] = account
            await self.account_update(account, login.status)
        elif event.type == EventType.LOGIN_UPDATED:
            if TYPE_CHECKING:
                assert isinstance(event, events.LoginEvent)
            login = event.login
            if not login.user:
                logger.warning(f"Received login-updated event without user info: {login}")
                return
            login_sn = f"{login.user.id}@{id(conn)}"
            if login_sn not in self.accounts:
                if login.status == LoginStatus.ONLINE:
                    account = Account(
                        login,
                        conn.config,
                        conn.proxy_urls,
                        self.default_api_cls,
                    )
                    logger.info(f"account added: {account}")
                    account.connected.set()
                    self.accounts[login_sn] = account
                    conn.accounts[login_sn] = account
                    await self.account_update(account, LoginStatus.ONLINE)
                else:
                    logger.warning(f"Received event for unknown account: {event}")
                    return
            else:
                account = self.accounts[login_sn]
                account.self_info = login
            logger.info(f"account updated: {account}")
            (
                account.connected.set()
                if login.status in (LoginStatus.ONLINE, LoginStatus.CONNECT)
                else account.connected.clear()
            )
            await self.account_update(account, login.status)
        elif event.type == EventType.LOGIN_REMOVED:
            if TYPE_CHECKING:
                assert isinstance(event, events.LoginEvent)
            login = event.login
            if not login.user:
                logger.warning(f"Received login-removed event without user info: {login}")
                return
            login_sn = f"{login.user.id}@{id(conn)}"
            if login_sn not in self.accounts:
                logger.warning(f"Received event for unknown account: {event}")
                return
            account = self.accounts[login_sn]
        else:
            login_sn = f"{event.login.user.id}@{id(conn)}"
            if login_sn not in self.accounts:
                logger.warning(f"Received event for unknown account: {event}")
                return
            account = self.accounts[login_sn]

        await asyncio.gather(*(callback(account, event) for callback in self.event_callbacks))

        if event.type == EventType.LOGIN_REMOVED:
            logger.info(f"account removed: {account}")
            account.connected.clear()
            await self.account_update(account, LoginStatus.OFFLINE)
            del self.accounts[login_sn]
            del conn.accounts[login_sn]

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
        manager.add_component(AiohttpClientService())
        manager.add_component(self)
        manager.launch_blocking(loop=loop, stop_signal=stop_signal)

    async def run_async(
        self,
        manager: Launart | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        if manager is None:
            manager = it(Launart)
        manager.add_component(AiohttpClientService())
        manager.add_component(self)
        handled_signals: dict[signal.Signals, Any] = {}
        launch_task = asyncio.create_task(manager.launch(), name="amnesia-launch")
        signal_handler = functools.partial(manager._on_sys_signal, main_task=launch_task)
        if threading.current_thread() is threading.main_thread():  # pragma: worst case
            try:
                for sig in stop_signal:
                    handled_signals[sig] = signal.getsignal(sig)
                    signal.signal(sig, signal_handler)
            except ValueError:  # pragma: no cover
                # `signal.signal` may throw if `threading.main_thread` does
                # not support signals
                handled_signals.clear()
        await launch_task
        for sig, handler in handled_signals.items():
            if signal.getsignal(sig) is signal_handler:
                signal.signal(sig, handler)
