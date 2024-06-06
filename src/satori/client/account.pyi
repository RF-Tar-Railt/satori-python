import asyncio
from typing import Any, Iterable, Protocol, TypeVar, overload

from yarl import URL

from satori.element import Element
from satori.model import (
    Channel,
    Direction,
    Event,
    Guild,
    Login,
    Member,
    MessageObject,
    Order,
    PageDequeResult,
    PageResult,
    Role,
    Upload,
    User,
)

from .protocol import Protocol

TS = TypeVar("TS", bound="Session")

class Api(Protocol):
    token: str | None = None

    @property
    def api_base(self) -> URL: ...

class ApiInfo(Api):
    def __init__(
        self, host: str = "localhost", port: int = 5140, path: str = "", token: str | None = None
    ): ...

class Account:
    platform: str
    self_id: str
    self_info: Login
    config: Api
    session: Protocol
    connected: asyncio.Event

    def __init__(
        self, platform: str, self_id: str, self_info: Login, config: Api, session_cls: type[Protocol] = Protocol
    ): ...
    @property
    def identity(self) -> str: ...
    @overload
    def custom(self, config: Api, session_cls: type[TS] = Protocol) -> TS: ...
    @overload
    def custom(
        self, *, session_cls: type[TS] = Protocol, host: str, port: int, token: str | None = None
    ) -> TS: ...
    async def send(
        self,
        event: Event,
        message: str | Iterable[str | Element],
        **kwargs,
    ) -> list[MessageObject]: ...
    async def send_message(
        self,
        channel_id: str,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送消息

        参数:
            channel_id: 要发送的频道 ID
            message: 要发送的消息
        """
        ...

    async def send_private_message(
        self,
        user_id: str,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送私聊消息

        参数:
            user_id: 要发送的用户 ID
            message: 要发送的消息
        """
        ...

    async def update_message(
        self,
        channel_id: str,
        message_id: str,
        message: str | Iterable[str | Element],
    ):
        """更新消息

        参数:
            channel_id: 要更新的频道 ID
            message_id: 要更新的消息 ID
            message: 要更新的消息
        """
        ...

    async def message_create(
        self,
        *,
        channel_id: str,
        content: str,
    ) -> list[MessageObject]: ...
    async def message_get(self, *, channel_id: str, message_id: str) -> MessageObject: ...
    async def message_delete(self, *, channel_id: str, message_id: str) -> None: ...
    async def message_update(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None: ...
    async def message_list(
        self,
        channel_id: str,
        next_token: str | None = None,
        direction: Direction = "before",
        limit: int = 50,
        order: Order = "asc",
    ) -> PageDequeResult[MessageObject]: ...
    async def channel_get(self, *, channel_id: str) -> Channel: ...
    async def channel_list(self, *, guild_id: str, next_token: str | None = None) -> PageResult[Channel]: ...
    async def channel_create(self, *, guild_id: str, data: Channel) -> Channel: ...
    async def channel_update(
        self,
        *,
        channel_id: str,
        data: Channel,
    ) -> None: ...
    async def channel_delete(self, *, channel_id: str) -> None: ...
    async def channel_mute(self, *, channel_id: str, duration: float = 0) -> None: ...
    async def user_channel_create(self, *, user_id: str, guild_id: str | None = None) -> Channel: ...
    async def guild_get(self, *, guild_id: str) -> Guild: ...
    async def guild_list(self, *, next_token: str | None = None) -> PageResult[Guild]: ...
    async def guild_approve(self, *, request_id: str, approve: bool, comment: str) -> None: ...
    async def guild_member_list(
        self, *, guild_id: str, next_token: str | None = None
    ) -> PageResult[Member]: ...
    async def guild_member_get(self, *, guild_id: str, user_id: str) -> Member: ...
    async def guild_member_kick(self, *, guild_id: str, user_id: str, permanent: bool = False) -> None: ...
    async def guild_member_mute(self, *, guild_id: str, user_id: str, duration: float = 0) -> None: ...
    async def guild_member_approve(self, *, request_id: str, approve: bool, comment: str) -> None: ...
    async def guild_member_role_set(self, *, guild_id: str, user_id: str, role_id: str) -> None: ...
    async def guild_member_role_unset(self, *, guild_id: str, user_id: str, role_id: str) -> None: ...
    async def guild_role_list(self, guild_id: str, next_token: str | None = None) -> PageResult[Role]: ...
    async def guild_role_create(
        self,
        *,
        guild_id: str,
        role: Role,
    ) -> Role: ...
    async def guild_role_update(
        self,
        *,
        guild_id: str,
        role_id: str,
        role: Role,
    ) -> None: ...
    async def guild_role_delete(self, *, guild_id: str, role_id: str) -> None: ...
    async def reaction_create(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None: ...
    async def reaction_delete(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: str | None = None,
    ) -> None: ...
    async def reaction_clear(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str | None = None,
    ) -> None: ...
    async def reaction_list(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]: ...
    async def login_get(self) -> Login: ...
    async def user_get(self, *, user_id: str) -> User: ...
    async def friend_list(self, *, next_token: str | None = None) -> PageResult[User]: ...
    async def friend_approve(self, *, request_id: str, approve: bool, comment: str) -> None: ...
    async def internal(
        self,
        *,
        action: str,
        **kwargs,
    ) -> Any: ...
    async def admin_login_list(self) -> list[Login]: ...
    @overload
    async def upload_create(self, *uploads: Upload) -> list[str]: ...
    @overload
    async def upload_create(self, **uploads: Upload) -> dict[str, str]: ...

    upload = upload_create
