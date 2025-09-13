import mimetypes
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import datetime
from enum import IntEnum
from os import PathLike
from pathlib import Path
from typing import IO, Any, Generic, Literal, TypeAlias, TypeVar
from typing_extensions import Self

from msgspec import Struct, field, convert, to_builtins

from satori.element import Element, transform
from satori.parser import Element as RawElement
from satori.parser import parse


class ModelBase:

    @classmethod
    def parse(cls: type[Self], raw: dict) -> Self:
        obj = convert(raw, cls, strict=False)
        obj._raw_data = raw
        return obj

    def dump(self) -> dict:
        _raw_data = getattr(self, "_raw_data", None)
        try:
            return to_builtins(self)  # type: ignore
        finally:
            if _raw_data is not None:
                self._raw_data = _raw_data


class ChannelType(IntEnum):
    TEXT = 0
    DIRECT = 1
    CATEGORY = 2
    VOICE = 3


class Channel(Struct, ModelBase, kw_only=True):
    id: str
    type: ChannelType = ChannelType.TEXT
    name: str | None = None
    parent_id: str | None = None


class Guild(Struct, ModelBase, kw_only=True):
    id: str
    name: str | None = None
    avatar: str | None = None


class User(Struct, ModelBase, kw_only=True):
    id: str
    name: str | None = None
    nick: str | None = None
    avatar: str | None = None
    is_bot: bool | None = None


class Member(Struct, ModelBase, kw_only=True):
    user: User | None = None
    nick: str | None = None
    avatar: str | None = None
    joined_at: datetime | None = None

    @classmethod
    def parse(cls, raw: dict):
        if "joined_at" in raw:
            raw["joined_at"] = int(raw["joined_at"]) / 1000
        return super().parse(raw)

    def dump(self):
        _joined_at = None
        if self.joined_at is not None:
            _joined_at = self.joined_at
            self.joined_at = self.joined_at.timestamp() * 1000  # type: ignore
        try:
            return super().dump()
        finally:
            if _joined_at is not None:
                self.joined_at = _joined_at


class Role(Struct, ModelBase, kw_only=True):
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


class Login(Struct, ModelBase, kw_only=True):
    sn: int
    status: LoginStatus
    adapter: str
    platform: str
    user: User
    features: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.user.id


class LoginPartial(Login):
    platform: str | None = None
    user: User | None = None


class ArgvInteraction(Struct, ModelBase, kw_only=True):
    name: str
    arguments: list
    options: Any


class ButtonInteraction(Struct, ModelBase, kw_only=True):
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


class Identify(Struct, ModelBase, kw_only=True):
    token: str | None = None
    sn: int | None = None

    @property
    def sequence(self) -> int | None:
        return self.sn


class Ready(Struct, ModelBase, kw_only=True):
    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)


class MetaPayload(Struct, ModelBase, kw_only=True):
    """Meta 信令"""

    proxy_urls: list[str]


class Meta(Struct, ModelBase, kw_only=True):
    """Meta 数据"""

    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)


class MessageObject(Struct, ModelBase, kw_only=True):
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
    ):
        content = "".join(str(i) for i in content)  # type: ignore
        data = locals().copy()
        data.pop("cls", None)
        data.pop("__class__", None)
        obj = cls(**data)  # type: ignore
        obj._parsed_message = content
        return obj

    @property
    def message(self) -> list[Element]:
        if hasattr(self, "_parsed_message"):
            return self._parsed_message
        self._parsed_message = transform(parse(self.content))
        return self._parsed_message

    @message.setter
    def message(self, value: list[Element]):
        self._parsed_message = value
        self.content = "".join(str(i) for i in value)

    @classmethod
    def parse(cls, raw: dict):
        if "elements" in raw and "content" not in raw:
            content = [RawElement(*item.values()) for item in raw["elements"]]
            raw["content"] = "".join(str(i) for i in content)
        if "created_at" in raw:
            raw["created_at"] = int(raw["created_at"]) / 1000
        if "updated_at" in raw:
            raw["updated_at"] = int(raw["updated_at"]) / 1000
        return super().parse(raw)


    def dump(self):
        _created_at = None
        if self.created_at is not None:
            _created_at = self.created_at
            self.created_at = self.created_at.timestamp() * 1000  # type: ignore
        _updated_at = None
        if self.updated_at is not None:
            _updated_at = self.updated_at
            self.updated_at = self.updated_at.timestamp() * 1000  # type: ignore
        try:
            return super().dump()
        finally:
            if _created_at is not None:
                self.created_at = _created_at
            if _updated_at is not None:
                self.updated_at = _updated_at


