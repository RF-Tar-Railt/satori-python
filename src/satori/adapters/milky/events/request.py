from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Member, MessageObject, User

from ..utils import group_avatar, user_avatar
from .base import register_event


@register_event("friend_request")
async def friend_request(login, net, raw):
    data = raw["data"]
    user = User(str(data["initiator_id"]), avatar=user_avatar(data["initiator_id"]))
    channel = Channel(f"private:{user.id}", ChannelType.DIRECT)
    message_id = f"{data['initiator_uid']}|{1 if data.get('is_filtered') else 0}"
    message = MessageObject(message_id, data.get("comment", ""))
    return Event(
        EventType.FRIEND_REQUEST,
        datetime.fromtimestamp(raw["time"]),
        login,
        user=user,
        channel=channel,
        message=message,
    )


@register_event("group_join_request")
async def group_join_request(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id)
    user = User(str(data["initiator_id"]), avatar=user_avatar(data["initiator_id"]))
    member = Member(user, avatar=user_avatar(data["initiator_id"]))
    message_id = f"{data['notification_seq']}|join_request|{guild_id}|{1 if data.get('is_filtered') else 0}"
    message = MessageObject(message_id, data.get("comment", ""))
    return Event(
        EventType.GUILD_MEMBER_REQUEST,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        message=message,
    )


@register_event("group_invited_join_request")
async def group_invited_join_request(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id)
    user = User(str(data["target_user_id"]), avatar=user_avatar(data["target_user_id"]))
    member = Member(user, avatar=user.avatar)
    message_id = f"{data['notification_seq']}|invited_join_request|{guild_id}|0"
    message = MessageObject(message_id, "")
    operator = User(str(data["initiator_id"]), avatar=user_avatar(data["initiator_id"]))
    return Event(
        EventType.GUILD_MEMBER_REQUEST,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        operator=operator,
        message=message,
    )


@register_event("group_invitation")
async def group_invitation(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id)
    user = User(str(data["initiator_id"]), avatar=user_avatar(data["initiator_id"]))
    message_id = f"{guild_id}|{data['invitation_seq']}"
    message = MessageObject(message_id, "")
    return Event(
        EventType.GUILD_REQUEST,
        datetime.fromtimestamp(raw["time"]),
        login,
        guild=guild,
        channel=channel,
        user=user,
        message=message,
    )
