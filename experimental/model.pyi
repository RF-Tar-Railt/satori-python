from collections.abc import AsyncIterable, Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from os import PathLike
from typing import IO, Any, Callable, Generic, Literal, Optional, TypeVar, Union, AsyncIterator
from typing_extensions import TypeAlias, Self

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
    name: Optional[str] = None
    parent_id: Optional[str] = None


@dataclass(kw_only=True)
class Guild(ModelBase):
    id: str
    name: Optional[str] = None
    avatar: Optional[str] = None



@dataclass(kw_only=True)
class User(ModelBase):
    id: str
    name: Optional[str] = None
    nick: Optional[str] = None
    avatar: Optional[str] = None
    is_bot: Optional[bool] = None



@dataclass(kw_only=True)
class Member(ModelBase):
    user: Optional[User] = None
    nick: Optional[str] = None
    avatar: Optional[str] = None
    joined_at: Optional[datetime] = None



@dataclass(kw_only=True)
class Role(ModelBase):
    id: str
    name: Optional[str] = None



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
    platform: Optional[str] = None
    user: Optional[User] = None


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
    token: Optional[str] = None
    sn: Optional[int] = None


    @property
    def sequence(self) -> Optional[int]: ...

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
    channel: Optional[Channel] = None
    guild: Optional[Guild] = None
    member: Optional[Member] = None
    user: Optional[User] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: list[Element],
        channel: Optional[Channel] = None,
        guild: Optional[Guild] = None,
        member: Optional[Member] = None,
        user: Optional[User] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> "MessageObject": ...

    @property
    def message(self) -> list[Element]: ...

    @message.setter
    def message(self, value: list[Element]): ...


@dataclass(kw_only=True)
class MessageReceipt(ModelBase):
    id: str
    content: Optional[str] = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: Optional[list[Element]] = None,
    ) -> "MessageReceipt": ...

    @property
    def message(self) -> Optional[list[Element]]: ...

    @message.setter
    def message(self, value: Optional[list[Element]]): ...


@dataclass(kw_only=True)
class Event(ModelBase):
    type: str
    timestamp: datetime
    login: Login
    argv: Optional[ArgvInteraction] = None
    button: Optional[ButtonInteraction] = None
    channel: Optional[Channel] = None
    guild: Optional[Guild] = None
    member: Optional[Member] = None
    message: Optional[MessageObject] = None
    operator: Optional[User] = None
    role: Optional[Role] = None
    user: Optional[User] = None

    _type: Optional[str] = None
    _data: Optional[dict] = None

    sn: int = 0


    @property
    def platform(self) -> str: ...

    @property
    def self_id(self) -> str: ...


T = TypeVar("T", bound=ModelBase)


@dataclass
class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict, parser: Optional[Callable[[dict], T]] = None) -> "PageResult[T]": ...


@dataclass
class PageDequeResult(PageResult[T]):
    prev: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict, parser: Optional[Callable[[dict], T]] = None) -> "PageDequeResult[T]": ...


class IterablePageResult(Generic[T], AsyncIterable[T], Awaitable[PageResult[T]]):
    func: Callable[[Optional[str]], Awaitable[PageResult[T]]]
    next_page: Optional[str]

    def __init__(self, func: Callable[[Optional[str]], Awaitable[PageResult[T]]], initial_page: Optional[str] = None): ...

    def __await__(self): ...

    def __aiter__(self) -> AsyncIterator[T]: ...


Direction: TypeAlias = Literal["before", "after", "around"]
Order: TypeAlias = Literal["asc", "desc"]


@dataclass
class Upload:
    file: Union[bytes, IO[bytes], PathLike]
    mimetype: str = "image/png"
    name: Optional[str] = None

    def dump(self) -> dict[str, Any]: ...