class MessageReceipt(Struct, ModelBase, kw_only=True):
    id: str
    content: str | None = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: list[Element] | None = None,
    ):
        return cls(id=id, content="".join(str(i) for i in content) if content else None)

    @property
    def message(self) -> list[Element] | None:
        return transform(parse(self.content)) if self.content else None

    @message.setter
    def message(self, value: list[Element] | None):
        self.content = "".join(str(i) for i in value) if value else None

    @classmethod
    def parse(cls, raw: dict):
        if "elements" in raw and "content" not in raw:
            content = [RawElement(*item.values()) for item in raw["elements"]]
            raw["content"] = "".join(str(i) for i in content)
        return super().parse(raw)


class Event(Struct, ModelBase, kw_only=True):
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

    @classmethod
    def parse(cls, raw: dict):
        if "timestamp" in raw:
            raw["timestamp"] = int(raw["timestamp"]) / 1000
        return super().parse(raw)

    @property
    def platform(self):
        return self.login.platform

    @property
    def self_id(self):
        return self.login.id

    def dump(self):
        _timestamp = None
        if self.timestamp is not None:
            _timestamp = self.timestamp
            self.timestamp = self.timestamp.timestamp() * 1000  # type: ignore
        try:
            return super().dump()
        finally:
            if _timestamp is not None:
                self.timestamp = _timestamp


T = TypeVar("T", bound=ModelBase)


class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageResult[T]":
        data = [(parser or ModelBase.parse)(item) for item in raw["data"]]
        return cls(data, raw.get("next"))  # type: ignore

    def dump(self):
        res: dict = {"data": [item.dump() for item in self.data]}
        if self.next:
            res["next"] = self.next
        return res


class PageDequeResult(PageResult[T]):
    prev: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageDequeResult[T]":
        data = [(parser or ModelBase.parse)(item) for item in raw["data"]]
        return cls(data, raw.get("next"), raw.get("prev"))  # type: ignore

    def dump(self):
        res: dict = {"data": [item.dump() for item in self.data]}
        if self.next:
            res["next"] = self.next
        if self.prev:
            res["prev"] = self.prev
        return res


class IterablePageResult(Generic[T], AsyncIterable[T], Awaitable[PageResult[T]]):
    def __init__(
        self, func: Callable[[str | None], Awaitable[PageResult[T]]], initial_page: str | None = None
    ):
        self.func = func
        self.next_page = initial_page

    def __await__(self):
        return self.func(self.next_page).__await__()

    def __aiter__(self):
        async def _gen():
            while True:
                result = await self.func(self.next_page)
                for item in result.data:
                    yield item
                self.next_page = result.next
                if not self.next_page:
                    break

        return _gen()


Direction: TypeAlias = Literal["before", "after", "around"]
Order: TypeAlias = Literal["asc", "desc"]


class Upload:
    file: bytes | IO[bytes] | PathLike
    mimetype: str = "image/png"
    name: str | None = None

    def __post_init__(self):
        if isinstance(self.file, PathLike):
            self.mimetype = mimetypes.guess_type(str(self.file))[0] or self.mimetype
            self.name = Path(self.file).name

    def dump(self):
        file = self.file

        if isinstance(file, PathLike):
            file = open(file, "rb")

        return {"value": file, "filename": self.name, "content_type": self.mimetype}
