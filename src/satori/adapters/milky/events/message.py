from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, MessageObject, User

from ..message import decode_message
from ..utils import group_avatar, user_avatar
from .base import register_event


@register_event("message_receive")
async def message_receive(login, net, raw):
    message = await decode_message(net, raw["data"])
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(raw["time"]),
        login,
        channel=message.channel,
        guild=message.guild,
        member=message.member,
        user=message.user,
        message=message,
    )


@register_event("message_recall")
async def message_recall(login, net, raw):
    data = raw["data"]
    scene = data["message_scene"]
    peer_id = str(data["peer_id"])
    if scene == "group":
        channel = Channel(peer_id, ChannelType.TEXT)
        guild = Guild(peer_id, avatar=group_avatar(peer_id))
    elif scene == "temp":
        channel = Channel(f"private:temp_{peer_id}", ChannelType.DIRECT)
        guild = None
    else:
        channel = Channel(f"private:{peer_id}", ChannelType.DIRECT)
        guild = None
    user = User(str(data["sender_id"]), avatar=user_avatar(data["sender_id"]))
    operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
    message = MessageObject(str(data["message_seq"]), "", channel=channel, guild=guild, user=user)
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.fromtimestamp(raw["time"]),
        login,
        channel=channel,
        guild=guild,
        user=user,
        operator=operator,
        message=message,
    )


@register_event("group_message_reaction")
async def group_message_reaction(login, net, raw):
    data = raw["data"]
    guild_id = str(data["group_id"])
    guild = Guild(guild_id, avatar=group_avatar(guild_id))
    channel = Channel(guild_id, ChannelType.TEXT)
    user = User(str(data["user_id"]), avatar=user_avatar(data["user_id"]))
    face_id = data["face_id"]
    message = MessageObject(
        str(data["message_seq"]), f"<milky:face id='{face_id}'>", channel=channel, guild=guild, user=user
    )
    if data["is_add"]:
        event_type = EventType.REACTION_ADDED
    else:
        event_type = EventType.REACTION_REMOVED
    return Event(
        event_type,
        datetime.fromtimestamp(raw["time"]),
        login,
        channel=channel,
        guild=guild,
        user=user,
        message=message,
    )
