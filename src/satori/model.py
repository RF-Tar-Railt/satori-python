import mimetypes
from collections.abc import AsyncIterable, Awaitable
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from enum import IntEnum
from os import PathLike
from pathlib import Path
from typing import IO, Any, Callable, ClassVar, Generic, Literal, Optional, TypeVar, Union
from typing_extensions import TypeAlias

from .element import Element, transform
from .parser import Element as RawElement
from .parser import parse


@dataclass
class ModelBase:
    __converter__: ClassVar[dict[str, Callable[[Any], Any]]] = {}
    _raw_data: dict[str, Any] = field(init=False, default_factory=dict, repr=False, compare=False, hash=False)

    @classmethod
    def parse(cls, raw: dict):
        fs = fields(cls)
        data = {}
        for fd in fs:
            if fd.name in raw:
                if fd.name in cls.__converter__:
                    data[fd.name] = cls.__converter__[fd.name](raw[fd.name])
                else:
                    data[fd.name] = raw[fd.name]
        obj = cls(**data)  # type: ignore
        obj._raw_data = raw
        return obj

    def dump(self) -> dict:
        raise NotImplementedError


class ChannelType(IntEnum):
    TEXT = 0
    DIRECT = 1
    CATEGORY = 2
    VOICE = 3


@dataclass
class Channel(ModelBase):
    id: str
    type: ChannelType
    name: Optional[str] = None
    parent_id: Optional[str] = None

    __converter__ = {"type": ChannelType}

    def dump(self):
        res = {"id": self.id, "type": self.type.value}
        if self.name:
            res["name"] = self.name
        if self.parent_id:
            res["parent_id"] = self.parent_id
        return res


@dataclass
class Guild(ModelBase):
    id: str
    name: Optional[str] = None
    avatar: Optional[str] = None

    def dump(self):
        res = {"id": self.id}
        if self.name:
            res["name"] = self.name
        if self.avatar:
            res["avatar"] = self.avatar
        return res


@dataclass
class User(ModelBase):
    id: str
    name: Optional[str] = None
    nick: Optional[str] = None
    avatar: Optional[str] = None
    is_bot: Optional[bool] = None

    def dump(self):
        res: dict[str, Any] = {"id": self.id}
        if self.name:
            res["name"] = self.name
        if self.nick:
            res["nick"] = self.nick
        if self.avatar:
            res["avatar"] = self.avatar
        if self.is_bot:
            res["is_bot"] = self.is_bot
        return res


@dataclass
class Member(ModelBase):
    user: Optional[User] = None
    nick: Optional[str] = None
    avatar: Optional[str] = None
    joined_at: Optional[datetime] = None

    __converter__ = {"user": User.parse, "joined_at": lambda ts: datetime.fromtimestamp(int(ts) / 1000)}

    def dump(self):
        res = {}
        if self.user:
            res["user"] = self.user.dump()
        if self.nick:
            res["nick"] = self.nick
        if self.avatar:
            res["avatar"] = self.avatar
        if self.joined_at:
            res["joined_at"] = int(self.joined_at.timestamp() * 1000)
        return res


@dataclass
class Role(ModelBase):
    id: str
    name: Optional[str] = None

    def dump(self):
        res = {"id": self.id}
        if self.name:
            res["name"] = self.name
        return res


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


@dataclass
class Login(ModelBase):
    sn: int
    status: LoginStatus
    adapter: str
    platform: str
    user: User
    features: list[str] = field(default_factory=list)

    __converter__ = {"user": User.parse, "status": LoginStatus}

    def dump(self):
        res: dict[str, Any] = {
            "sn": self.sn,
            "status": self.status.value,
            "adapter": self.adapter,
        }
        if self.platform:
            res["platform"] = self.platform
        if self.user:
            res["user"] = self.user.dump()
        if self.features:
            res["features"] = self.features
        return res

    @classmethod
    def parse(cls, raw: dict):
        if "self_id" in raw and "user" not in raw:
            raw["user"] = {"id": raw["self_id"]}
        if "sn" not in raw:
            raw["sn"] = 0
        if "adapter" not in raw:
            raw["adapter"] = "satori"
        if "status" not in raw:
            raw["status"] = LoginStatus.ONLINE
        return super().parse(raw)

    @property
    def id(self) -> str:
        return self.user.id


@dataclass
class LoginPartial(Login):
    platform: Optional[str] = None
    user: Optional[User] = None


@dataclass
class ArgvInteraction(ModelBase):
    name: str
    arguments: list
    options: Any

    def dump(self):
        return asdict(self)


@dataclass
class ButtonInteraction(ModelBase):
    id: str

    def dump(self):
        return asdict(self)


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


@dataclass
class Identify(ModelBase):
    token: Optional[str] = None
    sn: Optional[int] = None

    @classmethod
    def parse(cls, raw: dict):
        if "sequence" in raw and "sn" not in raw:
            raw["sn"] = raw["sequence"]
        return super().parse(raw)

    @property
    def sequence(self) -> Optional[int]:
        return self.sn

    def dump(self):
        return asdict(self)


@dataclass
class Ready(ModelBase):
    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)

    __converter__ = {"logins": lambda raw: [LoginPartial.parse(login) for login in raw]}

    def dump(self):
        return asdict(self)


@dataclass
class MetaPayload(ModelBase):
    """Meta 信令"""

    proxy_urls: list[str]

    def dump(self):
        return asdict(self)


@dataclass
class Meta(ModelBase):
    """Meta 数据"""

    logins: list[LoginPartial]
    proxy_urls: list[str] = field(default_factory=list)

    __converter__ = {"logins": lambda raw: [LoginPartial.parse(login) for login in raw]}

    def dump(self):
        return asdict(self)


