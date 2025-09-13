from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, TypeAlias, TypeVar, overload
from typing_extensions import NotRequired, TypedDict

from starlette.datastructures import FormData

from satori.model import (
    Channel,
    Direction,
    Guild,
    Login,
    Member,
    MessageObject,
    ModelBase,
    Order,
    PageDequeResult,
    PageResult,
    Role,
    User,
)

from .. import Api
from .model import Request

T = TypeVar("T")
R = TypeVar("R", covariant=True)


class RouteCall(Protocol[T, R]):
    def __call__(self, request: Request[T]) -> Awaitable[R]: ...


INTERAL: TypeAlias = RouteCall[Any, ModelBase | list[ModelBase] | dict[str, Any] | list[dict[str, Any]] | None]


class MessageParam(TypedDict):
    channel_id: str
    content: str


MESSAGE_CREATE: TypeAlias = RouteCall[MessageParam, list[MessageObject] | list[dict[str, Any]]]


class MessageOpParam(TypedDict):
    channel_id: str
    message_id: str


MESSAGE_GET: TypeAlias = RouteCall[MessageOpParam, MessageObject | dict[str, Any]]
MESSAGE_DELETE: TypeAlias = RouteCall[MessageOpParam, None]


class MessageUpdateParam(TypedDict):
    channel_id: str
    message_id: str
    content: str


MESSAGE_UPDATE: TypeAlias = RouteCall[MessageUpdateParam, None]


class MessageListParam(TypedDict):
    channel_id: str
    next: NotRequired[str]
    direction: NotRequired[Direction]
    limit: NotRequired[int]
    order: NotRequired[Order]


MESSAGE_LIST: TypeAlias = RouteCall[MessageListParam, PageDequeResult[MessageObject] | dict[str, Any]]


class ChannelParam(TypedDict):
    channel_id: str


CHANNEL_GET: TypeAlias = RouteCall[ChannelParam, Channel | dict[str, Any]]
CHANNEL_DELETE: TypeAlias = RouteCall[ChannelParam, None]


class ChannelListParam(TypedDict):
    guild_id: str
    next: NotRequired[str]


CHANNEL_LIST: TypeAlias = RouteCall[ChannelListParam, PageResult[Channel] | dict[str, Any]]


class ChannelCreateParam(TypedDict):
    guild_id: str
    data: dict


CHANNEL_CREATE: TypeAlias = RouteCall[ChannelCreateParam, Channel | dict[str, Any]]


class ChannelUpdateParam(TypedDict):
    channel_id: str
    data: dict


CHANNEL_UPDATE: TypeAlias = RouteCall[ChannelUpdateParam, None]


class ChannelMuteParam(TypedDict):
    channel_id: str
    duration: float


CHANNEL_MUTE: TypeAlias = RouteCall[ChannelMuteParam, None]


class UserChannelCreateParam(TypedDict):
    user_id: str
    guild_id: NotRequired[str]


ROUTE_USER_CHANNEL_CREATE: TypeAlias = RouteCall[UserChannelCreateParam, Channel | dict[str, Any]]


class GuildGetParam(TypedDict):
    guild_id: str


GUILD_GET: TypeAlias = RouteCall[GuildGetParam, Guild | dict[str, Any]]


class GuildListParam(TypedDict):
    next: NotRequired[str]


GUILD_LIST: TypeAlias = RouteCall[GuildListParam, PageResult[Guild] | dict[str, Any]]


class GuildMemberGetParam(TypedDict):
    guild_id: str
    user_id: str


GUILD_MEMBER_GET: TypeAlias = RouteCall[GuildMemberGetParam, Member | dict[str, Any]]


class GuildXXXListParam(TypedDict):
    guild_id: str
    next: NotRequired[str]


GUILD_MEMBER_LIST: TypeAlias = RouteCall[GuildXXXListParam, PageResult[Member] | dict[str, Any]]


class GuildMemberKickParam(TypedDict):
    guild_id: str
    user_id: str
    permanent: NotRequired[bool]


GUILD_MEMBER_KICK: TypeAlias = RouteCall[GuildMemberKickParam, None]


class GuildMemberMuteParam(TypedDict):
    guild_id: str
    user_id: str
    duration: float


GUILD_MEMBER_MUTE: TypeAlias = RouteCall[GuildMemberMuteParam, None]


class GuildMemberRoleParam(TypedDict):
    guild_id: str
    user_id: str
    role_id: str


GUILD_MEMBER_ROLE_SET: TypeAlias = RouteCall[GuildMemberRoleParam, None]
GUILD_MEMBER_ROLE_UNSET: TypeAlias = RouteCall[GuildMemberRoleParam, None]

GUILD_ROLE_LIST: TypeAlias = RouteCall[GuildXXXListParam, PageResult[Role] | dict[str, Any]]


class GuildRoleCreateParam(TypedDict):
    guild: str
    role: dict


GUILD_ROLE_CREATE: TypeAlias = RouteCall[GuildRoleCreateParam, Role | dict[str, Any]]


class GuildRoleUpdateParam(TypedDict):
    guild: str
    role_id: str
    role: dict


GUILD_ROLE_UPDATE: TypeAlias = RouteCall[GuildRoleUpdateParam, None]


class GuildRoleDeleteParam(TypedDict):
    guild: str
    role_id: str


GUILD_ROLE_DELETE: TypeAlias = RouteCall[GuildRoleDeleteParam, None]


class ReactionCreateParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str


REACTION_CREATE: TypeAlias = RouteCall[ReactionCreateParam, None]


class ReactionDeleteParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str
    user_id: NotRequired[str]


