from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from satori.model import Channel, ChannelType, Guild, Member, User

AVATAR_URL = "https://q.qlogo.cn/headimg_dl?dst_uin={uin}&spec=640"
GROUP_AVATAR_URL = "https://p.qlogo.cn/gh/{group}/{group}/640"


class MilkyNetwork(Protocol):
    async def call_api(self, action: str, params: dict | None = None) -> dict: ...


def user_avatar(uin: int | str) -> str:
    return AVATAR_URL.format(uin=uin)


def group_avatar(group_id: int | str) -> str:
    return GROUP_AVATAR_URL.format(group=group_id)


def decode_group_channel(group: dict) -> Channel:
    return Channel(str(group["group_id"]), ChannelType.TEXT, group.get("group_name"))


def decode_private_channel(profile: dict, channel_id: str) -> Channel:
    return Channel(channel_id, ChannelType.DIRECT, profile.get("nickname"))


def decode_guild(group: dict) -> Guild:
    return Guild(str(group["group_id"]), group.get("group_name"), group_avatar(group["group_id"]))


def decode_member(member: dict) -> Member:
    user_id = str(member["user_id"])
    user = User(user_id, member.get("nickname"), avatar=user_avatar(user_id))
    joined_at = member.get("join_time")
    return Member(
        user=user,
        nick=member.get("card") or member.get("nickname"),
        avatar=user_avatar(user_id),
        joined_at=datetime.fromtimestamp(joined_at) if joined_at else None,
    )


def decode_friend(friend: dict) -> User:
    user_id = str(friend["user_id"])
    return User(user_id, friend.get("nickname"), avatar=user_avatar(user_id))


def decode_login_user(login: dict) -> User:
    user_id = str(login["uin"])
    return User(user_id, login.get("nickname"), avatar=user_avatar(user_id))


def decode_user_profile(profile: dict, user_id: str) -> User:
    return User(user_id, profile.get("nickname"), avatar=user_avatar(user_id), nick=profile.get("remark"))


def decode_guild_channel_id(data: dict) -> tuple[str | None, str]:
    scene = data.get("message_scene")
    peer_id = str(data.get("peer_id"))
    if scene == "group":
        return peer_id, peer_id
    if scene == "temp":
        return None, f"private:temp_{peer_id}"
    return None, f"private:{peer_id}"


def get_scene_and_peer(channel_id: str) -> tuple[Literal["friend", "group", "temp"], int]:
    if channel_id.startswith("private:temp_"):
        return "temp", int(channel_id.removeprefix("private:temp_"))
    if channel_id.startswith("private:"):
        return "friend", int(channel_id.removeprefix("private:"))
    return "group", int(channel_id)
