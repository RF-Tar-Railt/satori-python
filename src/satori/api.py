from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Iterable, List, cast

import aiohttp

from .element import Element
from .exception import (
    ApiNotImplementedException,
    BadRequestException,
    ForbiddenException,
    MethodNotAllowedException,
    NotFoundException,
    UnauthorizedException,
)
from .model import Channel, Event, Guild, Login, Member, Message, PageResult, Role, User

if TYPE_CHECKING:
    from .account import Account


class Session:
    def __init__(self, account: Account):
        self.account = account

    async def call_api(self, action: str, params: dict | None = None) -> dict:
        endpoint = self.account.config.api_base / action
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.account.config.token or ''}",
            "X-Platform": self.account.platform,
            "X-Self-ID": self.account.self_id,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=params or {},
                headers=headers,
            ) as resp:
                if 200 <= resp.status < 300:
                    return json.loads(content) if (content := await resp.text()) else {}
                elif resp.status == 400:
                    raise BadRequestException(await resp.text())
                elif resp.status == 401:
                    raise UnauthorizedException(await resp.text())
                elif resp.status == 403:
                    raise ForbiddenException(await resp.text())
                elif resp.status == 404:
                    raise NotFoundException(await resp.text())
                elif resp.status == 405:
                    raise MethodNotAllowedException(await resp.text())
                elif resp.status == 500:
                    raise ApiNotImplementedException(await resp.text())
                else:
                    resp.raise_for_status()

    async def send(
        self,
        event: Event,
        message: str | Iterable[str | Element],
    ) -> list[Message]:
        if not event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.send_message(event.channel.id, message)

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
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        return await self.message_create(channel_id=channel_id, content=msg)

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
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content="".join(str(i) for i in message))

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
    ) -> list[Message]:
        res = await self.call_api(
            "message.create",
            {"channel_id": channel_id, "content": content},
        )
        res = cast(List[dict], res)
        return [Message.parse(i) for i in res]

    async def message_get(self, *, channel_id: str, message_id: str) -> Message:
        res = await self.call_api(
            "message.get",
            {"channel_id": channel_id, "message_id": message_id},
        )
        return Message.parse(res)

    async def message_delete(self, *, channel_id: str, message_id: str) -> None:
        await self.call_api(
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
        await self.call_api(
            "message.update",
            {"channel_id": channel_id, "message_id": message_id, "content": content},
        )

    async def message_list(self, *, channel_id: str, next_token: str | None = None) -> PageResult[Message]:
        res = await self.call_api(
            "message.list",
            {"channel_id": channel_id, "next": next_token},
        )
        return PageResult.parse(res, Message.parse)

    async def channel_get(self, *, channel_id: str) -> Channel:
        res = await self.call_api(
            "channel.get",
            {"channel_id": channel_id},
        )
        return Channel.parse(res)

    async def channel_list(self, *, guild_id: str, next_token: str | None = None) -> PageResult[Channel]:
        res = await self.call_api(
            "channel.list",
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Channel.parse)

    async def channel_create(self, *, guild_id: str, data: Channel) -> Channel:
        res = await self.call_api(
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
        await self.call_api(
            "channel.update",
            {"channel_id": channel_id, "data": data.dump()},
        )

    async def channel_delete(self, *, channel_id: str) -> None:
        await self.call_api(
            "channel.delete",
            {"channel_id": channel_id},
        )

    async def user_channel_create(self, *, user_id: str, guild_id: str | None = None) -> Channel:
        data = {"user_id": user_id}
        if guild_id is not None:
            data["guild_id"] = guild_id
        res = await self.call_api(
            "user.channel.create",
            data,
        )
        return Channel.parse(res)

    async def guild_get(self, *, guild_id: str) -> Guild:
        res = await self.call_api(
            "guild.get",
            {"guild_id": guild_id},
        )
        return Guild.parse(res)

    async def guild_list(self, *, next_token: str | None = None) -> PageResult[Guild]:
        res = await self.call_api(
            "guild.list",
            {"next": next_token},
        )
        return PageResult.parse(res, Guild.parse)

    async def guild_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            "guild.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_list(self, *, guild_id: str, next_token: str | None = None) -> PageResult[Member]:
        res = await self.call_api(
            "guild.member.list",
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Member.parse)

    async def guild_member_get(self, *, guild_id: str, user_id: str) -> Member:
        res = await self.call_api(
            "guild.member.get",
            {"guild_id": guild_id, "user_id": user_id},
        )
        return Member.parse(res)

    async def guild_member_kick(self, *, guild_id: str, user_id: str, permanent: bool = False) -> None:
        await self.call_api(
            "guild.member.kick",
            {"guild_id": guild_id, "user_id": user_id, "permanent": permanent},
        )

    async def guild_member_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            "guild.member.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_role_set(self, *, guild_id: str, user_id: str, role_id: str) -> None:
        await self.call_api(
            "guild.member.role.set",
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_member_role_unset(self, *, guild_id: str, user_id: str, role_id: str) -> None:
        await self.call_api(
            "guild.member.role.unset",
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_role_list(self, guild_id: str, next_token: str | None = None) -> PageResult[Role]:
        res = await self.call_api(
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
        res = await self.call_api(
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
        await self.call_api(
            "guild.role.update",
            {"guild_id": guild_id, "role_id": role_id, "role": role.dump()},
        )

    async def guild_role_delete(self, *, guild_id: str, role_id: str) -> None:
        await self.call_api(
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
        await self.call_api(
            "reaction.create",
            {"channel_id": channel_id, "message_id": message_id, "emoji": emoji},
        )

    async def reaction_delete(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: str | None = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id, "emoji": emoji}
        if user_id is not None:
            data["user_id"] = user_id
        await self.call_api(
            "reaction.delete",
            data,
        )

    async def reaction_clear(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str | None = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id}
        if emoji is not None:
            data["emoji"] = emoji
        await self.call_api(
            "reaction.clear",
            data,
        )

    async def reaction_list(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]:
        res = await self.call_api(
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
        res = await self.call_api("login.get", {})
        return Login.parse(res)

    async def user_get(self, *, user_id: str) -> User:
        res = await self.call_api("user.get", {"user_id": user_id})
        return User.parse(res)

    async def friend_list(self, *, next_token: str | None = None) -> PageResult[User]:
        res = await self.call_api("friend.list", {"next": next_token})
        return PageResult.parse(res, User.parse)

    async def friend_approve(self, *, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            "friend.approve",
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def internal(
        self,
        *,
        action: str,
        **kwargs,
    ) -> Any:
        return await self.call_api(f"internal/{action}", kwargs)