REACTION_DELETE: TypeAlias = RouteCall[ReactionDeleteParam, None]


class ReactionClearParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: NotRequired[str]


REACTION_CLEAR: TypeAlias = RouteCall[ReactionClearParam, None]


class ReactionListParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str
    next: NotRequired[str]


REACTION_LIST: TypeAlias = RouteCall[ReactionListParam, PageResult[User] | dict[str, Any]]
LOGIN_GET: TypeAlias = RouteCall[Any, Login | dict[str, Any]]


class UserGetParam(TypedDict):
    user_id: str


USER_GET: TypeAlias = RouteCall[UserGetParam, User | dict[str, Any]]


class FriendListParam(TypedDict):
    next: NotRequired[str]


FRIEND_LIST: TypeAlias = RouteCall[FriendListParam, PageResult[User] | dict[str, Any]]


class ApproveParam(TypedDict):
    message_id: str
    approve: bool
    comment: NotRequired[str]


APPROVE: TypeAlias = RouteCall[ApproveParam, None]


UPLOAD_CREATE: TypeAlias = RouteCall[FormData, dict[str, str]]


class RouterMixin:
    routes: dict[str, RouteCall[Any, Any]]

    @overload
    def route(self, path: Literal[Api.MESSAGE_CREATE]) -> Callable[[MESSAGE_CREATE], MESSAGE_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_UPDATE]) -> Callable[[MESSAGE_UPDATE], MESSAGE_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_GET]) -> Callable[[MESSAGE_GET], MESSAGE_GET]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_DELETE]) -> Callable[[MESSAGE_DELETE], MESSAGE_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_LIST]) -> Callable[[MESSAGE_LIST], MESSAGE_LIST]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_GET]) -> Callable[[CHANNEL_GET], CHANNEL_GET]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_LIST]) -> Callable[[CHANNEL_LIST], CHANNEL_LIST]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_CREATE]) -> Callable[[CHANNEL_CREATE], CHANNEL_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_UPDATE]) -> Callable[[CHANNEL_UPDATE], CHANNEL_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_DELETE]) -> Callable[[CHANNEL_DELETE], CHANNEL_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_MUTE]) -> Callable[[CHANNEL_MUTE], CHANNEL_MUTE]: ...

    @overload
    def route(
        self, path: Literal[Api.USER_CHANNEL_CREATE]
    ) -> Callable[[ROUTE_USER_CHANNEL_CREATE], ROUTE_USER_CHANNEL_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_GET]) -> Callable[[GUILD_GET], GUILD_GET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_LIST]) -> Callable[[GUILD_LIST], GUILD_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_APPROVE]) -> Callable[[APPROVE], APPROVE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_LIST]) -> Callable[[GUILD_MEMBER_LIST], GUILD_MEMBER_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_GET]) -> Callable[[GUILD_MEMBER_GET], GUILD_MEMBER_GET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_KICK]) -> Callable[[GUILD_MEMBER_KICK], GUILD_MEMBER_KICK]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_MUTE]) -> Callable[[GUILD_MEMBER_MUTE], GUILD_MEMBER_MUTE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_APPROVE]) -> Callable[[APPROVE], APPROVE]: ...

    @overload
    def route(
        self, path: Literal[Api.GUILD_MEMBER_ROLE_SET]
    ) -> Callable[[GUILD_MEMBER_ROLE_SET], GUILD_MEMBER_ROLE_SET]: ...

    @overload
    def route(
        self, path: Literal[Api.GUILD_MEMBER_ROLE_UNSET]
    ) -> Callable[[GUILD_MEMBER_ROLE_UNSET], GUILD_MEMBER_ROLE_UNSET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_LIST]) -> Callable[[GUILD_ROLE_LIST], GUILD_ROLE_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_CREATE]) -> Callable[[GUILD_ROLE_CREATE], GUILD_ROLE_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_UPDATE]) -> Callable[[GUILD_ROLE_UPDATE], GUILD_ROLE_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_DELETE]) -> Callable[[GUILD_ROLE_DELETE], GUILD_ROLE_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_CREATE]) -> Callable[[REACTION_CREATE], REACTION_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_DELETE]) -> Callable[[REACTION_DELETE], REACTION_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_CLEAR]) -> Callable[[REACTION_CLEAR], REACTION_CLEAR]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_LIST]) -> Callable[[REACTION_LIST], REACTION_LIST]: ...

    @overload
    def route(self, path: Literal[Api.LOGIN_GET]) -> Callable[[LOGIN_GET], LOGIN_GET]: ...

    @overload
    def route(self, path: Literal[Api.USER_GET]) -> Callable[[USER_GET], USER_GET]: ...

    @overload
    def route(self, path: Literal[Api.FRIEND_LIST]) -> Callable[[FRIEND_LIST], FRIEND_LIST]: ...

    @overload
    def route(self, path: Literal[Api.FRIEND_APPROVE]) -> Callable[[APPROVE], APPROVE]: ...

    @overload
    def route(self, path: Literal[Api.UPLOAD_CREATE]) -> Callable[[UPLOAD_CREATE], UPLOAD_CREATE]: ...

    @overload
    def route(self, path: str) -> Callable[[INTERAL], INTERAL]: ...

    def route(self, path: str | Api) -> Callable[[RouteCall], RouteCall]:
        """注册一个 Satori 路由

        Args:
            path (str | Api): 路由路径；若 path 不属于 Api，则会被认为是内部接口
        """

        def wrapper(func: RouteCall):
            if isinstance(path, Api):
                self.routes[path.value] = func
            else:
                self.routes[f"internal/{path}"] = func
            return func

        return wrapper
