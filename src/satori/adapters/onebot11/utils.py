from typing import Protocol

from satori import Role


class OneBotNetwork(Protocol):
    async def call_api(self, action: str, params: dict | None = None) -> dict: ...


SPECIAL_POST_TYPE = {"message_sent": "message"}


def onebot11_event_type(raw: dict) -> str:
    return (
        f"{(post := raw['post_type'])}."
        f"{raw.get(f'{SPECIAL_POST_TYPE.get(post, post)}_type', '_')}"
        f"{f'.{sub}' if (sub:=raw.get('sub_type')) else ''}"
    )


USER_AVATAR_URL = "https://q2.qlogo.cn/headimg_dl?dst_uin={uin}&spec=640"
GROUP_AVATAR_URL = "https://p.qlogo.cn/gh/{group}/{group}/"

ROLE_MAPPING = {
    "member": Role("MEMBER", "群成员"),
    "admin": Role("ADMINISTRATOR", "管理员"),
    "owner": Role("OWNER", "群主"),
}
