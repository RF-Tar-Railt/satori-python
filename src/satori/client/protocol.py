from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, cast, overload

from aiohttp import FormData
from graia.amnesia.builtins.aiohttp import AiohttpClientService
from launart import Launart

from satori.const import Api
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

from .network.util import validate_response

if TYPE_CHECKING:
    from .account import Account


class ApiProtocol:
    def __init__(self, account: Account):
        self.account = account

    async def download(self, url: str):
        endpoint = self.account.config.api_base / "proxy" / url.lstrip("/")
        aio = Launart.current().get_component(AiohttpClientService)
        async with aio.session.get(endpoint) as resp:
            await validate_response(resp, noreturn=True)
            return await resp.read()

    async def call_api(self, action: str | Api, params: dict | None = None, multipart: bool = False) -> dict:
        endpoint = self.account.config.api_base / (action.value if isinstance(action, Api) else action)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.account.config.token or ''}",
            "X-Platform": self.account.platform,
            "X-Self-ID": self.account.self_id,
        }
        aio = Launart.current().get_component(AiohttpClientService)
        if multipart:
            data = FormData(quote_fields=False)
            if params is None:
                raise TypeError("multipart requires params")
            headers.pop("Content-Type")
            for k, v in params.items():
                if isinstance(v, dict):
                    data.add_field(k, v["value"], filename=v.get("filename"), content_type=v["content_type"])
                else:
                    data.add_field(k, v)
            async with aio.session.post(
                endpoint,
                data=data,
                headers=headers,
            ) as resp:
                return await validate_response(resp)
        async with aio.session.post(
            endpoint,
            json=params or {},
            headers=headers,
        ) as resp:
            return await validate_response(resp)

    async def send(
        self,
        event: Event,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        if not event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.send_message(event.channel.id, message)

    async def send_message(
        self,
        channel: str | Channel,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送消息

        参数:
            channel_id: 要发送的频道 ID
            message: 要发送的消息
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        return await self.message_create(channel_id=channel_id, content=msg)

    async def send_private_message(
        self,
        user: str | User,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送私聊消息

        参数:
            user_id: 要发送的用户 ID
            message: 要发送的消息
        """
        user_id = user.id if isinstance(user, User) else user
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content="".join(str(i) for i in message))

    async def update_message(
        self,
        channel: str | Channel,
        message_id: str,
        message: str | Iterable[str | Element],
    ):
        """更新消息

        参数:
            channel_id: 要更新的频道 ID
            message_id: 要更新的消息 ID
            message: 要更新的消息
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        await self.message_update(
            channel_id=channel_id,
            message_id=message_id,
            content=msg,
        )

    async def message_create(
        self,
        channel_id: str,
        content: str,
    ) -> list[MessageObject]:
        res = await self.call_api(
            Api.MESSAGE_CREATE,
            {"channel_id": channel_id, "content": content},
        )
        res = cast("list[dict]", res)
        return [MessageObject.parse(i) for i in res]

    async def message_get(self, channel_id: str, message_id: str) -> MessageObject:
        res = await self.call_api(
            Api.MESSAGE_GET,
            {"channel_id": channel_id, "message_id": message_id},
        )
        return MessageObject.parse(res)

    async def message_delete(self, channel_id: str, message_id: str) -> None:
        await self.call_api(
            Api.MESSAGE_DELETE,
            {"channel_id": channel_id, "message_id": message_id},
        )

    async def message_update(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None:
        await self.call_api(
            Api.MESSAGE_UPDATE,
            {"channel_id": channel_id, "message_id": message_id, "content": content},
        )

    async def message_list(
        self,
        channel_id: str,
        next_token: str | None = None,
        direction: Direction = "before",
        limit: int = 50,
        order: Order = "asc",
    ) -> PageDequeResult[MessageObject]:
        if not next_token and direction != "before":
            raise ValueError("Invalid direction")
        res = await self.call_api(
            Api.MESSAGE_LIST,
            {
                "channel_id": channel_id,
                "next": next_token,
                "direction": direction,
                "limit": limit,
                "order": order,
            },
        )
        return PageDequeResult.parse(res, MessageObject.parse)

    async def channel_get(self, channel_id: str) -> Channel:
        res = await self.call_api(
            Api.CHANNEL_GET,
            {"channel_id": channel_id},
        )
        return Channel.parse(res)

    async def channel_list(self, guild_id: str, next_token: str | None = None) -> PageResult[Channel]:
        res = await self.call_api(
            Api.CHANNEL_LIST,
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Channel.parse)

    async def channel_create(self, guild_id: str, data: Channel) -> Channel:
        res = await self.call_api(
            Api.CHANNEL_CREATE,
            {"guild_id": guild_id, "data": data.dump()},
        )
        return Channel.parse(res)

    async def channel_update(
        self,
        channel_id: str,
        data: Channel,
    ) -> None:
        await self.call_api(
            Api.CHANNEL_UPDATE,
            {"channel_id": channel_id, "data": data.dump()},
        )

    async def channel_delete(self, channel_id: str) -> None:
        await self.call_api(
            Api.CHANNEL_DELETE,
            {"channel_id": channel_id},
        )

    async def channel_mute(self, channel_id: str, duration: float = 0) -> None:
        await self.call_api(
            Api.CHANNEL_MUTE,
            {"channel_id": channel_id, "duration": duration},
        )

    async def user_channel_create(self, user_id: str, guild_id: str | None = None) -> Channel:
        data = {"user_id": user_id}
        if guild_id is not None:
            data["guild_id"] = guild_id
        res = await self.call_api(
            Api.USER_CHANNEL_CREATE,
            data,
        )
        return Channel.parse(res)

    async def guild_get(self, guild_id: str) -> Guild:
        res = await self.call_api(
            Api.GUILD_GET,
            {"guild_id": guild_id},
        )
        return Guild.parse(res)

    async def guild_list(self, next_token: str | None = None) -> PageResult[Guild]:
        res = await self.call_api(
            Api.GUILD_LIST,
            {"next": next_token},
        )
        return PageResult.parse(res, Guild.parse)

    async def guild_approve(self, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            Api.GUILD_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_list(self, guild_id: str, next_token: str | None = None) -> PageResult[Member]:
        res = await self.call_api(
            Api.GUILD_MEMBER_LIST,
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Member.parse)

    async def guild_member_get(self, guild_id: str, user_id: str) -> Member:
        res = await self.call_api(
            Api.GUILD_MEMBER_GET,
            {"guild_id": guild_id, "user_id": user_id},
        )
        return Member.parse(res)

    async def guild_member_kick(self, guild_id: str, user_id: str, permanent: bool = False) -> None:
        await self.call_api(
            Api.GUILD_MEMBER_KICK,
            {"guild_id": guild_id, "user_id": user_id, "permanent": permanent},
        )

    async def guild_member_mute(self, guild_id: str, user_id: str, duration: float = 0) -> None:
        await self.call_api(
            Api.GUILD_MEMBER_MUTE,
            {"guild_id": guild_id, "user_id": user_id, "duration": duration},
        )

    async def guild_member_approve(self, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            Api.GUILD_MEMBER_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_role_set(self, guild_id: str, user_id: str, role_id: str) -> None:
        await self.call_api(
            Api.GUILD_MEMBER_ROLE_SET,
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_member_role_unset(self, guild_id: str, user_id: str, role_id: str) -> None:
        await self.call_api(
            Api.GUILD_MEMBER_ROLE_UNSET,
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_role_list(self, guild_id: str, next_token: str | None = None) -> PageResult[Role]:
        res = await self.call_api(
            Api.GUILD_ROLE_LIST,
            {"guild_id": guild_id, "next": next_token},
        )
        return PageResult.parse(res, Role.parse)

    async def guild_role_create(
        self,
        guild_id: str,
        role: Role,
    ) -> Role:
        res = await self.call_api(
            Api.GUILD_ROLE_CREATE,
            {"guild_id": guild_id, "role": role.dump()},
        )
        return Role.parse(res)

    async def guild_role_update(
        self,
        guild_id: str,
        role_id: str,
        role: Role,
    ) -> None:
        await self.call_api(
            Api.GUILD_ROLE_UPDATE,
            {"guild_id": guild_id, "role_id": role_id, "role": role.dump()},
        )

    async def guild_role_delete(self, guild_id: str, role_id: str) -> None:
        await self.call_api(
            Api.GUILD_ROLE_DELETE,
            {"guild_id": guild_id, "role_id": role_id},
        )

    async def reaction_create(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        await self.call_api(
            Api.REACTION_CREATE,
            {"channel_id": channel_id, "message_id": message_id, "emoji": emoji},
        )

    async def reaction_delete(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: str | None = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id, "emoji": emoji}
        if user_id is not None:
            data["user_id"] = user_id
        await self.call_api(
            Api.REACTION_DELETE,
            data,
        )

    async def reaction_clear(
        self,
        channel_id: str,
        message_id: str,
        emoji: str | None = None,
    ) -> None:
        data = {"channel_id": channel_id, "message_id": message_id}
        if emoji is not None:
            data["emoji"] = emoji
        await self.call_api(
            Api.REACTION_CLEAR,
            data,
        )

    async def reaction_list(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]:
        res = await self.call_api(
            Api.REACTION_LIST,
            {
                "channel_id": channel_id,
                "message_id": message_id,
                "emoji": emoji,
                "next": next_token,
            },
        )
        return PageResult.parse(res, User.parse)

    async def login_get(self) -> Login:
        res = await self.call_api(Api.LOGIN_GET, {})
        return Login.parse(res)

    async def user_get(self, user_id: str) -> User:
        res = await self.call_api(Api.USER_GET, {"user_id": user_id})
        return User.parse(res)

    async def friend_list(self, next_token: str | None = None) -> PageResult[User]:
        res = await self.call_api(Api.FRIEND_LIST, {"next": next_token})
        return PageResult.parse(res, User.parse)

    async def friend_approve(self, request_id: str, approve: bool, comment: str) -> None:
        await self.call_api(
            Api.FRIEND_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def internal(
        self,
        action: str,
        **kwargs,
    ) -> Any:
        return await self.call_api(f"internal/{action}", kwargs)

    async def admin_login_list(self) -> list[Login]:
        res = await self.call_api("admin/login.list")
        return [Login.parse(i) for i in res]

    @overload
    async def upload_create(self, *uploads: Upload) -> list[str]: ...

    @overload
    async def upload_create(self, **uploads: Upload) -> dict[str, str]: ...

    async def upload_create(self, *args: Upload, **kwargs: Upload):
        if args and kwargs:
            raise RuntimeError("upload can't accept both args and kwargs")
        if args:
            ids = []
            for upload in args:
                ids.append(str(id(upload)))
            resp = await self.call_api(
                Api.UPLOAD_CREATE, {name: upload.dump() for name, upload in zip(ids, args)}, multipart=True
            )
            return list(resp.values())
        return await self.call_api(
            Api.UPLOAD_CREATE, {k: upload.dump() for k, upload in kwargs.items()}, multipart=True
        )

    upload = upload_create
