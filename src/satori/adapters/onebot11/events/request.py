from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Login, Member, MessageObject, User

from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, OneBotNetwork
from .base import register_event


@register_event("request.friend")
async def request_friend(login: Login, adapter: OneBotNetwork, raw: dict) -> Event:
    user_id = str(raw["user_id"])
    user = User(user_id, avatar=USER_AVATAR_URL.format(uin=user_id))
    channel = Channel(f"private:{user_id}", ChannelType.DIRECT)
    return Event(
        EventType.FRIEND_REQUEST,
        datetime.fromtimestamp(raw["time"]),
        login,
        user=user,
        channel=channel,
        message=MessageObject(raw["flag"], raw.get("comment", "")),
    )


@register_event("request.group.invite")
@register_event("request.group.add")
async def request_group_invite(login: Login, adapter: OneBotNetwork, raw: dict) -> Event:
    group_id = str(raw["group_id"])
    guild = Guild(group_id, avatar=GROUP_AVATAR_URL.format(group=group_id))
    channel = Channel(group_id)
    user_id = str(raw["user_id"])
    user = User(user_id, avatar=USER_AVATAR_URL.format(uin=user_id))
    return Event(
        EventType.GUILD_REQUEST if raw["sub_type"] == "invite" else EventType.GUILD_MEMBER_ADDED,
        datetime.fromtimestamp(raw["time"]),
        login,
        user=user,
        member=Member(user, avatar=USER_AVATAR_URL.format(uin=user_id)),
        channel=channel,
        guild=guild,
        message=MessageObject(raw["flag"], raw.get("comment", "")),
    )
