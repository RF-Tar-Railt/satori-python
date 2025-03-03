from datetime import datetime
from typing import Callable

from satori import Api
from satori.model import Channel, ChannelType, Guild, Login, Member, MessageObject, PageResult, Role, User
from satori.server import Adapter, Request
from satori.server.route import (
    ApproveParam,
    ChannelListParam,
    ChannelMuteParam,
    ChannelParam,
    ChannelUpdateParam,
    FriendListParam,
    GuildGetParam,
    GuildListParam,
    GuildMemberGetParam,
    GuildMemberKickParam,
    GuildMemberMuteParam,
    GuildMemberRoleParam,
    GuildXXXListParam,
    MessageOpParam,
    MessageParam,
    UserChannelCreateParam,
    UserGetParam,
)

from .message import OneBot11MessageEncoder, decode
from .utils import GROUP_AVATAR_URL, USER_AVATAR_URL, OneBotNetwork

INTERNAL_API = [
    "get_forward_msg",
    "send_like",
    "set_group_card",
    "set_group_leave",
    "set_group_special_title",
    "get_login_info",
    "get_group_honor_info",
    "get_cookies",
    "get_csrf_token",
    "get_credentials",
    "get_record",
    "get_image",
    "can_send_image",
    "can_send_record",
    "get_status",
    "get_version_info",
    "set_restart",
    "clean_cache",
    # additional
    "group_poke",
    "friend_poke",
    "set_group_reaction",
]


