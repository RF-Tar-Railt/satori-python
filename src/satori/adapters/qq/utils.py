from collections import UserDict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Literal, Protocol, TypeVar
from urllib.parse import urlparse
from urllib.request import url2pathname

from aiohttp import ClientResponse, ClientSession

from satori.model import Channel, ChannelType, Guild, Member, Role, User

from .exception import ActionFailed, ApiNotAvailable, AuditException, RateLimitException, UnauthorizedException

CallMethod = Literal["get", "post", "fetch", "update", "multipart", "put", "delete", "patch"]


class QQBotNetwork(Protocol):
    session: ClientSession

    @property
    def bot_id_mapping(self) -> dict[str, str]: ...

    async def call_api(self, method: CallMethod, action: str, params: dict | None = None) -> dict: ...


class Opcode(int, Enum):
    DISPATCH = 0
    """[Receive] 服务端进行消息推送"""
    HEARTBEAT = 1
    """[Send/Receive] 客户端或服务端发送心跳"""
    IDENTIFY = 2
    """[Send] 客户端发送鉴权"""
    RESUME = 6
    """[Send] 客户端恢复连接"""
    RECONNECT = 7
    """[Receive] 服务端通知客户端重新连接"""
    INVALID_SESSION = 9
    """[Receive] 当 identify 或 resume 的时候，如果参数有错，服务端会返回该消息"""
    HELLO = 10
    """[Receive] 当客户端与网关建立 ws 连接之后，网关下发的第一条消息"""
    HEARTBEAT_ACK = 11
    """[Receive/Reply] 服务端回应心跳"""
    HTTP_CALLBACK_ACK = 12
    """[Reply] 仅用于 http 回调模式的回包，代表机器人收到了平台推送的数据"""
    SERVER_VERIFY = 13
    """[Receive] 开放平台对机器人服务端进行验证"""


@dataclass
class Payload:
    op: int | Opcode
    d: dict | None = None
    s: int | None = None
    t: str | None = None
    id: str | None = None

    @property
    def opcode(self) -> Opcode:
        return Opcode(self.op)

    @property
    def data(self) -> dict:
        return self.d or {}

    @property
    def sequence(self) -> int | None:
        return self.s

    @property
    def type(self) -> str | None:
        return self.t


async def validate_response(resp: ClientResponse):
    status = resp.status
    if status == 200 or 203 <= status < 300:
        try:
            data = await resp.json(content_type=None)
        except JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return data.get("data", data)
    if status in {201, 202}:
        data = await resp.json()
        if (
            data
            and data.get("code") == 304023
            and (audit_id := data.get("data", {}).get("message_audit", {}).get("audit_id"))
        ):
            exc = AuditException(audit_id)
        else:
            exc = ActionFailed(status, resp.headers, await resp.text())
    elif status == 401:
        exc = UnauthorizedException(status, resp.headers, await resp.text())
    elif status in {404, 405}:
        exc = ApiNotAvailable(status, resp.headers, await resp.text())
    elif status == 429:
        exc = RateLimitException(status, resp.headers, await resp.text())
    else:
        exc = ActionFailed(status, resp.headers, await resp.text())
    raise exc


def decode_guild(profile: dict) -> Guild:
    return Guild(
        profile["id"],
        name=profile["name"],
        avatar=profile["icon"],
    )


def decode_channel(profile: dict) -> Channel:
    return Channel(
        id=profile["id"],
        name=profile.get("name", ""),
        type={0: ChannelType.TEXT, 2: ChannelType.VOICE, 4: ChannelType.CATEGORY}.get(
            profile["type"], ChannelType.TEXT
        ),
        parent_id=profile["parent_id"],
    )


def decode_user(profile: dict) -> User:
    return User(
        profile["id"],
        profile.get("username"),
        avatar=profile.get("avatar"),
        is_bot=profile.get("bot", False),
    )


def decode_member(profile: dict) -> Member:
    return Member(
        decode_user(profile["user"]) if "user" in profile else None,
        profile.get("nick"),
        joined_at=datetime.fromisoformat(profile["joined_at"]) if "joined_at" in profile else None,
        roles=[(ROLE_MAPPING.get(r) or Role(r)) for r in profile["roles"]],
    )


def decode_group(profile: dict) -> tuple[Guild, Channel]:
    group_openid = profile["group_openid"]
    guild = Guild(group_openid, profile.get("group_name"))
    channel = Channel(group_openid, ChannelType.TEXT, profile.get("group_name"), parent_id=None)
    return guild, channel


def decode_group_user(profile: dict, app_id: str) -> User:
    user_id = profile.get("user_openid") or profile.get("member_openid") or profile["id"]
    return User(
        user_id,
        profile.get("username"),
        avatar=USER_AVATAR_URL.format(app_id=app_id, user_id=user_id),
        is_bot=profile.get("bot", False),
    )


def decode_group_member(profile: dict, app_id: str) -> Member:
    user = decode_group_user(profile, app_id)
    return Member(
        user,
        profile.get("nick"),
        avatar=user.avatar,
        joined_at=datetime.fromisoformat(profile["joined_at"]) if "joined_at" in profile else None,
        roles=[ROLE_MAPPING[profile.get("member_role", "member")]],
    )


USER_AVATAR_URL = "https://q.qlogo.cn/qqapp/{app_id}/{user_id}/640"


ROLE_MAPPING = {
    "1": Role("member", "成员"),
    "5": Role("channel_admin", "子频道管理员"),
    "2": Role("admin", "管理员"),
    "4": Role("owner", "创建者"),
    "member": Role("member", "成员"),
    "owner": Role("owner", "群主"),
    "admin": Role("admin", "管理员"),
}


def parse_file_uri(uri):
    """解析 file URI 为 Path 对象"""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"不是 file URI: {uri}")

    path = url2pathname(parsed.path)

    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"

    return Path(path)


K = TypeVar("K")
V = TypeVar("V")


class DequeDict(UserDict[K, V]):
    """一个带有最大长度的字典，超过最大长度时会删除最旧的条目"""

    def __init__(self, maxlen: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxlen = maxlen
        self._order = deque(self.data.keys(), maxlen=maxlen)

    def __setitem__(self, key: K, item: V):
        if key not in self.data and len(self.data) >= self.maxlen:
            oldest_key = self._order.popleft()
            del self.data[oldest_key]
        self.data[key] = item
        if key not in self._order:
            self._order.append(key)

    def __delitem__(self, key):
        super().__delitem__(key)
        self._order.remove(key)
