from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Callable, Generic, List, Optional, TypeVar

from .element import Element, transform
from .parser import parse


class ChannelType(IntEnum):
    TEXT = 0
    VOICE = 1
    CATEGORY = 2
    DIRECT = 3


@dataclass
class Channel:
    id: str
    type: ChannelType
    name: Optional[str] = None
    parent_id: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict):
        data = raw.copy()
        data["type"] = ChannelType(raw["type"])
        return cls(**data)

    def dump(self):
        res = {"id": self.id, "type": self.type.value}
        if self.name:
            res["name"] = self.name
        if self.parent_id:
            res["parent_id"] = self.parent_id
        return res


@dataclass
class Guild:
    id: str
    name: Optional[str] = None
    avatar: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict):
        return cls(**raw)

    def dump(self):
        res = {"id": self.id}
        if self.name:
            res["name"] = self.name
        if self.avatar:
            res["avatar"] = self.avatar
        return res


@dataclass
class User:
    id: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    is_bot: Optional[bool] = None

    @classmethod
    def parse(cls, raw: dict):
        return cls(**raw)

    def dump(self):
        res = {"id": self.id}
        if self.name:
            res["name"] = self.name
        if self.avatar:
            res["avatar"] = self.avatar
        if self.is_bot:
            res["is_bot"] = self.is_bot
        return res


@dataclass
class Member:
    user: Optional[User] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    joined_at: Optional[datetime] = None

    @classmethod
    def parse(cls, raw: dict):
        data = raw.copy()
        if "user" in raw:
            data["user"] = User(**raw["user"])
        if "joined_at" in raw:
            data["joined_at"] = datetime.fromtimestamp(int(raw["joined_at"]) / 1000)
        return cls(**data)

    def dump(self):
        res = {}
        if self.user:
            res["user"] = self.user.dump()
        if self.name:
            res["name"] = self.name
        if self.avatar:
            res["avatar"] = self.avatar
        if self.joined_at:
            res["joined_at"] = int(self.joined_at.timestamp() * 1000)
        return res


@dataclass
class Role:
    id: str
    name: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict):
        return cls(**raw)

    def dump(self):
        res = {"id": self.id}
        if self.name:
            res["name"] = self.name
        return res


class LoginStatus(IntEnum):
    OFFLINE = 0
    ONLINE = 1
    CONNECT = 2
    DISCONNECT = 3
    RECONNECT = 4


@dataclass
class Login:
    status: LoginStatus
    user: Optional[User] = None
    self_id: Optional[str] = None
    platform: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict):
        data = raw.copy()
        if "user" in raw:
            data["user"] = User(**raw["user"])
        data["status"] = LoginStatus(data["status"])
        return cls(**data)

    def dump(self):
        res = {"status": self.status.value}
        if self.user:
            res["user"] = self.user.dump()
        if self.self_id:
            res["self_id"] = self.self_id
        if self.platform:
            res["platform"] = self.platform
        return res


class Opcode(IntEnum):
    EVENT = 0
    PING = 1
    PONG = 2
    IDENTIFY = 3
    READY = 4


@dataclass
class Identify:
    token: Optional[str] = None
    sequence: Optional[int] = None


@dataclass
class Ready:
    logins: List[Login]


@dataclass
class Message:
    id: str
    content: List[Element]
    channel: Optional[Channel] = None
    guild: Optional[Guild] = None
    member: Optional[Member] = None
    user: Optional[User] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def parse(cls, raw: dict):
        data = {
            "id": raw["id"],
            "content": transform(parse(raw["content"])),
        }
        if "channel" in raw:
            data["channel"] = Channel(**raw["channel"])
        if "guild" in raw:
            data["guild"] = Guild(**raw["guild"])
        if "member" in raw:
            data["member"] = Member.parse(raw["member"])
        if "user" in raw:
            data["user"] = User(**raw["user"])
        if "created_at" in raw:
            data["created_at"] = datetime.fromtimestamp(int(raw["created_at"]) / 1000)
        if "updated_at" in raw:
            data["updated_at"] = datetime.fromtimestamp(int(raw["updated_at"]) / 1000)
        return cls(**data)

    def dump(self):
        res = {"id": self.id, "content": "".join(map(str, self.content))}
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
class Event:
    id: int
    type: str
    platform: str
    self_id: str
    timestamp: datetime
    channel: Optional[Channel] = None
    guild: Optional[Guild] = None
    login: Optional[Login] = None
    member: Optional[Member] = None
    message: Optional[Message] = None
    operator: Optional[User] = None
    role: Optional[Role] = None
    user: Optional[User] = None

    @classmethod
    def parse(cls, raw: dict):
        data = {
            "id": raw["id"],
            "type": raw["type"],
            "platform": raw["platform"],
            "self_id": raw["self_id"],
            "timestamp": datetime.fromtimestamp(int(raw["timestamp"]) / 1000),
        }
        if "channel" in raw:
            data["channel"] = Channel(**raw["channel"])
        if "guild" in raw:
            data["guild"] = Guild(**raw["guild"])
        if "login" in raw:
            data["login"] = Login.parse(raw["login"])
        if "member" in raw:
            data["member"] = Member.parse(raw["member"])
        if "message" in raw:
            data["message"] = Message.parse(raw["message"])
        if "operator" in raw:
            data["operator"] = User(**raw["operator"])
        if "role" in raw:
            data["role"] = Role(**raw["role"])
        if "user" in raw:
            data["user"] = User(**raw["user"])
        return cls(**data)

    def dump(self):
        res = {
            "id": self.id,
            "type": self.type,
            "platform": self.platform,
            "self_id": self.self_id,
            "timestamp": int(self.timestamp.timestamp() * 1000),
        }
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
        return res


T = TypeVar("T")


@dataclass
class PageResult(Generic[T]):
    data: List[T]
    next: Optional[str] = None

    @classmethod
    def parse(cls, raw: dict, parser: Callable[[dict], T]) -> "PageResult[T]":
        data = [parser(item) for item in raw["data"]]
        return cls(data, raw.get("next"))
