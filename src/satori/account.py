import asyncio
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Union, cast

from .element import Element
from .model import Channel, Event, Guild, Login, Member, Message, PageResult, Role, User

if TYPE_CHECKING:
    from .network.base import BaseNetwork


class Account:
    platform: str
    self_id: str

    def __init__(self, platform: str, self_id: str, client: "BaseNetwork"):
        self.platform = platform
        self.self_id = self_id
        self.client = client
        self.connected = asyncio.Event()

    @property
    def identity(self):
        return f"{self.platform}/{self.self_id}"

    def __repr__(self):
        return f"<Account {self.self_id} ({self.platform})>"

    async def send(
        self,
        event: Event,
        message: Union[str, Iterable[Union[str, Element]]],
        **kwargs,
    ) -> List[Message]:
        if not event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.send_message(event.channel.id, message)

    async def send_message(
        self,
        channel_id: str,
        message: Union[str, Iterable[Union[str, Element]]],
    ) -> List[Message]:
        """发送消息

        参数:
            channel_id: 要发送的频道 ID
            message: 要发送的消息
        """
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        return await self.message_create(channel_id=channel_id, content=msg)

    async def send_private_message(
        self,
        user_id: str,
        message: Union[str, Iterable[Union[str, Element]]],
    ) -> List[Message]:
        """发送私聊消息

        参数:
            user_id: 要发送的用户 ID
            message: 要发送的消息
        """
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content="".join(str(i) for i in message))

    async def update_message(
        self,
        channel_id: str,
        message_id: str,
        message: Union[str, Iterable[Union[str, Element]]],
    ):
        """更新消息

        参数:
            channel_id: 要更新的频道 ID
            message_id: 要更新的消息 ID
            message: 要更新的消息
        """
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        await self.message_update(
            channel_id=channel_id,
            message_id=message_id,
            content=msg,
        )

    async def message_create(
        self,
        *,
        channel_id: str,
        content: str,
    ) -> List[Message]:
        res = await self.client.call_http(
            self,
            "message.create",
            {"channel_id": channel_id, "content": content},
        )
        res = cast(List[dict], res)
        return [Message.parse(i) for i in res]

    async def message_get(self, *, channel_id: str, message_id: str) -> Message:
        res = await self.client.call_http(
            self,
            "message.get",
            {"channel_id": channel_id, "message_id": message_id},
        )
        return Message.parse(res)

    async def message_delete(self, *, channel_id: str, message_id: str) -> None:
        await self.client.call_http(
            self,
            "message.delete",
            {"channel_id": channel_id, "message_id": message_id},
        )

    async def message_update(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None:
        await self.client.call_http(
            self,
            "message.update",
            {"channel_id": channel_id, "message_id": message_id, "content": content},
        )

    async def message_list(self, *, channel_id: str, next_token: Optional[str] = None) -> PageResult[Message]:
        res = await self.client.call_http(
            self,
            "message.list",
            {"channel_id": channel_id, "next": next_token},
        )
        return PageResult.parse(res, Message.parse)

    async def channel_get(self, *, channel_id: str) -> Channel:
        res = await self.client.call_http(
            self,
            "channel.get",
            {"channel_id": channel_id},
        )
        return Channel.parse(res)

    async def channel_list(self, *, guild_id: str, next_token: Optional[str] = None) -> PageResult[Channel]:
        res = await self.client.call_http(
            self,
            "channel.list",
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Channel.parse)

    async def channel_create(self, *, guild_id: str, data: Channel) -> Channel:
        res = await self.client.call_http(
            self,
            "channel.create",
            {"guild_id": guild_id, "data": data.dump()},
        )
        return Channel.parse(res)

    async def channel_update(
        self,
        *,
        channel_id: str,
        data: Channel,
    ) -> None:
        await self.client.call_http(
            self,
            "channel.update",
            {"channel_id": channel_id, "data": data.dump()},
        )

    async def channel_delete(self, *, channel_id: str) -> None:
        await self.client.call_http(
            self,
            "channel.delete",
            {"channel_id": channel_id},
        )

    async def user_channel_create(self, *, user_id: str, guild_id: Optional[str] = None) -> Channel:
        data = {"user_id": user_id}
        if guild_id is not None:
            data["guild_id"] = guild_id
        res = await self.client.call_http(
            self,
            "user.channel.create",
            data,
        )
        return Channel.parse(res)

    async def guild_get(self, *, guild_id: str) -> Guild:
        res = await self.client.call_http(
            self,
            "guild.get",
            {"guild_id": guild_id},
        )
        return Guild.parse(res)

    async def guild_list(self, *, next_token: Optional[str] = None) -> PageResult[Guild]:
        res = await self.client.call_http(
            self,
            "guild.list",
            {"next": next_token},
        )
        return PageResult.parse(res, Guild.parse)

    async def guild_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.client.call_http(
            self,
            "guild.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_list(
        self, *, guild_id: str, next_token: Optional[str] = None
    ) -> PageResult[Member]:
        res = await self.client.call_http(
            self,
            "guild.member.list",
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Member.parse)

    async def guild_member_get(self, *, guild_id: str, user_id: str) -> Member:
        res = await self.client.call_http(
            self,
            "guild.member.get",
            {"guild_id": guild_id, "user_id": user_id},
        )
        return Member.parse(res)

    async def guild_member_kick(self, *, guild_id: str, user_id: str, permanent: bool = False) -> None:
        await self.client.call_http(
            self,
            "guild.member.kick",
            {"guild_id": guild_id, "user_id": user_id, "permanent": permanent},
        )

    async def guild_member_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.client.call_http(
            self,
            "guild.member.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_role_set(self, *, guild_id: str, user_id: str, role_id: str) -> None:
        await self.client.call_http(
            self,
            "guild.member.role.set",
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_member_role_unset(self, *, guild_id: str, user_id: str, role_id: str) -> None:
        await self.client.call_http(
            self,
            "guild.member.role.unset",
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_role_list(self, guild_id: str, next_token: Optional[str] = None) -> PageResult[Role]:
        res = await self.client.call_http(
            self,
            "guild.role.list",
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Role.parse)

    async def guild_role_create(
        self,
        *,
        guild_id: str,
        role: Role,
    ) -> Role:
        res = await self.client.call_http(
            self,
            "guild.role.create",
            {"guild_id": guild_id, "role": role.dump()},
        )
        return Role.parse(res)

    async def guild_role_update(
        self,
        *,
        guild_id: str,
        role_id: str,
        role: Role,
    ) -> None:
        await self.client.call_http(
            self,
            "guild.role.update",
            {"guild_id": guild_id, "role_id": role_id, "role": role.dump()},
        )

    async def guild_role_delete(self, *, guild_id: str, role_id: str) -> None:
        await self.client.call_http(
            self,
            "guild.role.delete",
            {"guild_id": guild_id, "role_id": role_id},
        )

    async def reaction_create(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        await self.client.call_http(
            self,
            "reaction.create",
            {"channel_id": channel_id, "message_id": message_id, "emoji": emoji},
        )

    async def reaction_delete(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: Optional[str] = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id, "emoji": emoji}
        if user_id is not None:
            data["user_id"] = user_id
        await self.client.call_http(
            self,
            "reaction.delete",
            data,
        )

    async def reaction_clear(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: Optional[str] = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id}
        if emoji is not None:
            data["emoji"] = emoji
        await self.client.call_http(
            self,
            "reaction.clear",
            data,
        )

    async def reaction_list(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        next_token: Optional[str] = None,
    ) -> PageResult[User]:
        res = await self.client.call_http(
            self,
            "reaction.list",
            {
                "channel_id": channel_id,
                "message_id": message_id,
                "emoji": emoji,
                "next": next_token,
            },
        )
        return PageResult.parse(res, User.parse)

    async def login_get(self) -> Login:
        res = await self.client.call_http(self, "login.get", {})
        return Login.parse(res)

    async def user_get(self, *, user_id: str) -> User:
        res = await self.client.call_http(self, "user.get", {"user_id": user_id})
        return User.parse(res)

    async def friend_list(self, *, next_token: Optional[str] = None) -> PageResult[User]:
        res = await self.client.call_http(self, "friend.list", {"next": next_token})
        return PageResult.parse(res, User.parse)

    async def friend_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.client.call_http(
            self,
            "friend.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def internal(
        self,
        *,
        action: str,
        **kwargs,
    ) -> Any:
        return await self.client.call_http(self, f"internal/{action}", kwargs)
