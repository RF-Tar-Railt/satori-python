from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Event, Guild, User

from ..utils import Payload
from .base import register_event


@register_event("FRIEND_ADD")
@register_event("FRIEND_DEL")
async def friend_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    t = {
        "FRIEND_ADD": EventType.FRIEND_ADDED,
        "FRIEND_DEL": EventType.FRIEND_REMOVED,
    }[payload.type or ""]
    user = User(raw["openid"])
    return Event(
        t,
        (
            datetime.fromtimestamp(int(raw["timestamp"]))
            if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit()
            else datetime.fromisoformat(str(raw["timestamp"]))
        ),
        login,
        user=user,
    )


@register_event("GROUP_ADD_ROBOT")
@register_event("GROUP_DEL_ROBOT")
async def group_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    if "group_openid" in raw:
        guild = Guild(raw["group_openid"])
    else:
        guild = Guild(raw["guild_id"])
    operator = User(raw["op_member_openid"])
    t = {
        "GROUP_ADD_ROBOT": EventType.GUILD_ADDED,
        "GROUP_DEL_ROBOT": EventType.GUILD_REMOVED,
    }[payload.type or ""]
    return Event(
        t,
        (
            datetime.fromtimestamp(int(raw["timestamp"]))
            if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit()
            else datetime.fromisoformat(str(raw["timestamp"]))
        ),
        login,
        guild=guild,
        operator=operator,
    )
