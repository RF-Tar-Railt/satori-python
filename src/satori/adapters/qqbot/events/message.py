from __future__ import annotations

from datetime import datetime

from example.client3 import avatars
from satori import EventType, Quote, At, Text
from satori.model import MessageObject, Channel, ChannelType, Event, Guild, MessageObject, User, Member, Role

from ..message import decode_segments
from ..utils import decode_user, USER_AVATAR_URL, Payload
from .base import register_event


@register_event("AT_MESSAGE_CREATE")
@register_event("MESSAGE_CREATE")
async def at_message(login, guild_login, net, payload: Payload):
    raw = payload.data
    guild = Guild(raw["guild_id"])
    channel = Channel(raw["channel_id"], ChannelType.TEXT, parent_id=guild.id)
    user = decode_user(raw["author"])
    member = Member(
        user,
        avatar=user.avatar,
        joined_at=datetime.fromisoformat(raw["member"]["joined_at"]),
    )
    role = Role(raw["member"]["roles"][0])
    msg = decode_segments(raw)
    if payload.type == "AT_MESSAGE_CREATE" and len(msg) >= 2 and isinstance(msg[1], Text):
        text = msg[1].text.lstrip()
        if not text:
            msg.pop(1)
        else:
            msg[1] = Text(text)

    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(raw["timestamp"]),
        guild_login,
        channel=channel,
        guild=guild,
        member=member,
        user=user,
        message=MessageObject.from_elements(
            raw["id"], msg
        ),
        role=role,
        referrer={
            "msg_id": raw["id"],
            "msg_seq": -1,
        }
    )

@register_event("GROUP_AT_MESSAGE_CREATE")
async def group_at_message_create(login, guild_login, net, payload: Payload):
    raw = payload.data
    if "group_openid" in raw:
        channel = Channel(raw["group_openid"], ChannelType.TEXT)
    else:
        channel = Channel(raw["group_id"], ChannelType.TEXT)
    app_id = net.adapter.bot_id_mapping[login.id]
    if "member_openid" in raw:
        user = User(raw["member_openid"], avatar=USER_AVATAR_URL.format(app_id, user_id=raw["member_openid"]))
    else:
        user = User(raw["id"], avatar=USER_AVATAR_URL.format(app_id, user_id=raw["id"]))
    member = Member(user, avatar=user.avatar)
    msg = decode_segments(raw)
    msg.insert(0, At(login.id))
    if isinstance(msg[1], Text):
        text = msg[1].text.lstrip()
        if not text:
            msg.pop(1)
        else:
            msg[1] = Text(text)
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(raw["timestamp"]),
        login,
        channel=channel,
        guild=Guild(channel.id),
        member=member,
        user=user,
        message=MessageObject.from_elements(
            raw["id"], msg
        ),
        referrer={
            "msg_id": raw["id"],
            "msg_seq": -1,
        }
    )


@register_event("DIRECT_MESSAGE_CREATE")
async def direct_message_create(login, guild_login, net, payload: Payload):
    raw = payload.data
    guild = Guild(f"{raw['src_guild_id']}_{raw['guild_id']}")
    channel = Channel(f"{raw['guild_id']}_{raw['channel_id']}", ChannelType.DIRECT)
    user = decode_user(raw["author"])
    member = Member(
        user,
        avatar=user.avatar,
        joined_at=datetime.fromisoformat(raw["member"]["joined_at"]),
    )
    role = Role(raw["member"]["roles"][0])
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(raw["timestamp"]),
        guild_login,
        channel=channel,
        guild=guild,
        member=member,
        user=user,
        role=role,
        message=MessageObject.from_elements(
            raw["id"], decode_segments(raw)
        ),
        referrer={
            "direct": True,
            "msg_id": raw["id"],
            "msg_seq": -1,
        }
    )


@register_event("C2C_MESSAGE_CREATE")
async def c2c_message_create(login, guild_login, net, payload: Payload):
    raw = payload.data
    app_id = net.adapter.bot_id_mapping[login.id]
    if "user_openid" in raw["author"]:
        user = User(
            raw["author"]["user_openid"],
            avatar=USER_AVATAR_URL.format(app_id, user_id=raw["author"]["user_openid"])
        )
    else:
        user = User(
            raw["author"]["id"],
            avatar=USER_AVATAR_URL.format(app_id, user_id=raw["author"]["id"])
        )
    channel = Channel(f"private:{user.id}", ChannelType.DIRECT)
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.fromtimestamp(raw["timestamp"]),
        login,
        channel=channel,
        user=user,
        message=MessageObject.from_elements(
            raw["id"], decode_segments(raw)
        ),
        referrer={
            "direct": True,
            "msg_id": raw["id"],
            "msg_seq": -1,
        }
    )


#
# @register_event("message_recall")
# async def message_recall(login, net, raw):
#     data = raw["data"]
#     scene = data["message_scene"]
#     peer_id = str(data["peer_id"])
#     if scene == "group":
#         channel = Channel(peer_id, ChannelType.TEXT)
#         guild = Guild(peer_id, avatar=group_avatar(peer_id))
#     elif scene == "temp":
#         channel = Channel(f"private:temp_{peer_id}", ChannelType.DIRECT)
#         guild = None
#     else:
#         channel = Channel(f"private:{peer_id}", ChannelType.DIRECT)
#         guild = None
#     user = User(str(data["sender_id"]), avatar=user_avatar(data["sender_id"]))
#     operator = User(str(data["operator_id"]), avatar=user_avatar(data["operator_id"]))
#     message = MessageObject(str(data["message_seq"]), "", channel=channel, guild=guild, user=user)
#     return Event(
#         EventType.MESSAGE_DELETED,
#         datetime.fromtimestamp(raw["time"]),
#         login,
#         channel=channel,
#         guild=guild,
#         user=user,
#         operator=operator,
#         message=message,
#     )
#
#
# @register_event("group_message_reaction")
# async def group_message_reaction(login, net, raw):
#     data = raw["data"]
#     guild_id = str(data["group_id"])
#     guild = Guild(guild_id, avatar=group_avatar(guild_id))
#     channel = Channel(guild_id, ChannelType.TEXT)
#     user = User(str(data["user_id"]), avatar=user_avatar(data["user_id"]))
#     face_id = data["face_id"]
#     message = MessageObject(
#         str(data["message_seq"]), f"<milky:face id='{face_id}'>", channel=channel, guild=guild, user=user
#     )
#     if data["is_add"]:
#         event_type = EventType.REACTION_ADDED
#     else:
#         event_type = EventType.REACTION_REMOVED
#     return Event(
#         event_type,
#         datetime.fromtimestamp(raw["time"]),
#         login,
#         channel=channel,
#         guild=guild,
#         user=user,
#         message=message,
#     )
