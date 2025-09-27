from datetime import datetime

from satori import Event, EventType
from satori.model import Channel, ChannelType, Guild, Login, Member, MessageObject, User

from ..message import parse_message_object
from ..utils import GROUP_AVATAR_URL, USER_AVATAR_URL, MilkyNetwork
from .base import register_event


@register_event("message.created")
async def message_created(login: Login, net: MilkyNetwork, data: dict) -> Event | None:
    """Handle message created event from milky protocol."""
    
    # Parse user info
    user_info = data.get("user", {})
    user = User(
        id=str(user_info.get("id", "")),
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_info.get("id", "")),
    )

    # Parse channel info
    channel_info = data.get("channel", {})
    channel = Channel(
        id=str(channel_info.get("id", "")),
        type=ChannelType.TEXT,
        name=channel_info.get("name", ""),
    )

    # Parse guild info if present
    guild = None
    if guild_info := data.get("guild"):
        guild = Guild(
            id=str(guild_info.get("id", "")),
            name=guild_info.get("name", ""),
            avatar=GROUP_AVATAR_URL.format(group=guild_info.get("id", "")),
        )

    # Parse member info if present
    member = None
    if guild and data.get("member"):
        member = Member(
            user=user,
            nick=data.get("member", {}).get("nick"),
        )

    # Parse message
    message = parse_message_object(data)

    return Event(
        type=EventType.MESSAGE_CREATED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        channel=channel,
        guild=guild,
        member=member,
        message=message,
    )


@register_event("message.deleted")
async def message_deleted(login: Login, net: MilkyNetwork, data: dict) -> Event | None:
    """Handle message deleted event from milky protocol."""
    
    # Parse user info
    user_info = data.get("user", {})
    user = User(
        id=str(user_info.get("id", "")),
        name=user_info.get("name", ""),
        avatar=USER_AVATAR_URL.format(uin=user_info.get("id", "")),
    )

    # Parse channel info
    channel_info = data.get("channel", {})
    channel = Channel(
        id=str(channel_info.get("id", "")),
        type=ChannelType.TEXT,
        name=channel_info.get("name", ""),
    )

    # Parse guild info if present
    guild = None
    if guild_info := data.get("guild"):
        guild = Guild(
            id=str(guild_info.get("id", "")),
            name=guild_info.get("name", ""),
            avatar=GROUP_AVATAR_URL.format(group=guild_info.get("id", "")),
        )

    return Event(
        type=EventType.MESSAGE_DELETED,
        timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
        id=data.get("id"),
        platform=login.platform,
        self_id=login.user.id,
        user=user,
        channel=channel,
        guild=guild,
    )