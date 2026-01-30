from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Event, Guild, User, Member, Role

from ..utils import decode_user, decode_channel, decode_guild, Payload
from .base import register_event


@register_event("CHANNEL_CREATE")
@register_event("CHANNEL_UPDATE")
@register_event("CHANNEL_DELETE")
async def channel_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    guild = Guild(raw["guild_id"])
    channel = decode_channel(raw)
    t = {
        "CHANNEL_CREATE": EventType.CHANNEL_ADDED,
        "CHANNEL_UPDATE": EventType.CHANNEL_UPDATED,
        "CHANNEL_DELETE": EventType.CHANNEL_REMOVED,
    }[payload.type or ""]
    operator = User(raw["op_user_id"])
    return Event(
        t,
        datetime.now(),
        guild_login,
        channel=channel,
        guild=guild,
        operator=operator
    )


@register_event("GUILD_CREATE")
@register_event("GUILD_UPDATE")
@register_event("GUILD_DELETE")
async def guild_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    guild = decode_guild(raw)
    t = {
        "GUILD_CREATE": EventType.GUILD_ADDED,
        "GUILD_UPDATE": EventType.GUILD_UPDATED,
        "GUILD_DELETE": EventType.GUILD_REMOVED,
    }[payload.type or ""]
    operator = User(raw["op_user_id"])
    return Event(
        t,
        datetime.now(),
        guild_login,
        guild=guild,
        operator=operator
    )


@register_event("GUILD_MEMBER_ADD")
@register_event("GUILD_MEMBER_UPDATE")
@register_event("GUILD_MEMBER_DELETE")
async def guild_member_event(login, guild_login, net, payload: Payload):
    raw = payload.data
    guild = Guild(raw["guild_id"])
    t = {
        "GUILD_MEMBER_ADD": EventType.GUILD_MEMBER_ADDED,
        "GUILD_MEMBER_UPDATE": EventType.GUILD_MEMBER_UPDATED,
        "GUILD_MEMBER_DELETE": EventType.GUILD_MEMBER_REMOVED,
    }[payload.type or ""]
    user = decode_user(raw["user"])
    member = Member(
        user,
        nick=raw["nick"],
        avatar=user.avatar,
        joined_at=datetime.fromisoformat(raw["joined_at"]),
    )
    role = Role(raw["roles"][0])
    operator = User(raw["op_user_id"])
    return Event(
        t,
        datetime.now(),
        guild_login,
        guild=guild,
        user=user,
        member=member,
        operator=operator,
        role=role
    )