def apply(adapter: Adapter, net_getter: Callable[[str], OneBotNetwork], login_getter: Callable[[str], Login]):
    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return login_getter(request.self_id)

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        net = net_getter(request.self_id)
        login = login_getter(request.self_id)
        encoder = OneBot11MessageEncoder(login, net, request.params["channel_id"])
        await encoder.send(request.params["content"])
        return encoder.results

    @adapter.route(Api.MESSAGE_GET)
    async def message_get(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_msg", {"message_id": int(request.params["message_id"])})
        if not result:
            raise RuntimeError(f"Failed to get message {request.params['message_id']}")
        sender: dict = result["sender"]
        user = User(str(sender["user_id"]), sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
        if result["message_type"] == "private":
            return MessageObject(
                request.params["message_id"],
                await decode(result["message"], net),
                user=user,
                channel=Channel(f"private:{sender['user_id']}", ChannelType.DIRECT, sender["nickname"]),
            )
        member = Member(user, sender["nickname"], USER_AVATAR_URL.format(uin=sender["user_id"]))
        guild = Guild(
            request.params["channel_id"], avatar=GROUP_AVATAR_URL.format(group=request.params["channel_id"])
        )
        channel = Channel(request.params["channel_id"], ChannelType.TEXT)
        return MessageObject(
            request.params["message_id"],
            await decode(result["message"], net),
            user=user,
            member=member,
            guild=guild,
            channel=channel,
        )

    @adapter.route(Api.MESSAGE_DELETE)
    async def message_delete(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        await net.call_api("delete_msg", {"message_id": int(request.params["message_id"])})
        return

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_group_info", {"group_id": int(request.params["channel_id"])})
        if not result:
            raise RuntimeError(f"Failed to get group {request.params['channel_id']}")
        return Channel(
            str(result["group_id"]),
            ChannelType.TEXT,
            result["group_name"],
            GROUP_AVATAR_URL.format(group=result["group_id"]),
        )

    @adapter.route(Api.GUILD_GET)
    async def guild_get(request: Request[GuildGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_group_info", {"group_id": int(request.params["guild_id"])})
        if not result:
            raise RuntimeError(f"Failed to get group {request.params['guild_id']}")
        return Guild(
            str(result["group_id"]), result["group_name"], GROUP_AVATAR_URL.format(group=result["group_id"])
        )

    @adapter.route(Api.USER_CHANNEL_CREATE)
    async def user_channel_create(request: Request[UserChannelCreateParam]):
        user_id = str(request.params["user_id"])
        return Channel(f"private:{user_id}", ChannelType.DIRECT)

    @adapter.route(Api.CHANNEL_LIST)
    async def channel_list(request: Request[ChannelListParam]):
        net = net_getter(request.self_id)
        result: list[dict] = await net.call_api("get_group_list", {})  # type: ignore
        return PageResult(
            [
                Channel(
                    str(item["group_id"]),
                    ChannelType.TEXT,
                    item["group_name"],
                    GROUP_AVATAR_URL.format(group=item["group_id"]),
                )
                for item in result
            ]
        )

    @adapter.route(Api.GUILD_LIST)
    async def guild_list(request: Request[GuildListParam]):
        net = net_getter(request.self_id)
        result: list[dict] = await net.call_api("get_group_list", {})  # type: ignore
        return PageResult(
            [
                Guild(
                    str(item["group_id"]), item["group_name"], GROUP_AVATAR_URL.format(group=item["group_id"])
                )
                for item in result
            ]
        )

    @adapter.route(Api.CHANNEL_UPDATE)
    async def channel_update(request: Request[ChannelUpdateParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_name",
            {"group_id": int(request.params["channel_id"]), "group_name": request.params["data"]["name"]},
        )
        return

    @adapter.route(Api.CHANNEL_MUTE)
    async def channel_mute(request: Request[ChannelMuteParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_whole_ban",
            {
                "group_id": int(request.params["channel_id"]),
                "enable": request.params["duration"] > 0,
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_GET)
    async def guild_member_get(request: Request[GuildMemberGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_group_member_info",
            {"group_id": int(request.params["guild_id"]), "user_id": int(request.params["user_id"])},
        )
        if not result:
            raise RuntimeError(
                f"Failed to get member {request.params['user_id']} in group {request.params['guild_id']}"
            )
        user = User(
            str(result["user_id"]), result["nickname"], avatar=USER_AVATAR_URL.format(uin=result["user_id"])
        )
        return Member(user, result["card"], user.avatar, datetime.fromtimestamp(result["join_time"]))

    @adapter.route(Api.GUILD_MEMBER_LIST)
    async def guild_member_list(request: Request[GuildXXXListParam]):
        net = net_getter(request.self_id)
        result: list[dict] = await net.call_api(  # type: ignore
            "get_group_member_list",
            {"group_id": int(request.params["guild_id"])},
        )
        return PageResult(
            [
                Member(
                    User(
                        str(item["user_id"]),
                        item["nickname"],
                        avatar=USER_AVATAR_URL.format(uin=item["user_id"]),
                    ),
                    item["card"],
                    USER_AVATAR_URL.format(uin=item["user_id"]),
                    datetime.fromtimestamp(item["join_time"]),
                )
                for item in result
            ]
        )

    @adapter.route(Api.GUILD_MEMBER_KICK)
    async def guild_member_kick(request: Request[GuildMemberKickParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_kick",
            {
                "group_id": int(request.params["guild_id"]),
                "user_id": int(request.params["user_id"]),
                "reject_add_request": request.params.get("permanent", False),
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_MUTE)
    async def guild_member_mute(request: Request[GuildMemberMuteParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_ban",
            {
                "group_id": int(request.params["guild_id"]),
                "user_id": int(request.params["user_id"]),
                "duration": request.params["duration"],
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_ROLE_SET)
    async def guild_member_role_set(request: Request[GuildMemberRoleParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_admin",
            {
                "group_id": int(request.params["guild_id"]),
                "user_id": int(request.params["user_id"]),
                "enable": request.params["role_id"] == "ADMINISTRATOR",
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_ROLE_UNSET)
    async def guild_member_role_unset(request: Request[GuildMemberRoleParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_admin",
            {
                "group_id": int(request.params["guild_id"]),
                "user_id": int(request.params["user_id"]),
                "enable": request.params["role_id"] != "ADMINISTRATOR",
            },
        )
        return

    @adapter.route(Api.GUILD_ROLE_LIST)
    async def guild_role_list(request: Request[GuildXXXListParam]):
        return PageResult([Role("ADMINISTRATOR", "admin"), Role("MEMBER", "member"), Role("OWNER", "owner")])

    @adapter.route(Api.USER_GET)
    async def user_get(request: Request[UserGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_stranger_info", {"user_id": int(request.params["user_id"])})
        if not result:
            raise RuntimeError(f"Failed to get user {request.params['user_id']}")
        return User(
            str(result["user_id"]),
            result["nickname"],
            result.get("remark"),
            USER_AVATAR_URL.format(uin=result["user_id"]),
        )

    @adapter.route(Api.FRIEND_LIST)
    async def friend_list(request: Request[FriendListParam]):
        net = net_getter(request.self_id)
        result: list[dict] = await net.call_api("get_friend_list", {})  # type: ignore
        return PageResult(
            [
                User(
                    str(item["user_id"]),
                    item["nickname"],
                    item.get("remark"),
                    USER_AVATAR_URL.format(uin=item["user_id"]),
                )
                for item in result
            ]
        )

    @adapter.route(Api.GUILD_APPROVE)
    async def guild_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_add_request",
            {
                "flag": request.params["message_id"],
                "sub_type": "invite",
                "approve": request.params["approve"],
                "reason": request.params.get("comment", ""),
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_APPROVE)
    async def guild_member_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_group_add_request",
            {
                "flag": request.params["message_id"],
                "sub_type": "add",
                "approve": request.params["approve"],
                "reason": request.params.get("comment", ""),
            },
        )
        return

    @adapter.route(Api.FRIEND_APPROVE)
    async def friend_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "set_friend_add_request",
            {
                "flag": request.params["message_id"],
                "approve": request.params["approve"],
            },
        )
        return

    for api in INTERNAL_API:

        @adapter.route(api)
        async def internal_api(request: Request[dict]):
            net = net_getter(request.self_id)
            return await net.call_api(api, request.params)
