from __future__ import annotations

from datetime import datetime

from satori import EventType, At, Text
from satori.model import Channel, ChannelType, Event, Guild, MessageObject, User, Member, Role

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
        datetime.fromtimestamp(int(raw["timestamp"])) if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit() else datetime.fromisoformat(str(raw["timestamp"])),
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
        datetime.fromtimestamp(int(raw["timestamp"])) if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit() else datetime.fromisoformat(str(raw["timestamp"])),
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
        datetime.fromtimestamp(int(raw["timestamp"])) if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit() else datetime.fromisoformat(str(raw["timestamp"])),
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
        datetime.fromtimestamp(int(raw["timestamp"])) if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit() else datetime.fromisoformat(str(raw["timestamp"])),
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


@register_event("MESSAGE_DELETE")
@register_event("PUBLIC_MESSAGE_DELETE")
async def message_delete(login, guild_login, new, payload: Payload):
    raw = payload.data
    guild = Guild(raw["message"]["guild_id"])
    channel = Channel(raw["message"]["channel_id"], ChannelType.TEXT, parent_id=guild.id)
    user = decode_user(raw["message"]["author"])
    operator = decode_user(raw["op_user"])
    member = Member(
        user,
        avatar=user.avatar,
        joined_at=datetime.fromisoformat(raw["message"]["member"]["joined_at"]),
    )
    role = Role(raw["message"]["member"]["roles"][0])
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.now(),
        guild_login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        operator=operator,
        role=role,
        message=MessageObject(raw["message"]["id"], ""),
        referrer={
            "direct": False,
            "msg_id": raw["message"]["id"],
            "msg_seq": -1,
        }
    )


@register_event("DIRECT_MESSAGE_DELETE")
async def direct_message_delete(login, guild_login, new, payload: Payload):
    raw = payload.data
    guild = Guild(f"{raw['message']['src_guild_id']}_{raw['message']['guild_id']}")
    channel = Channel(f"{raw['message']['guild_id']}_{raw['message']['channel_id']}", ChannelType.DIRECT)
    user = decode_user(raw["message"]["author"])
    operator = decode_user(raw["op_user"])
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.now(),
        guild_login,
        guild=guild,
        channel=channel,
        user=user,
        operator=operator,
        message=MessageObject(raw["message"]["id"], ""),
        referrer={
            "direct": True,
            "msg_id": raw["message"]["id"],
            "msg_seq": -1,
        }
    )


@register_event("MESSAGE_REACTION_ADD")
@register_event("MESSAGE_REACTION_REMOVE")
async def message_reaction(login, guild_login, new, payload: Payload):
    raw = payload.data
    if raw["target"]["type"] != 'ReactionTargetType_MSG':
        return
    guild = Guild(raw["guild_id"])
    channel = Channel(raw["channel_id"], ChannelType.TEXT, parent_id=guild.id)
    user = User(raw["user_id"])
    member = Member(user)
    return Event(
        EventType.REACTION_ADDED if payload.type == "MESSAGE_REACTION_ADD" else EventType.REACTION_REMOVED,
        datetime.now(),
        guild_login,
        channel=channel,
        guild=guild,
        user=user,
        member=member,
        message=MessageObject(
            raw["target"]["id"],
            f"<qq:emoji id=\"{raw['emoji']['type']}:{raw['emoji']['id']}\" />"
        )
    )
