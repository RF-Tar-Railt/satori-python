from __future__ import annotations

from datetime import datetime

from satori import Button, ButtonInteraction, EventType, Text
from satori.model import Channel, ChannelType, Event, Guild, Member, MessageObject, User

from ..utils import Payload
from .base import register_event


@register_event("INTERACTION_CREATE")
async def interaction(login, guild_login, net, payload: Payload):
    raw = payload.data
    chat_type = raw["chat_type"]
    if chat_type == 0:
        guild = Guild(raw["guild_id"])
        channel = Channel(raw["channel_id"], ChannelType.TEXT)
        user = User(raw["data"]["resolved"]["user_id"])
        member = Member(user)
    elif chat_type == 1:
        guild = Guild(raw["group_openid"])
        channel = Channel(raw["group_openid"], ChannelType.TEXT)
        user = User(raw["group_member_openid"])
        member = Member(user)
    else:
        guild = None
        channel = Channel(f"private:{raw['user_openid ']}", ChannelType.DIRECT)
        user = User(raw["data"]["user_openid"])
        member = None
    button = ButtonInteraction(raw["data"]["resolved"]["button_id"], raw["data"]["resolved"]["button_data"])
    return Event(
        EventType.INTERACTION_BUTTON,
        (
            datetime.fromtimestamp(int(raw["timestamp"]))
            if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit()
            else datetime.fromisoformat(str(raw["timestamp"]))
        ),
        guild_login if chat_type == 0 else login,
        guild=guild,
        channel=channel,
        user=user,
        member=member,
        button=button,
        message=MessageObject.from_elements(
            raw["id"],
            [Button.action(raw["data"]["resolved"]["button_id"])(Text(raw["data"]["resolved"]["button_data"]))],
        ),
        referrer={
            "direct": chat_type == 2,
            "msg_id": raw["id"],
            "msg_seq": -1,
        },
    )
