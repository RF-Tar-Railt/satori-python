import asyncio
from collections.abc import Iterable
from typing import Any, Generic, Protocol, TypeVar, overload
from typing_extensions import deprecated

from yarl import URL

from satori.element import Element
from satori.model import (
    Channel,
    Direction,
    Event,
    Guild,
    IterablePageResult,
    Login,
    Member,
    MessageObject,
    MessageReceipt,
    Meta,
    Order,
    PageDequeResult,
    Role,
    Upload,
    User,
)

from .protocol import ApiProtocol

TP = TypeVar("TP", bound="ApiProtocol")
TP1 = TypeVar("TP1", bound="ApiProtocol")

class Api(Protocol):
    token: str | None = None

    @property
    def api_base(self) -> URL: ...

class ApiInfo(Api):
    def __init__(
        self, host: str = "localhost", port: int = 5140, path: str = "", token: str | None = None
    ): ...

class Account(Generic[TP]):
    adapter: str
    self_info: Login
    proxy_urls: list[str]
    config: Api
    protocol: TP
    connected: asyncio.Event

    def __init__(
        self,
        login: Login,
        config: Api,
        proxy_urls: list[str],
        protocol_cls: type[TP] = ApiProtocol,
    ): ...
    @property
    def platform(self) -> str: ...
    @property
    def self_id(self) -> str: ...
    @overload
    def custom(self, config: Api, protocol_cls: type[TP1] = ApiProtocol) -> Account[TP1]: ...
    @overload
    def custom(self, *, protocol_cls: type[TP1]) -> Account[TP1]: ...
    @overload
    def custom(
        self, *, protocol_cls: type[TP1] = ApiProtocol, host: str, port: int, token: str | None = None
    ) -> Account[TP1]: ...
    def ensure_url(self, url: str) -> URL:
        """确定链接形式。

        若链接符合以下条件之一，则返回链接的代理形式 ({host}/{path}/{version}/proxy/{url})：
            - 链接以 "upload://" 开头
            - 链接开头出现在 self_info.proxy_urls 中的某一项
        """

    async def send(self, event: Event, message: str | Iterable[str | Element]) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            event (Event): 当前事件(上下文)
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageObject]: `MessageObject` 对象构成的数组

        Raises:
            RuntimeError: 传入的事件缺少 `channel` 对象
        """

    async def send_message(
        self, channel: str | Channel, message: str | Iterable[str | Element]
    ) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            channel (str | Channel): 要发送的频道 ID
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageObject]: `MessageObject` 对象构成的数组
        """

    async def send_private_message(
        self, user: str | User, message: str | Iterable[str | Element]
    ) -> list[MessageReceipt]:
        """发送私聊消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            user (str | User): 要发送的用户 ID
            message (str | Iterable[str | Element]): 要发送的消息

        Returns:
            list[MessageObject]: `MessageObject` 对象构成的数组
        """

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

    async def message_create(self, channel_id: str, content: str) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            channel_id (str): 频道 ID
            content (str): 消息内容

        Returns:
            list[MessageObject]: `MessageObject` 对象构成的数组
        """

    async def message_get(self, channel_id: str, message_id: str) -> MessageObject:
        """获取特定消息。返回一个 `MessageObject` 对象。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID

        Returns:
            MessageObject: `MessageObject` 对象
        """

    async def message_delete(self, channel_id: str, message_id: str) -> None:
        """撤回特定消息。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID

        Returns:
            None: 该方法无返回值
        """

    async def message_update(self, channel_id: str, message_id: str, content: str) -> None:
        """编辑特定消息。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            content (str): 消息内容

        Returns:
            None: 该方法无返回值
        """

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

    async def channel_get(self, channel_id: str) -> Channel:
        """根据 ID 获取频道。返回一个 `Channel` 对象。

        Args:
            channel_id (str): 频道 ID

        Returns:
            Channel: `Channel` 对象
        """

    def channel_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Channel]:
        """获取群组中的全部频道。返回一个 Channel 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Channel]: `Channel` 的分页列表
        """

    async def channel_create(self, guild_id: str, data: Channel) -> Channel:
        """创建群组频道。返回一个 Channel 对象。

        Args:
            guild_id (str): 群组 ID
            data (Channel): 频道数据

        Returns:
            Channel: `Channel` 对象
        """

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

    async def channel_delete(self, channel_id: str) -> None:
        """删除群组频道。

        Args:
            channel_id (str): 频道 ID

        Returns:
            None: 该方法无返回值
        """

    async def channel_mute(self, channel_id: str, duration: float = 60) -> None:
        """禁言群组频道。

        如果传入的禁言时长为 0 则表示解除禁言。

        Args:
            channel_id (str): 频道 ID
            duration (float, optional): 禁言时长 (秒)，默认为 60 秒
        Returns:
            None: 该方法无返回值
        """

    async def user_channel_create(self, user_id: str, guild_id: str | None = None) -> Channel:
        """创建一个私聊频道。返回一个 Channel 对象。

        Args:
            user_id (str): 用户 ID
            guild_id (str | None, optional): 群组 ID

        Returns:
            Channel: `Channel` 对象
        """

    async def guild_get(self, guild_id: str) -> Guild:
        """根据 ID 获取群组。返回一个 `Guild` 对象。

        Args:
            guild_id (str): 群组 ID

        Returns:
            Guild: `Guild` 对象
        """

    def guild_list(self, next_token: str | None = None) -> IterablePageResult[Guild]:
        """获取当前用户加入的全部群组。返回一个 Guild 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Guild]: `Guild` 的分页列表
        """

    async def guild_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理来自群组的邀请。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """

    def guild_member_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Member]:
        """获取群组成员列表。返回一个 Member 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Member]: `Member` 的分页列表
        """

    async def guild_member_get(self, guild_id: str, user_id: str) -> Member:
        """获取群成员信息。返回一个 `Member` 对象。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID

        Returns:
            Member: `Member` 对象
        """

    async def guild_member_kick(self, guild_id: str, user_id: str, permanent: bool = False) -> None:
        """将某个用户踢出群组。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            permanent (bool, optional): 是否永久踢出 (无法再次加入群组)，默认为 False

        Returns:
            None: 该方法无返回值
        """

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

    async def guild_member_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理来自群组的加群请求。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """

    async def guild_member_role_set(self, guild_id: str, user_id: str, role_id: str) -> None:
        """设置群组内用户的角色。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """

    async def guild_member_role_unset(self, guild_id: str, user_id: str, role_id: str) -> None:
        """取消群组内用户的角色。

        Args:
            guild_id (str): 群组 ID
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """

    def guild_role_list(self, guild_id: str, next_token: str | None = None) -> IterablePageResult[Role]:
        """获取群组角色列表。返回一个 Role 的分页列表。

        Args:
            guild_id (str): 群组 ID
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Role]: `Role` 的分页列表
        """

    async def guild_role_create(self, guild_id: str, role: Role) -> Role:
        """创建群组角色。返回一个 Role 对象。

        Args:
            guild_id (str): 群组 ID
            role (Role): 角色数据

        Returns:
            Role: `Role` 对象
        """

    async def guild_role_update(self, guild_id: str, role_id: str, role: Role) -> None:
        """修改群组角色。

        Args:
            guild_id (str): 群组 ID
            role_id (str): 角色 ID
            role (Role): 角色数据

        Returns:
            None: 该方法无返回值
        """

    async def guild_role_delete(self, guild_id: str, role_id: str) -> None:
        """删除群组角色。

        Args:
            guild_id (str): 群组 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """

    async def reaction_create(self, channel_id: str, message_id: str, emoji: str) -> None:
        """向特定消息添加表态。

        Args:
            channel_id (str): 频道 ID
            message_id (str): 消息 ID
            emoji (str): 表态名称

        Returns:
            None: 该方法无返回值
        """

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

    async def login_get(self) -> Login:
        """获取当前登录信息。返回一个 `Login` 对象。

        Returns:
            Login: `Login` 对象
        """

    async def user_get(self, user_id: str) -> User:
        """获取用户信息。返回一个 `User` 对象。

        Args:
            user_id (str): 用户 ID

        Returns:
            User: `User` 对象
        """

    def friend_list(self, next_token: str | None = None) -> IterablePageResult[User]:
        """获取好友列表。返回一个 User 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[User]: `User` 的分页列表
        """

    async def friend_approve(self, request_id: str, approve: bool, comment: str) -> None:
        """处理好友申请。

        Args:
            request_id (str): 请求 ID
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """

    async def internal(self, action: str, method: str = "POST", **kwargs) -> Any:
        """内部接口调用。

        Args:
            action (str): 内部接口名称
            method (str, optional): 请求方法，默认为 POST
            **kwargs: 参数
        """

    async def meta_get(self) -> Meta:
        """获取元信息。返回一个 `Meta` 对象。

        Returns:
            Meta: `Meta` 对象
        """

    @deprecated("Use `meta_get` instead")
    async def admin_login_list(self) -> list[Login]:
        """获取登录信息列表。返回一个 `Login` 对象构成的数组。

        Returns:
            list[Login]: `Login` 对象构成的数组
        """

    async def webhook_create(self, url: str, token: str | None = None):
        """创建 Webhook。"""

    async def webhook_delete(self, url: str):
        """删除 Webhook。"""

    @overload
    async def upload_create(self, *uploads: Upload) -> list[str]: ...
    @overload
    async def upload_create(self, **uploads: Upload) -> dict[str, str]: ...
    async def upload_create(self, *args: Upload, **kwargs: Upload):
        """上传文件。

        如果要发送的消息中含有图片或其他媒体资源，\
            可以使用此 API 将文件上传至 Satori 服务器并转换为 URL，以便在消息编码中使用。
        """
    upload = upload_create

    async def download(self, url: str):
        """访问内部链接。"""

    async def request_internal(self, url: str, method: str = "GET", **kwargs) -> dict:
        """访问内部链接。"""
