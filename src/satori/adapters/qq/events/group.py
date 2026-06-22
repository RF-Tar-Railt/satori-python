from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Member, User

from ..utils import USER_AVATAR_URL, Payload
from .base import register_event


@register_event("FRIEND_ADD")
@register_event("FRIEND_DEL")
async def friend_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    t = {
        "FRIEND_ADD": EventType.FRIEND_ADDED,
        "FRIEND_DEL": EventType.FRIEND_REMOVED,
    }[payload.type or ""]
    app_id = net.bot_id_mapping[login.id]
    user = User(raw["openid"], avatar=USER_AVATAR_URL.format(app_id=app_id, user_id=raw["openid"]))
    return Event(
        t,
        (
            datetime.fromtimestamp(int(raw["timestamp"]))
            if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit()
            else datetime.fromisoformat(str(raw["timestamp"]))
        ),
        login,
        user=user,
        channel=Channel(f"private:{user.id}", type=ChannelType.DIRECT),
        referrer={"event_id": payload.id},
    )


@register_event("GROUP_ADD_ROBOT")
@register_event("GROUP_DEL_ROBOT")
async def group_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    if "group_openid" in raw:
        guild = Guild(raw["group_openid"])
    else:
        guild = Guild(raw["group_id"])
    app_id = net.bot_id_mapping[login.id]
    operator = User(
        raw["op_member_openid"], avatar=USER_AVATAR_URL.format(app_id=app_id, user_id=raw["op_member_openid"])
    )
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
        channel=Channel(guild.id, type=ChannelType.TEXT),
        operator=operator,
        referrer={"event_id": payload.id},
    )


@register_event("GROUP_MEMBER_ADD")
@register_event("GROUP_MEMBER_REMOVE")
async def group_member_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    if "group_openid" in raw:
        guild = Guild(raw["group_openid"])
    else:
        guild = Guild(raw["group_id"])
    app_id = net.bot_id_mapping[login.id]
    member = User(raw["member_openid"], avatar=USER_AVATAR_URL.format(app_id=app_id, user_id=raw["member_openid"]))
    t = {
        "GROUP_MEMBER_ADD": EventType.GUILD_MEMBER_ADDED,
        "GROUP_MEMBER_REMOVE": EventType.GUILD_MEMBER_REMOVED,
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
        channel=Channel(guild.id, type=ChannelType.TEXT),
        user=member,
        member=Member(user=member, avatar=member.avatar),
        referrer={"event_id": payload.id},
    )
