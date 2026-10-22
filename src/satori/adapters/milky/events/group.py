from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Member, Role, User

from ..utils import group_avatar, user_avatar
from .base import register_event


@register_event("group_member_increase")
async def group_member_increase(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id, ChannelType.TEXT)
    if data["user_id"] == raw["self_id"]:
        return Event(
            EventType.GUILD_ADDED,
            datetime.now(),
            login=login,
            user=login.user,
            member=Member(login.user, avatar=user_avatar(data["user_id"]), roles=[Role("member", "群成员")]),
            guild=guild,
            channel=channel,
        )
    user = User(str(data["user_id"]), avatar=user_avatar(data["user_id"]))
    member = Member(user, avatar=user.avatar, roles=[Role("member", "群成员")])
    operator = None
    if data.get("operator_id"):
        operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
    return Event(
        EventType.GUILD_MEMBER_ADDED,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        operator=operator,
    )


@register_event("group_member_decrease")
async def group_member_decrease(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id, ChannelType.TEXT)
    if data["user_id"] == raw["self_id"]:
        return Event(
            EventType.GUILD_REMOVED,
            datetime.now(),
            login=login,
            user=login.user,
            member=Member(login.user, avatar=user_avatar(data["user_id"]), roles=[Role("member", "群成员")]),
            guild=guild,
            channel=channel,
        )
    user = User(str(data["user_id"]), avatar=user_avatar(data["user_id"]))
    member = Member(user, avatar=user.avatar)
    operator = None
    if data.get("operator_id"):
        operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
    return Event(
        EventType.GUILD_MEMBER_REMOVED,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        operator=operator,
    )


@register_event("group_disband")
async def group_disband(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id, ChannelType.TEXT)
    operator = None
    if data.get("operator_id"):
        operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
    return Event(
        EventType.GUILD_REMOVED,
        datetime.now(),
        login,
        guild=guild,
        channel=channel,
        operator=operator,
    )


@register_event("group_name_change")
async def group_name_change(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, name=data.get("new_group_name"), avatar=group_avatar(guild_id))
    channel = Channel(guild_id, ChannelType.TEXT, name=data.get("new_group_name"))
    operator = None
    if data.get("operator_id"):
        operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
    return Event(
        EventType.GUILD_UPDATED,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        operator=operator,
    )
