from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Login, Member, MessageObject, User

from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, MilkyNetwork
from .base import register_event


@register_event("request.friend")
async def request_friend(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle friend request events from milky protocol."""
    user_info = data.get("user", {})
    user_id = str(user_info.get("id", ""))
    
    user = User(
        id=user_id,
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_id)
    )
    
    channel = Channel(f"private:{user_id}", ChannelType.DIRECT, user.name)
    
    message = MessageObject(
        id=str(data.get("request_id", "")),
        content=data.get("message", "")
    )
    
    return Event(
        type=EventType.FRIEND_REQUEST,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        channel=channel,
        message=message,
    )


@register_event("request.guild.invite")
@register_event("request.guild.join")
async def request_guild(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle guild request events from milky protocol."""
    guild_info = data.get("guild", {})
    guild_id = str(guild_info.get("id", ""))
    
    guild = Guild(
        id=guild_id,
        name=guild_info.get("name", ""),
        avatar=GROUP_AVATAR_URL.format(group=guild_id)
    )
    
    user_info = data.get("user", {})
    user_id = str(user_info.get("id", ""))
    
    user = User(
        id=user_id,
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_id)
    )
    
    member = Member(
        user=user,
        nick=data.get("member", {}).get("nick"),
    )
    
    channel = Channel(
        id=guild_id,
        type=ChannelType.TEXT,
        name=guild.name
    )
    
    message = MessageObject(
        id=str(data.get("request_id", "")),
        content=data.get("message", "")
    )
    
    # Determine event type based on request sub-type
    event_type = EventType.GUILD_REQUEST if data.get("sub_type") == "invite" else EventType.GUILD_MEMBER_REQUEST
    
    return Event(
        type=event_type,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        member=member,
        channel=channel,
        guild=guild,
        message=message,
    )