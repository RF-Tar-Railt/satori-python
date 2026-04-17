import mimetypes
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import datetime
from enum import IntEnum
from os import PathLike
from pathlib import Path
from typing import IO, Any, Generic, Literal, TypeAlias, TypeVar
from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from satori.element import Element, Emoji, transform
from satori.parser import Element as RawElement
from satori.parser import parse


class ModelBase(BaseModel):

    @classmethod
    def parse(cls: type[Self], raw: dict) -> Self:
        return cls.model_validate(raw, extra="allow")

    def dump(self) -> dict:
        return self.model_dump(exclude_none=True)

    model_config = ConfigDict(extra="allow")


class ChannelType(IntEnum):
    TEXT = 0
    DIRECT = 1
    CATEGORY = 2
    VOICE = 3


class Channel(ModelBase):
    id: str
    type: ChannelType = ChannelType.TEXT
    name: str | None = None
    parent_id: str | None = None


class Guild(ModelBase):
    id: str
    name: str | None = None
    avatar: str | None = None


class User(ModelBase):
    id: str
    name: str | None = None
    nick: str | None = None
    avatar: str | None = None
    is_bot: bool | None = None


class Friend(ModelBase):
    user: User | None = None
    nick: str | None = None

    @property
    def remark(self) -> str | None:
        return self.nick


class Role(ModelBase):
    id: str
    name: str | None = None

    @model_validator(mode="before")
    def parse_role(cls, raw):
        if isinstance(raw, str):
            return {"id": raw}
        return raw


class Member(ModelBase):
    user: User | None = None
    nick: str | None = None
    avatar: str | None = None
    joined_at: datetime | None = None
    roles: list[Role] = Field(default_factory=list)

    @field_validator("joined_at", mode="before")
    def parse_joined_at(cls, v):
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000)
        return v

    @field_serializer("joined_at", mode="plain")
    def serialize_joined_at(self, v: datetime | None) -> int | None:
        if v is not None:
            return int(v.timestamp() * 1000)
        return None


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


class Login(ModelBase):
    sn: int
    status: LoginStatus
    adapter: str
    platform: str
    user: User
    features: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    def parse_login(cls, raw):
        if isinstance(raw, dict):
            if "self_id" in raw and "user" not in raw:
                raw["user"] = {"id": raw["self_id"]}
            if "sn" not in raw:
                raw["sn"] = 0
            if "adapter" not in raw:
                raw["adapter"] = "satori"
            if "status" not in raw:
                raw["status"] = LoginStatus.ONLINE
        return raw

    @property
    def id(self) -> str:
        return self.user.id


class LoginPartial(Login):
    platform: str | None = None
    user: User | None = None


class ArgvInteraction(ModelBase):
    name: str
    arguments: list
    options: Any


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


class Identify(ModelBase):
    token: str | None = None
    sn: int | None = None

    @model_validator(mode="before")
    def parse_identify(cls, raw):
        if isinstance(raw, dict) and "sequence" in raw and "sn" not in raw:
            raw["sn"] = raw["sequence"]
        return raw

    @property
    def sequence(self) -> int | None:
        return self.sn


class Ready(ModelBase):
    logins: list[LoginPartial]
    proxy_urls: list[str] = Field(default_factory=list)


class MetaPayload(ModelBase):
    """Meta 信令"""

    proxy_urls: list[str]


class Meta(ModelBase):
    """Meta 数据"""

    logins: list[LoginPartial]
    proxy_urls: list[str] = Field(default_factory=list)


class EmojiObject(ModelBase):
    id: str
    name: str | None = None

    def to_element(self) -> Emoji:
        return Emoji(self.id, self.name)


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
    ):
        obj = cls(
            id=id,
            content="".join(str(i) for i in content),
            channel=channel,
            guild=guild,
            member=member,
            user=user,
            created_at=created_at,
            updated_at=updated_at,
            referrer=referrer,
        )
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

    @model_validator(mode="before")
    def parse_message(cls, raw):
        if isinstance(raw, dict) and "elements" in raw and "content" not in raw:
            content = [RawElement(*item.values()) for item in raw["elements"]]
            raw["content"] = "".join(str(i) for i in content)
        return raw

    @field_validator("created_at", mode="before")
    def parse_created_at(cls, v):
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000)
        return v

    @field_validator("updated_at", mode="before")
    def parse_updated_at(cls, v):
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000)
        return v

    @field_serializer("created_at", mode="plain")
    def serialize_created_at(self, v: datetime | None) -> int | None:
        if v is not None:
            return int(v.timestamp() * 1000)
        return None

    @field_serializer("updated_at", mode="plain")
    def serialize_updated_at(self, v: datetime | None) -> int | None:
        if v is not None:
            return int(v.timestamp() * 1000)
        return None


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

    @field_validator("timestamp", mode="before")
    def parse_timestamp(cls, v):
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000)
        return v

    @field_serializer("timestamp", mode="plain")
    def serialize_timestamp(self, v: datetime) -> int:
        return int(v.timestamp() * 1000)

    @model_validator(mode="before")
    def parse_event(cls, raw):
        if isinstance(raw, dict):
            if "id" in raw and "sn" not in raw:
                raw["sn"] = raw["id"]
            if "platform" in raw and "self_id" in raw and "login" not in raw:
                raw["login"] = {
                    "sn": 0,
                    "platform": raw["platform"],
                    "user": {"id": raw["self_id"]},
                    "status": LoginStatus.ONLINE,
                }
            if "self_id" in raw and not raw.get("login", {}).get("user"):
                if "login" not in raw:
                    raw["login"] = {"sn": 0, "status": LoginStatus.ONLINE, "platform": raw.get("platform", "unknown")}
                raw["login"]["user"] = {"id": raw["self_id"]}
        return raw

    @property
    def platform(self):
        return self.login.platform

    @property
    def self_id(self):
        return self.login.id


T = TypeVar("T", bound=ModelBase)


class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageResult[T]":
        data = [(parser or ModelBase.parse)(item) for item in raw["data"]]
        return cls(data=data, next=raw.get("next"))  # type: ignore


class PageDequeResult(PageResult[T]):
    prev: str | None = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T] | None = None) -> "PageDequeResult[T]":
        data = [(parser or ModelBase.parse)(item) for item in raw["data"]]
        return cls(data=data, next=raw.get("next"), prev=raw.get("prev"))  # type: ignore


class IterablePageResult(Generic[T], AsyncIterable[T], Awaitable[PageResult[T]]):
    def __init__(self, func: Callable[[str | None], Awaitable[PageResult[T]]], initial_page: str | None = None):
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
    def __init__(self, file: bytes | IO[bytes] | PathLike, mimetype: str = "image/png", name: str | None = None):
        self.file = file
        self.mimetype = mimetype

        if isinstance(self.file, PathLike):
            self.mimetype = mimetypes.guess_type(str(self.file))[0] or self.mimetype
            self.name = Path(self.file).name
        else:
            self.name = name

    def dump(self):
        file = self.file

        if isinstance(file, PathLike):
            file = open(file, "rb")

        return {"value": file, "filename": self.name, "content_type": self.mimetype}
