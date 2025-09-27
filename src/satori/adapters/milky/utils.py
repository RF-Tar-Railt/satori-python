from typing import Protocol


class MilkyNetwork(Protocol):
    async def call_api(self, action: str, params: dict | None = None) -> dict | None: ...


def milky_event_type(raw: dict) -> str:
    """Extract event type from milky protocol event data."""
    # Based on milky protocol structure
    event_type = raw.get("type", "unknown")
    sub_type = raw.get("sub_type", "")
    
    if sub_type:
        return f"{event_type}.{sub_type}"
    return event_type


# Milky protocol specific constants and mappings
USER_AVATAR_URL = "https://q2.qlogo.cn/headimg_dl?dst_uin={uin}&spec=640"
GROUP_AVATAR_URL = "https://p.qlogo.cn/gh/{group}/{group}/"

# Event type mappings for milky protocol
MILKY_EVENT_MAPPING = {
    "message": "message.created",
    "message_delete": "message.deleted", 
    "message_update": "message.updated",
    "friend_request": "request.friend",
    "guild_request": "request.guild",
    "member_join": "notice.member.join",
    "member_leave": "notice.member.leave",
    "friend_add": "notice.friend.add",
    "friend_remove": "notice.friend.remove",
}