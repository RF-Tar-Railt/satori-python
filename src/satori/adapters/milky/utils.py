from typing import Protocol


class MilkyNetwork(Protocol):
    async def call_api(self, action: str, params: dict | None = None) -> dict | None: ...


def milky_event_type(raw: dict) -> str:
    """Extract event type from milky protocol event data."""
    # Based on milky protocol structure, adapt as needed
    return f"{raw.get('type', 'unknown')}.{raw.get('sub_type', '')}"


# Milky protocol specific constants
USER_AVATAR_URL = "https://q2.qlogo.cn/headimg_dl?dst_uin={uin}&spec=640"
GROUP_AVATAR_URL = "https://p.qlogo.cn/gh/{group}/{group}/"