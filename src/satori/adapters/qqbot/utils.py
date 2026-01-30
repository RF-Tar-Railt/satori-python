from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, Literal

from aiohttp import ClientResponse

from .exception import ActionFailed, ApiNotAvailable, UnauthorizedException, AuditException, RateLimitException
from ... import User, Guild, Channel, ChannelType, Member

CallMethod = Literal["get", "post", "fetch", "update", "multipart", "put", "delete", "patch"]


class QQBotNetwork(Protocol):
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
        data = await resp.json()
        return data.get("data", data)
    if status in {201, 202}:
        data = await resp.json()
        if data and (audit_id := data.get("data", {}).get("message_audit", {}).get("audit_id")):
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
        type={
            0: ChannelType.TEXT,
            2: ChannelType.VOICE,
            4: ChannelType.CATEGORY
        }.get(profile["type"], ChannelType.TEXT),
        parent_id=profile["parent_id"],
    )


def decode_user(profile: dict) -> User:
    return User(
        profile["id"],
        profile["username"],
        avatar=profile.get("avatar"),
        is_bot=profile.get("bot", False),
    )


def decode_member(profile: dict) -> Member:
    return Member(
        decode_user(profile["user"]) if "user" in profile else None,
        profile.get("nick"),
        joined_at=datetime.fromisoformat(profile["joined_at"]) if "joined_at" in profile else None,
    )


USER_AVATAR_URL = "https://q.qlogo.cn/qqapp/{app_id}/{user_id}/100"


# ROLE_MAPPING = {
#     "member": Role("MEMBER", "群成员"),
#     "admin": Role("ADMINISTRATOR", "管理员"),
#     "owner": Role("OWNER", "群主"),
# }
