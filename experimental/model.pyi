from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from os import PathLike
from typing import IO, Any, Generic, Literal, TypeAlias, TypeVar, Generator, AsyncGenerator
from typing_extensions import Self

from satori.element import Element, Emoji


@dataclass(kw_only=True)
class ModelBase:
    # _raw_data: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def parse(cls: type[Self], raw: dict) -> Self: ...

    def dump(self) -> dict: ...


class ChannelType(IntEnum):
    TEXT = 0
    DIRECT = 1
    CATEGORY = 2
    VOICE = 3


@dataclass(kw_only=True)
class Channel(ModelBase):
    id: str
    type: ChannelType = ChannelType.TEXT
    name: str | None = None
    parent_id: str | None = None


@dataclass(kw_only=True)
class Guild(ModelBase):
    id: str
    name: str | None = None
    avatar: str | None = None



@dataclass(kw_only=True)
class User(ModelBase):
    id: str
    name: str | None = None
    nick: str | None = None
    avatar: str | None = None
    is_bot: bool | None = None



@dataclass(kw_only=True)
class Friend(ModelBase):
    user: User | None = None
    nick: str | None = None

    @property
    def remark(self) -> str | None: ...


@dataclass(kw_only=True)
class Role(ModelBase):
    id: str
    name: str | None = None



@dataclass(kw_only=True)
class Member(ModelBase):
    user: User | None = None
    nick: str | None = None
    avatar: str | None = None
    joined_at: datetime | None = None
    roles: list[Role] = field(default_factory=list)



class LoginStatus(IntEnum):
    OFFLINE = 0
    """离线"""
    ONLINE = 1
    """在线"""
    CONNECT = 2
    """正在连接"""
    DISCONNECT = 3
    """正在断开连接"""
    RECONNECT = 4
    """正在重新连接"""


@dataclass(kw_only=True)
class Login(ModelBase):
    sn: int
    status: LoginStatus
    adapter: str
    platform: str
    user: User
    features: list[str] = field(default_factory=list)

    @property
    def id(self) -> str: ...


@dataclass(kw_only=True)
class LoginPartial(Login):
    platform: str | None = None
    user: User | None = None


@dataclass(kw_only=True)
class ArgvInteraction(ModelBase):
    name: str
    arguments: list
    options: Any


@dataclass(kw_only=True)
class ButtonInteraction(ModelBase):
    id: str
    data: str | None = None


class Opcode(IntEnum):
    EVENT = 0
    """事件 (接收)"""
    PING = 1
    """心跳 (发送)"""
    PONG = 2
    """心跳回复 (接收)"""
    IDENTIFY = 3
    """鉴权 (发送)"""
    READY = 4
    """鉴权成功 (接收)"""
    META = 5
    """元信息更新 (接收)"""


@dataclass(kw_only=True)
class Identify(ModelBase):
    token: str | None = None
    sn: int | None = None

    @property
    def sequence(self) -> int | None: ...

@dataclass(kw_only=True)
class Ready(ModelBase):
    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class MetaPayload(ModelBase):
    """Meta 信令"""

    proxy_urls: list[str]

    def dump(self):
        return {"proxy_urls": self.proxy_urls}


@dataclass(kw_only=True)
class Meta(ModelBase):
    """Meta 数据"""

    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class EmojiObject(ModelBase):
    id: str
    name: str | None = None

    def to_element(self) -> Emoji: ...


@dataclass(kw_only=True)
class MessageObject(ModelBase):
    id: str
    content: str = ""
    channel: Channel | None = None
    guild: Guild | None = None
    member: Member | None = None
    user: User | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    referrer: dict | None = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: list[Element],
        channel: Channel | None = None,
        guild: Guild | None = None,
        member: Member | None = None,
        user: User | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        referrer: dict | None = None,
    ): ...

    @property
    def message(self) -> list[Element]: ...
    @message.setter
    def message(self, value: list[Element]): ...


@dataclass(kw_only=True)
class Event(ModelBase):
    type: str
    timestamp: datetime
    login: Login
    argv: ArgvInteraction | None = None
    button: ButtonInteraction | None = None
    channel: Channel | None = None
    guild: Guild | None = None
    member: Member | None = None
    message: MessageObject | None = None
    operator: User | None = None
    role: Role | None = None
    user: User | None = None
    referrer: dict | None = None
    emoji: EmojiObject | None = None

    _type: str | None = None
    _data: dict | None = None

    sn: int = 0

    @property
    def platform(self):
        return self.login.platform

    @property
    def self_id(self):
        return self.login.id


T = TypeVar("T", bound=ModelBase)


@dataclass(kw_only=True)
class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageResult[T]": ...


@dataclass(kw_only=True)
class PageDequeResult(PageResult[T]):
    prev: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageDequeResult[T]": ...


class IterablePageResult(Generic[T], AsyncIterable[T], Awaitable[PageResult[T]]):
    def __init__(self, func: Callable[[str | None], Awaitable[PageResult[T]]], initial_page: str | None = None): ...

    def __await__(self) -> Generator[Any, Any, PageResult[T]]: ...

    def __aiter__(self) -> AsyncGenerator[PageResult[T], Any]: ...

Direction: TypeAlias = Literal["before", "after", "around"]
Order: TypeAlias = Literal["asc", "desc"]


class Upload:
    def __init__(self, file: bytes | IO[bytes] | PathLike, mimetype: str = "image/png", name: str | None = None): ...
    def dump(self) -> dict: ...

