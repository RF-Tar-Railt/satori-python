from typing import Optional, Protocol


class OneBotNetwork(Protocol):
    async def call_api(self, action: str, params: Optional[dict] = None) -> Optional[dict]: ...


SPECIAL_POST_TYPE = {"message_sent": "message"}


def onebot11_event_type(raw: dict) -> str:
    return (
        f"{(post := raw['post_type'])}."
        f"{raw.get(f'{SPECIAL_POST_TYPE.get(post, post)}_type', '_')}"
        f"{f'.{sub}' if (sub:=raw.get('sub_type')) else ''}"
    )


USER_AVATAR_URL = "https://q2.qlogo.cn/headimg_dl?dst_uin={uin}&spec=640"
GROUP_AVATAR_URL = "https://p.qlogo.cn/gh/{group}/{group}/"
