import asyncio
from typing import Any, Iterable, overload

from .api import Session
from .config import ApiInfo, Config
from .element import Element
from .model import Channel, Event, Guild, Login, Member, Message, PageResult, Role, User

class Account:
    platform: str
    self_id: str
    config: Config
    session: Session
    connected: asyncio.Event

    def __init__(self, platform: str, self_id: str, config: Config): ...
    @property
    def identity(self) -> str: ...
    @overload
    def custom(self, config: ApiInfo) -> Session: ...
    @overload
    def custom(self, *, host: str, port: int, token: str | None = None) -> Session: ...
    async def send(
        self,
        event: Event,
        message: str | Iterable[str | Element],
        **kwargs,
    ) -> list[Message]: ...
    async def send_message(
        self,
        channel_id: str,
        message: str | Iterable[str | Element],
    ) -> list[Message]:
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
    ) -> list[Message]:
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
    ) -> list[Message]: ...
    async def message_get(self, *, channel_id: str, message_id: str) -> Message: ...
    async def message_delete(self, *, channel_id: str, message_id: str) -> None: ...
    async def message_update(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None: ...
    async def message_list(
        self, *, channel_id: str, next_token: str | None = None
    ) -> PageResult[Message]: ...
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
    async def user_channel_create(self, *, user_id: str, guild_id: str | None = None) -> Channel: ...
    async def guild_get(self, *, guild_id: str) -> Guild: ...
    async def guild_list(self, *, next_token: str | None = None) -> PageResult[Guild]: ...
    async def guild_approve(self, *, request_id: str, approve: bool, comment: str) -> None: ...
    async def guild_member_list(
        self, *, guild_id: str, next_token: str | None = None
    ) -> PageResult[Member]: ...
    async def guild_member_get(self, *, guild_id: str, user_id: str) -> Member: ...
    async def guild_member_kick(self, *, guild_id: str, user_id: str, permanent: bool = False) -> None: ...
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