@dataclass
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
    ):
        return cls(id, "".join(str(i) for i in content), channel, guild, member, user, created_at, updated_at)

    @property
    def message(self) -> list[Element]:
        return transform(parse(self.content))

    @message.setter
    def message(self, value: list[Element]):
        self.content = "".join(str(i) for i in value)

    @classmethod
    def parse(cls, raw: dict):
        if "elements" in raw and "content" not in raw:
            content = [RawElement(*item.values()) for item in raw["elements"]]
            raw["content"] = "".join(str(i) for i in content)
        return super().parse(raw)

    __converter__ = {
        "channel": Channel.parse,
        "guild": Guild.parse,
        "member": Member.parse,
        "user": User.parse,
        "created_at": lambda ts: datetime.fromtimestamp(int(ts) / 1000),
        "updated_at": lambda ts: datetime.fromtimestamp(int(ts) / 1000),
    }

    def dump(self):
        res: dict[str, Any] = {"id": self.id, "content": self.content}
        if self.channel:
            res["channel"] = self.channel.dump()
        if self.guild:
            res["guild"] = self.guild.dump()
        if self.member:
            res["member"] = self.member.dump()
        if self.user:
            res["user"] = self.user.dump()
        if self.created_at:
            res["created_at"] = int(self.created_at.timestamp() * 1000)
        if self.updated_at:
            res["updated_at"] = int(self.updated_at.timestamp() * 1000)
        return res


@dataclass
class MessageReceipt(ModelBase):
    id: str
    content: Optional[str] = None

    @classmethod
    def from_elements(
        cls,
        id: str,
        content: Optional[list[Element]] = None,
    ):
        return cls(id, "".join(str(i) for i in content) if content else None)

    @property
    def message(self) -> Optional[list[Element]]:
        return transform(parse(self.content)) if self.content else None

    @message.setter
    def message(self, value: Optional[list[Element]]):
        self.content = "".join(str(i) for i in value) if value else None

    @classmethod
    def parse(cls, raw: dict):
        if "elements" in raw and "content" not in raw:
            content = [RawElement(*item.values()) for item in raw["elements"]]
            raw["content"] = "".join(str(i) for i in content)
        return super().parse(raw)

    def dump(self):
        res = {"id": self.id}
        if self.content:
            res["content"] = self.content
        return res


@dataclass
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

    __converter__ = {
        "timestamp": lambda ts: datetime.fromtimestamp(int(ts) / 1000),
        "argv": ArgvInteraction.parse,
        "button": ButtonInteraction.parse,
        "channel": Channel.parse,
        "guild": Guild.parse,
        "login": Login.parse,
        "member": Member.parse,
        "message": MessageObject.parse,
        "operator": User.parse,
        "role": Role.parse,
        "user": User.parse,
    }

    @classmethod
    def parse(cls, raw: dict):
        if "id" in raw and "sn" not in raw:
            raw["sn"] = raw["id"]
        if "platform" in raw and "self_id" in raw and "login" not in raw:
            raw["login"] = {
                "sn": 0,
                "platform": raw["platform"],
                "user": {"id": raw["self_id"]},
                "status": LoginStatus.ONLINE,
            }
        return super().parse(raw)

    @property
    def platform(self):
        return self.login.platform

    @property
    def self_id(self):
        return self.login.id

    def dump(self):
        res = {
            "sn": self.sn,
            "type": self.type,
            "timestamp": int(self.timestamp.timestamp() * 1000),
            "login": self.login.dump(),
        }
        if self.argv:
            res["argv"] = self.argv.dump()
        if self.button:
            res["button"] = self.button.dump()
        if self.channel:
            res["channel"] = self.channel.dump()
        if self.guild:
            res["guild"] = self.guild.dump()
        if self.login:
            res["login"] = self.login.dump()
        if self.member:
            res["member"] = self.member.dump()
        if self.message:
            res["message"] = self.message.dump()
        if self.operator:
            res["operator"] = self.operator.dump()
        if self.role:
            res["role"] = self.role.dump()
        if self.user:
            res["user"] = self.user.dump()
        if self._type:
            res["_type"] = self._type
        if self._data:
            res["_data"] = self._data
        return res


T = TypeVar("T", bound=ModelBase)


@dataclass
class PageResult(ModelBase, Generic[T]):
    data: list[T]
    next: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict, parser: Optional[Callable[[dict], T]] = None) -> "PageResult[T]":
        data = [(parser or ModelBase.parse)(item) for item in raw["data"]]
        return cls(data, raw.get("next"))  # type: ignore

    def dump(self):
        res: dict = {"data": [item.dump() for item in self.data]}
        if self.next:
            res["next"] = self.next
        return res


@dataclass
class PageDequeResult(PageResult[T]):
    prev: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict, parser: Optional[Callable[[dict], T]] = None) -> "PageDequeResult[T]":
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
        self, func: Callable[[Optional[str]], Awaitable[PageResult[T]]], initial_page: Optional[str] = None
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


@dataclass
class Upload:
    file: Union[bytes, IO[bytes], PathLike]
    mimetype: str = "image/png"
    name: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.file, PathLike):
            self.mimetype = mimetypes.guess_type(str(self.file))[0] or self.mimetype
            self.name = Path(self.file).name

    def dump(self):
        file = self.file

        if isinstance(file, PathLike):
            file = open(file, "rb")

        return {"value": file, "filename": self.name, "content_type": self.mimetype}
