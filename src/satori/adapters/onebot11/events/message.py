from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Login, Member, MessageObject, User

from ..message import decode
from ..utils import GROUP_AVATAR_URL, ROLE_MAPPING, USER_AVATAR_URL, OneBotNetwork
from .base import register_event


@register_event("message.private.friend")
@register_event("message.private.other")
async def private_friend(login: Login, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(
        str(sender["user_id"]), sender["nickname"], sender.get("card"), USER_AVATAR_URL.format(uin=sender["user_id"])
    )
    channel = Channel(f"private:{sender['user_id']}", ChannelType.DIRECT, sender["nickname"])
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.now(),
        login=login,
        user=user,
        channel=channel,
        message=MessageObject(str(raw["message_id"]), await decode(raw["message"], net)),
    )


@register_event("message.private.group")
async def private_group(login: Login, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(
        str(sender["user_id"]), sender["nickname"], sender.get("card"), USER_AVATAR_URL.format(uin=sender["user_id"])
    )
    channel = Channel(f"private:{sender['user_id']}", ChannelType.DIRECT, sender["nickname"])
    group_id = sender["group_id"] if "group_id" in sender else raw.get("group_id")
    group_info = await net.call_api("get_group_info", {"group_id": group_id}) if group_id else {}
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.now(),
        login=login,
        user=user,
        member=Member(user, sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"])),
        guild=(
            Guild(str(group_id), group_info.get("group_name"), avatar=GROUP_AVATAR_URL.format(group=group_id))
            if group_id
            else None
        ),
        channel=channel,
        message=MessageObject(str(raw["message_id"]), await decode(raw["message"], net)),
    )


@register_event("notice.friend_recall")
async def friend_message_recall(login: Login, net: OneBotNetwork, raw: dict):
    info = await net.call_api("get_stranger_info", {"user_id": raw["user_id"]})
    user = User(str(raw["user_id"]), info.get("nickname"), info.get("card"), USER_AVATAR_URL.format(uin=raw["user_id"]))
    channel = Channel(f"private:{raw['user_id']}", ChannelType.DIRECT, info.get("nickname"))
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.now(),
        login=login,
        user=user,
        channel=channel,
        message=MessageObject(str(raw["message_id"]), ""),
    )


@register_event("message.group.normal")
@register_event("message.group.notice")
@register_event("message_sent.group.normal")
async def group(login: Login, net: OneBotNetwork, raw: dict):
    sender: dict = raw["sender"]
    user = User(
        str(sender["user_id"]), sender["nickname"], sender.get("card"), USER_AVATAR_URL.format(uin=sender["user_id"])
    )
    group_info = await net.call_api("get_group_info", {"group_id": raw["group_id"]})
    member_info = await net.call_api(
        "get_group_member_info", {"group_id": raw["group_id"], "user_id": sender["user_id"]}
    )
    member = Member(user, member_info["card"], USER_AVATAR_URL.format(uin=sender["user_id"]), roles=[ROLE_MAPPING[sender["role"]]])
    guild = Guild(
        str(raw["group_id"]), group_info.get("group_name"), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"])
    )
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT, group_info.get("group_name"))
    return Event(
        EventType.MESSAGE_CREATED,
        datetime.now(),
        login=login,
        user=user,
        guild=guild,
        channel=channel,
        member=member,
        message=MessageObject(str(raw["message_id"]), await decode(raw["message"], net)),
    )


@register_event("notice.group_recall")
async def group_message_recall(login: Login, net: OneBotNetwork, raw: dict):
    group_info = await net.call_api("get_group_info", {"group_id": raw["group_id"]})
    member_info = await net.call_api("get_group_member_info", {"group_id": raw["group_id"], "user_id": raw["user_id"]})
    operator_info = await net.call_api(
        "get_group_member_info", {"group_id": raw["group_id"], "user_id": raw["operator_id"]}
    )
    user = User(
        str(raw["user_id"]),
        member_info["nickname"],
        member_info.get("card"),
        USER_AVATAR_URL.format(uin=raw["user_id"]),
    )
    member = Member(user, member_info.get("card"), USER_AVATAR_URL.format(uin=raw["user_id"]),roles=[ROLE_MAPPING[member_info["role"]]])
    guild = Guild(
        str(raw["group_id"]), group_info.get("group_name"), avatar=GROUP_AVATAR_URL.format(group=raw["group_id"])
    )
    channel = Channel(str(raw["group_id"]), ChannelType.TEXT, group_info.get("group_name"))
    operator = User(
        str(raw["operator_id"]),
        operator_info["nickname"],
        operator_info.get("card"),
        USER_AVATAR_URL.format(uin=raw["operator_id"]),
    )
    return Event(
        EventType.MESSAGE_DELETED,
        datetime.now(),
        login=login,
        user=user,
        guild=guild,
        channel=channel,
        member=member,
        operator=operator,
        message=MessageObject(str(raw["message_id"]), ""),
    )
