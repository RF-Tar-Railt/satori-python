from collections.abc import AsyncIterable, Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from os import PathLike
from typing import IO, Any, Generic, Literal, TypeVar
from collections.abc import Callable, AsyncIterator
from typing_extensions import Self
from typing import TypeAlias

from satori.element import Element


@dataclass(kw_only=True)
class ModelBase:
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
class Member(ModelBase):
    user: User | None = None
    nick: str | None = None
    avatar: str | None = None
    joined_at: datetime | None = None



@dataclass(kw_only=True)
class Role(ModelBase):
    id: str
    name: str | None = None



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
    features: list[str] = ...

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
    proxy_urls: list[str] = ...

@dataclass(kw_only=True)
class MetaPayload(ModelBase):
    """Meta 信令"""

    proxy_urls: list[str]



@dataclass(kw_only=True)
class Meta(ModelBase):
    """Meta 数据"""

    logins: list[LoginPartial]
    proxy_urls: list[str] = ...



@dataclass(kw_only=True)
class MessageObject(ModelBase):
    id: str
    content: str
    channel: Channel | None = None
    guild: Guild | None = None
    member: Member | None = None
    user: User | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

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
    ) -> MessageObject: ...

    @property
    def message(self) -> list[Element]: ...

    @message.setter
    def message(self, value: list[Element]): ...


@dataclass(kw_only=True)
class MessageReceipt(ModelBase):
    id: str
    content: str | None = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: list[Element] | None = None,
    ) -> MessageReceipt: ...

    @property
    def message(self) -> list[Element] | None: ...

    @message.setter
    def message(self, value: list[Element] | None): ...


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

    _type: str | None = None
    _data: dict | None = None

    sn: int = 0


    @property
    def platform(self) -> str: ...

    @property
    def self_id(self) -> str: ...


T = TypeVar("T", bound=ModelBase)


@dataclass
class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> PageResult[T]: ...


@dataclass
class PageDequeResult(PageResult[T]):
    prev: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> PageDequeResult[T]: ...


class IterablePageResult(Generic[T], AsyncIterable[T], Awaitable[PageResult[T]]):
    func: Callable[[str | None], Awaitable[PageResult[T]]]
    next_page: str | None

    def __init__(self, func: Callable[[str | None], Awaitable[PageResult[T]]], initial_page: str | None = None): ...

    def __await__(self): ...

    def __aiter__(self) -> AsyncIterator[T]: ...


Direction: TypeAlias = Literal["before", "after", "around"]
Order: TypeAlias = Literal["asc", "desc"]


@dataclass
class Upload:
    file: bytes | IO[bytes] | PathLike
    mimetype: str = "image/png"
    name: str | None = None

    def dump(self) -> dict[str, Any]: ...
