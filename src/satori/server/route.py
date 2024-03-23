from typing import Any, Awaitable, Dict, List, Protocol, TypeVar, Union
from typing_extensions import NotRequired, TypeAlias, TypedDict

from satori.model import Channel, Guild, Login, Member, MessageObject, ModelBase, PageResult, Role, User

from .model import Request

T = TypeVar("T")
R = TypeVar("R", covariant=True)


class Router(Protocol[T, R]):
    def __call__(self, request: Request[T]) -> Awaitable[R]: ...


INTERAL: TypeAlias = Router[
    Any, Union[ModelBase, List[ModelBase], Dict[str, Any], List[Dict[str, Any]], None]
]


class MessageParam(TypedDict):
    channel_id: str
    content: str


MESSAGE_CREATE: TypeAlias = Router[MessageParam, Union[List[MessageObject], List[Dict[str, Any]]]]
MESSAGE_GET: TypeAlias = Router[MessageParam, Union[MessageObject, Dict[str, Any]]]
MESSAGE_DELETE: TypeAlias = Router[MessageParam, None]


class MessageUpdateParam(TypedDict):
    channel_id: str
    message_id: str
    content: str


MESSAGE_UPDATE: TypeAlias = Router[MessageUpdateParam, None]


class MessageListParam(TypedDict):
    channel_id: str
    next: NotRequired[str]


MESSAGE_LIST: TypeAlias = Router[MessageListParam, Union[PageResult[MessageObject], Dict[str, Any]]]


class ChannelParam(TypedDict):
    channel_id: str


CHANNEL_GET: TypeAlias = Router[ChannelParam, Union[Channel, Dict[str, Any]]]
CHANNEL_DELETE: TypeAlias = Router[ChannelParam, None]


class ChannelListParam(TypedDict):
    guild_id: str
    next: NotRequired[str]


CHANNEL_LIST: TypeAlias = Router[ChannelListParam, Union[PageResult[Channel], Dict[str, Any]]]


class ChanneCreateParam(TypedDict):
    guild_id: str
    data: dict


CHANNEL_CREATE: TypeAlias = Router[ChanneCreateParam, Union[Channel, Dict[str, Any]]]


class ChanneUpdateParam(TypedDict):
    channel_id: str
    data: dict


CHANNEL_UPDATE: TypeAlias = Router[ChanneUpdateParam, None]


class ChannelMuteParam(TypedDict):
    channel_id: str
    duration: float


CHANNEL_MUTE: TypeAlias = Router[ChannelMuteParam, None]


class UserChannelCreateParam(TypedDict):
    user_id: str
    guild_id: NotRequired[str]


ROUTE_USER_CHANNEL_CREATE: TypeAlias = Router[UserChannelCreateParam, Union[Channel, Dict[str, Any]]]


class GuildGetParam(TypedDict):
    guild_id: str


GUILD_GET: TypeAlias = Router[GuildGetParam, Union[Guild, Dict[str, Any]]]


class GuildListParam(TypedDict):
    next: NotRequired[str]


GUILD_LIST: TypeAlias = Router[GuildListParam, Union[PageResult[Guild], Dict[str, Any]]]


class GuildMemberGetParam(TypedDict):
    guild_id: str
    user_id: str


GUILD_MEMBER_GET: TypeAlias = Router[GuildMemberGetParam, Union[Member, Dict[str, Any]]]


class GuildXXXListParam(TypedDict):
    guild_id: str
    next: NotRequired[str]


GUILD_MEMBER_LIST: TypeAlias = Router[GuildXXXListParam, Union[PageResult[Member], Dict[str, Any]]]


class GuildMemberKickParam(TypedDict):
    guild_id: str
    user_id: str
    permanent: NotRequired[bool]


GUILD_MEMBER_KICK: TypeAlias = Router[GuildMemberKickParam, None]


class GuildMemberMuteParam(TypedDict):
    guild_id: str
    user_id: str
    duration: float


GUILD_MEMBER_MUTE: TypeAlias = Router[GuildMemberMuteParam, None]


class GuildMemberRoleParam(TypedDict):
    guild_id: str
    user_id: str
    role_id: str


GUILD_MEMBER_ROLE_SET: TypeAlias = Router[GuildMemberRoleParam, None]
GUILD_MEMBER_ROLE_UNSET: TypeAlias = Router[GuildMemberRoleParam, None]

GUILD_ROLE_LIST: TypeAlias = Router[GuildXXXListParam, Union[PageResult[Role], Dict[str, Any]]]


class GuildRoleCreateParam(TypedDict):
    guild: str
    role: dict


GUILD_ROLE_CREATE: TypeAlias = Router[GuildRoleCreateParam, Union[Role, Dict[str, Any]]]


class GuildRoleUpdateParam(TypedDict):
    guild: str
    role_id: str
    role: dict


GUILD_ROLE_UPDATE: TypeAlias = Router[GuildRoleUpdateParam, None]


class GuildRoleDeleteParam(TypedDict):
    guild: str
    role_id: str


GUILD_ROLE_DELETE: TypeAlias = Router[GuildRoleDeleteParam, None]


class ReactionCreateParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str


REACTION_CREATE: TypeAlias = Router[ReactionCreateParam, None]


class ReactionDeleteParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str
    user_id: NotRequired[str]


REACTION_DELETE: TypeAlias = Router[ReactionDeleteParam, None]


class ReactionClearParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: NotRequired[str]


REACTION_CLEAR: TypeAlias = Router[ReactionClearParam, None]


class ReactionListParam(TypedDict):
    channel_id: str
    message_id: str
    emoji: str
    next: NotRequired[str]


REACTION_LIST: TypeAlias = Router[ReactionListParam, Union[PageResult[User], Dict[str, Any]]]
LOGIN_GET: TypeAlias = Router[Any, Union[Login, Dict[str, Any]]]


class UserGetParam(TypedDict):
    user_id: str


USER_GET: TypeAlias = Router[UserGetParam, Union[User, Dict[str, Any]]]


class FriendListParam(TypedDict):
    next: NotRequired[str]


FRIEND_LIST: TypeAlias = Router[FriendListParam, Union[PageResult[User], Dict[str, Any]]]


class ApproveParam(TypedDict):
    message_id: str
    approve: bool
    comment: str


APPROVE: TypeAlias = Router[ApproveParam, None]
