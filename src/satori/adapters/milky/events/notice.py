from __future__ import annotations

from datetime import datetime

from satori import EventType
from satori.model import Channel, ChannelType, Event, Guild, Login, Member, User

from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, MilkyNetwork
from .base import register_event


@register_event("notice.member.join")
async def member_join(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle member join events from milky protocol."""
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
    
    return Event(
        type=EventType.GUILD_MEMBER_ADDED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        member=member,
        guild=guild,
    )


@register_event("notice.member.leave")
async def member_leave(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle member leave events from milky protocol."""
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
    
    return Event(
        type=EventType.GUILD_MEMBER_REMOVED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),  
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        member=member,
        guild=guild,
    )


@register_event("notice.friend.add")
async def friend_add(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle friend add events from milky protocol."""
    user_info = data.get("user", {})
    user_id = str(user_info.get("id", ""))
    
    user = User(
        id=user_id,
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_id)
    )
    
    channel = Channel(
        id=f"private:{user_id}",
        type=ChannelType.DIRECT,
        name=user.name
    )
    
    return Event(
        type=EventType.FRIEND_ADDED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        channel=channel,
    )


@register_event("notice.friend.remove")
async def friend_remove(login: Login, net: MilkyNetwork, data: dict) -> Event:
    """Handle friend remove events from milky protocol."""
    user_info = data.get("user", {})
    user_id = str(user_info.get("id", ""))
    
    user = User(
        id=user_id,
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_id)
    )
    
    channel = Channel(
        id=f"private:{user_id}",
        type=ChannelType.DIRECT,
        name=user.name
    )
    
    return Event(
        type=EventType.FRIEND_REMOVED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        channel=channel,
    )