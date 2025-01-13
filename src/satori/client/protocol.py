from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast, overload
from typing_extensions import deprecated

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
    IterablePageResult,
    Login,
    LoginPartial,
    Member,
    MessageObject,
    MessageReceipt,
    Meta,
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
        """访问资源链接。"""
        endpoint = self.account.ensure_url(url)
        aio = Launart.current().get_component(AiohttpClientService)
        async with aio.session.get(endpoint) as resp:
            await validate_response(resp, noreturn=True)
            return await resp.read()

    async def request_internal(self, url: str, method: str = "GET", **kwargs) -> dict:
        """访问内部链接。"""
        endpoint = self.account.ensure_url(url)
        aio = Launart.current().get_component(AiohttpClientService)
        async with aio.session.request(method, endpoint, **kwargs) as resp:
            return await validate_response(resp)

    async def call_api(
        self, action: str | Api, params: dict | None = None, multipart: bool = False, method: str = "POST"
    ) -> dict:
        endpoint = self.account.config.api_base / (action.value if isinstance(action, Api) else action)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.account.config.token or ''}",
            "X-Platform": self.account.platform,
            "X-Self-ID": self.account.self_id,
            "Satori-Platform": self.account.platform,
            "Satori-User-ID": self.account.self_id,
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
        async with aio.session.request(
            method,
            endpoint,
            json=params or {},
            headers=headers,
        ) as resp:
            return await validate_response(resp)

    async def send(self, event: Event, message: str | Iterable[str | Element]) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            event (Event): 当前事件(上下文)
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组

        Raises:
            RuntimeError: 传入的事件缺少 `channel` 对象
        """
        if not event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.send_message(event.channel.id, message)

    async def send_message(
        self, channel: str | Channel, message: str | Iterable[str | Element]
    ) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel (str | Channel): 要发送的频道 ID
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        return await self.message_create(channel_id=channel_id, content=msg)

    async def send_private_message(
        self, user: str | User, message: str | Iterable[str | Element]
    ) -> list[MessageReceipt]:
        """发送私聊消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            user (str | User): 要发送的用户 ID
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        user_id = user.id if isinstance(user, User) else user
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content="".join(str(i) for i in message))

    async def update_message(
        self, channel: str | Channel, message_id: str, message: str | Iterable[str | Element]
    ) -> None:
        """更新消息。

        Args:
            channel (str | Channel): 要更新的频道 ID
            message_id (str): 要更新的消息 ID
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            None: 该方法无返回值
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        msg = message if isinstance(message, str) else "".join(str(i) for i in message)
        await self.message_update(
            channel_id=channel_id,
            message_id=message_id,
            content=msg,
        )

    async def message_create(self, channel_id: str, content: str) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel_id (str): 频道 ID
            content (str): 消息内容

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        res = await self.call_api(
            Api.MESSAGE_CREATE,
            {"channel_id": channel_id, "content": content},
        )
        res = cast("list[dict]", res)
        return [MessageReceipt.parse(i) for i in res]

    async def message_get(self, channel_id: str, message_id: str) -> MessageObject:
        """获取特定消息。返回一个 `MessageObject` 对象。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID

        Returns:
            MessageObject: `MessageObject` 对象
        """
        res = await self.call_api(
            Api.MESSAGE_GET,
            {"channel_id": channel_id, "message_id": message_id},
        )
        return MessageObject.parse(res)

    async def message_delete(self, channel_id: str, message_id: str) -> None:
        """撤回特定消息。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.MESSAGE_DELETE,
            {"channel_id": channel_id, "message_id": message_id},
        )

    async def message_update(self, channel_id: str, message_id: str, content: str) -> None:
        """编辑特定消息。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            content (str): 消息内容

        Returns:
            None: 该方法无返回值
        """
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
        """获取频道消息列表。返回一个 `MessageObject` 的 双向分页列表。

        Args:
            channel_id (str): 频道 ID
            next_token (str | None, optional): 分页令牌，默认为空，\
                表示从最新消息开始查询。此时 direction 参数只能为 before
            direction (Literal["before", "after", "around"], optional): 查询方向，默认为 before
            limit (int, optional): 消息数量限制。\
                开发者应当使用返回值中 prev 或 next 的存在性判断是否有更多数据，而非依赖于返回值中 data 的长度
            order (Literal["asc", "desc"], optional): 对结果排序，默认为 asc (无论查询方向)

        Returns:
            PageDequeResult[MessageObject]: `MessageObject` 的 双向分页列表

        Raises:
            ValueError: 当分页令牌为空且 direction 参数不为 before 时
        """
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
        """根据 ID 获取频道。返回一个 `Channel` 对象。

        Args:
            channel_id (str): 频道 ID

        Returns:
            Channel: `Channel` 对象
        """
        res = await self.call_api(
            Api.CHANNEL_GET,
            {"channel_id": channel_id},
        )
        return Channel.parse(res)

    def channel_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Channel]:
        """获取群组中的全部频道。返回一个 Channel 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Channel]: `Channel` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(
                Api.CHANNEL_LIST,
                {"guild_id": guild_id, "next": token},
            )
            return PageResult.parse(res, Channel.parse)

        return IterablePageResult(_, next_token)

    async def channel_create(self, guild_id: str, data: Channel) -> Channel:
        """创建群组频道。返回一个 Channel 对象。

        Args:
            guild_id (str): 群组 ID
            data (Channel): 频道数据

        Returns:
            Channel: `Channel` 对象
        """
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
        """修改群组频道。

        Args:
            channel_id (str): 频道 ID
            data (Channel): 频道数据

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.CHANNEL_UPDATE,
            {"channel_id": channel_id, "data": data.dump()},
        )

    async def channel_delete(self, channel_id: str) -> None:
        """删除群组频道。

        Args:
            channel_id (str): 频道 ID

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.CHANNEL_DELETE,
            {"channel_id": channel_id},
        )

    async def channel_mute(self, channel_id: str, duration: float = 60) -> None:
        """禁言群组频道。

        如果传入的禁言时长为 0 则表示解除禁言。

        Args:
            channel_id (str): 频道 ID
            duration (float, optional): 禁言时长 (秒)，默认为 60 秒
        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.CHANNEL_MUTE,
            {"channel_id": channel_id, "duration": 1000 * duration},
        )

    async def user_channel_create(self, user_id: str, guild_id: str | None = None) -> Channel:
        """创建一个私聊频道。返回一个 Channel 对象。

        Args:
            user_id (str): 用户 ID
            guild_id (str | None, optional): 群组 ID

        Returns:
            Channel: `Channel` 对象
        """
        data = {"user_id": user_id}
        if guild_id is not None:
            data["guild_id"] = guild_id
        res = await self.call_api(
            Api.USER_CHANNEL_CREATE,
            data,
        )
        return Channel.parse(res)

    async def guild_get(self, guild_id: str) -> Guild:
        """根据 ID 获取群组。返回一个 `Guild` 对象。

        Args:
            guild_id (str): 群组 ID

        Returns:
            Guild: `Guild` 对象
        """
        res = await self.call_api(
            Api.GUILD_GET,
            {"guild_id": guild_id},
        )
        return Guild.parse(res)

    def guild_list(self, next_token: str | None = None) -> IterablePageResult[Guild]:
        """获取当前用户加入的全部群组。返回一个 Guild 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Guild]: `Guild` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(
                Api.GUILD_LIST,
                {"next": token},
            )
            return PageResult.parse(res, Guild.parse)

        return IterablePageResult(_, next_token)

    async def guild_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理来自群组的邀请。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    def guild_member_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Member]:
        """获取群组成员列表。返回一个 Member 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Member]: `Member` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(
                Api.GUILD_MEMBER_LIST,
                {"guild_id": guild_id, "next": token},
            )
            return PageResult.parse(res, Member.parse)

        return IterablePageResult(_, next_token)

    async def guild_member_get(self, guild_id: str, user_id: str) -> Member:
        """获取群成员信息。返回一个 `Member` 对象。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID

        Returns:
            Member: `Member` 对象
        """
        res = await self.call_api(
            Api.GUILD_MEMBER_GET,
            {"guild_id": guild_id, "user_id": user_id},
        )
        return Member.parse(res)

    async def guild_member_kick(self, guild_id: str, user_id: str, permanent: bool = False) -> None:
        """将某个用户踢出群组。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            permanent (bool, optional): 是否永久踢出 (无法再次加入群组)，默认为 False

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_MEMBER_KICK,
            {"guild_id": guild_id, "user_id": user_id, "permanent": permanent},
        )

    async def guild_member_mute(self, guild_id: str, user_id: str, duration: float = 60) -> None:
        """禁言群组成员。

        如果传入的禁言时长为 0 则表示解除禁言。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            duration (float, optional): 禁言时长 (秒)，默认为 60 秒

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_MEMBER_MUTE,
            {"guild_id": guild_id, "user_id": user_id, "duration": 1000 * duration},
        )

    async def guild_member_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理来自群组的加群请求。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_MEMBER_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def guild_member_role_set(self, guild_id: str, user_id: str, role_id: str) -> None:
        """设置群组内用户的角色。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_MEMBER_ROLE_SET,
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    async def guild_member_role_unset(self, guild_id: str, user_id: str, role_id: str) -> None:
        """取消群组内用户的角色。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_MEMBER_ROLE_UNSET,
            {"guild_id": guild_id, "user_id": user_id, "role_id": role_id},
        )

    def guild_role_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Role]:
        """获取群组角色列表。返回一个 Role 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Role]: `Role` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(
                Api.GUILD_ROLE_LIST,
                {"guild_id": guild_id, "next": token},
            )
            return PageResult.parse(res, Role.parse)

        return IterablePageResult(_, next_token)

    async def guild_role_create(self, guild_id: str, role: Role) -> Role:
        """创建群组角色。返回一个 Role 对象。

        Args:
            guild_id (str): 群组 ID
            role (Role): 角色数据

        Returns:
            Role: `Role` 对象
        """
        res = await self.call_api(
            Api.GUILD_ROLE_CREATE,
            {"guild_id": guild_id, "role": role.dump()},
        )
        return Role.parse(res)

    async def guild_role_update(self, guild_id: str, role_id: str, role: Role) -> None:
        """修改群组角色。

        Args:
            guild_id (str): 群组 ID
            role_id (str): 角色 ID
            role (Role): 角色数据

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_ROLE_UPDATE,
            {"guild_id": guild_id, "role_id": role_id, "role": role.dump()},
        )

    async def guild_role_delete(self, guild_id: str, role_id: str) -> None:
        """删除群组角色。

        Args:
            guild_id (str): 群组 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.GUILD_ROLE_DELETE,
            {"guild_id": guild_id, "role_id": role_id},
        )

    async def reaction_create(self, channel_id: str, message_id: str, emoji: str) -> None:
        """向特定消息添加表态。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            emoji (str): 表态名称

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.REACTION_CREATE,
            {"channel_id": channel_id, "message_id": message_id, "emoji": emoji},
        )

    async def reaction_delete(
        self, channel_id: str, message_id: str, emoji: str, user_id: str | None = None
    ) -> None:
        """从特定消息删除某个用户添加的特定表态。

        如果没有传入用户 ID 则表示删除自己的表态。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            emoji (str): 表态名称
            user_id (str | None, optional): 用户 ID，默认为 None

        Returns:
            None: 该方法无返回值
        """
        data = {"channel_id": channel_id, "message_id": message_id, "emoji": emoji}
        if user_id is not None:
            data["user_id"] = user_id
        await self.call_api(
            Api.REACTION_DELETE,
            data,
        )

    async def reaction_clear(self, channel_id: str, message_id: str, emoji: str | None = None) -> None:
        """从特定消息清除某个特定表态。

        如果没有传入表态名称则表示清除所有表态。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            emoji (str | None, optional): 表态名称，默认为 None

        Returns:
            None: 该方法无返回值
        """
        data = {"channel_id": channel_id, "message_id": message_id}
        if emoji is not None:
            data["emoji"] = emoji
        await self.call_api(
            Api.REACTION_CLEAR,
            data,
        )

    def reaction_list(
        self, channel_id: str, message_id: str, emoji: str, next_token: str | None = None
    ) -> IterablePageResult[User]:
        """获取添加特定消息的特定表态的用户列表。返回一个 User 的分页列表。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            emoji (str): 表态名称
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[User]: `User` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(
                Api.REACTION_LIST,
                {
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "emoji": emoji,
                    "next": token,
                },
            )
            return PageResult.parse(res, User.parse)

        return IterablePageResult(_, next_token)

    async def login_get(self) -> Login:
        """获取当前登录信息。返回一个 `Login` 对象。

        Returns:
            Login: `Login` 对象
        """
        res = await self.call_api(Api.LOGIN_GET, {})
        return Login.parse(res)

    async def user_get(self, user_id: str) -> User:
        """获取用户信息。返回一个 `User` 对象。

        Args:
            user_id (str): 用户 ID

        Returns:
            User: `User` 对象
        """
        res = await self.call_api(Api.USER_GET, {"user_id": user_id})
        return User.parse(res)

    def friend_list(self, next_token: str | None = None) -> IterablePageResult[User]:
        """获取好友列表。返回一个 User 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[User]: `User` 的分页列表
        """

        async def _(token: str | None):
            res = await self.call_api(Api.FRIEND_LIST, {"next": token})
            return PageResult.parse(res, User.parse)

        return IterablePageResult(_, next_token)

    async def friend_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理好友申请。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        await self.call_api(
            Api.FRIEND_APPROVE,
            {"message_id": request_id, "approve": approve, "comment": comment},
        )

    async def internal(self, action: str, method: str = "POST", **kwargs) -> Any:
        """内部接口调用。

        Args:
            action (str): 内部接口名称
            method (str, optional): 请求方法，默认为 POST
            **kwargs: 参数
        """
        return await self.call_api(f"internal/{action}", kwargs, method=method)

    async def meta_get(self) -> Meta:
        """获取元信息。返回一个 `Meta` 对象。

        Returns:
            Meta: `Meta` 对象
        """
        res = await self.call_api("meta")
        return Meta.parse(res)

    @deprecated("Use `meta_get` instead")
    async def admin_login_list(self) -> list[LoginPartial]:
        """获取登录信息列表。返回一个 `Login` 对象构成的数组。

        Returns:
            list[Login]: `Login` 对象构成的数组
        """
        return (await self.meta_get()).logins

    async def webhook_create(self, url: str, token: str | None = None):
        """创建 Webhook。"""
        await self.call_api("meta/webhook.create", {"url": url, "token": token})

    async def webhook_delete(self, url: str):
        """删除 Webhook。"""
        await self.call_api("meta/webhook.delete", {"url": url})

    @overload
    async def upload_create(self, *uploads: Upload) -> list[str]: ...

    @overload
    async def upload_create(self, **uploads: Upload) -> dict[str, str]: ...

    async def upload_create(self, *args: Upload, **kwargs: Upload):
        """上传文件。

        如果要发送的消息中含有图片或其他媒体资源，\
            可以使用此 API 将文件上传至 Satori 服务器并转换为 URL，以便在消息编码中使用。
        """
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
