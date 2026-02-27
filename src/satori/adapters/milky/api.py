from __future__ import annotations

from collections.abc import Callable

from satori import Api
from satori.model import Channel, ChannelType, Login, PageDequeResult, PageResult
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
    GuildXXXListParam,
    MessageListParam,
    MessageOpParam,
    MessageParam,
    ReactionCreateParam,
    ReactionDeleteParam,
    UserChannelCreateParam,
    UserGetParam,
)

from .message import MilkyMessageEncoder, decode_message
from .utils import (
    MilkyNetwork,
    decode_friend,
    decode_group_channel,
    decode_guild,
    decode_member,
    decode_private_channel,
    decode_user_profile,
    get_scene_and_peer,
)


def apply(
    adapter: Adapter,
    net_getter: Callable[[str], MilkyNetwork],
    login_getter: Callable[[str], Login],
):
    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return login_getter(request.self_id)

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        net = net_getter(request.self_id)
        login = login_getter(request.self_id)
        encoder = MilkyMessageEncoder(login, net, request.params["channel_id"])
        return await encoder.send(request.params["content"])

    @adapter.route(Api.MESSAGE_GET)
    async def message_get(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        scene, peer_id = get_scene_and_peer(request.params["channel_id"])
        result = await net.call_api(
            "get_message",
            {
                "message_scene": scene,
                "peer_id": peer_id,
                "message_seq": int(request.params["message_id"]),
            },
        )
        if not result or "message" not in result:
            raise RuntimeError("Failed to get message")
        return await decode_message(net, result["message"])

    @adapter.route(Api.MESSAGE_DELETE)
    async def message_delete(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        scene, peer_id = get_scene_and_peer(request.params["channel_id"])
        message_seq = int(request.params["message_id"])
        if scene == "group":
            await net.call_api("recall_group_message", {"group_id": peer_id, "message_seq": message_seq})
        else:
            await net.call_api("recall_private_message", {"user_id": peer_id, "message_seq": message_seq})
        return

    @adapter.route(Api.MESSAGE_LIST)
    async def message_list(request: Request[MessageListParam]):
        net = net_getter(request.self_id)
        params = request.params
        direction = params.get("direction", "before")
        if direction != "before":
            raise RuntimeError("Milky adapter only supports direction='before'")
        scene, peer_id = get_scene_and_peer(params["channel_id"])
        result = await net.call_api(
            "get_history_messages",
            {
                "message_scene": scene,
                "peer_id": peer_id,
                "start_message_seq": int(params["next"]) if params.get("next") else None,  # type: ignore
                "limit": params.get("limit"),
            },
        )
        if not result:
            return PageDequeResult([])
        messages = [await decode_message(net, item) for item in result.get("messages", [])]
        next_seq = result.get("next_message_seq")
        return PageDequeResult(messages, str(next_seq) if next_seq is not None else None)

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]):
        net = net_getter(request.self_id)
        channel_id = request.params["channel_id"]
        scene, peer_id = get_scene_and_peer(channel_id)
        if scene == "group":
            result = await net.call_api("get_group_info", {"group_id": peer_id})
            if not result:
                raise RuntimeError("Failed to get group info")
            return decode_group_channel(result["group"])
        profile = await net.call_api("get_user_profile", {"user_id": peer_id})
        if not profile:
            raise RuntimeError("Failed to get user profile")
        return decode_private_channel(profile, channel_id)

    @adapter.route(Api.CHANNEL_LIST)
    async def channel_list(request: Request[ChannelListParam]):
        net = net_getter(request.self_id)
        guild_id = int(request.params["guild_id"])
        result = await net.call_api("get_group_info", {"group_id": guild_id})
        if not result:
            raise RuntimeError("Failed to get group info")
        channel = decode_group_channel(result["group"])
        return PageResult([channel])

    @adapter.route(Api.USER_CHANNEL_CREATE)
    async def user_channel_create(request: Request[UserChannelCreateParam]):
        return Channel(f"private:{request.params['user_id']}", ChannelType.DIRECT)

    @adapter.route(Api.CHANNEL_UPDATE)
    async def channel_update(request: Request[ChannelUpdateParam]):
        net = net_getter(request.self_id)
        data = request.params["data"]
        channel_id = request.params["channel_id"]
        scene, peer_id = get_scene_and_peer(channel_id)
        if scene != "group":
            raise RuntimeError("Only group channels support update")
        if "name" in data:
            await net.call_api("set_group_name", {"group_id": peer_id, "new_group_name": data["name"]})
        return

    @adapter.route(Api.CHANNEL_MUTE)
    async def channel_mute(request: Request[ChannelMuteParam]):
        net = net_getter(request.self_id)
        scene, peer_id = get_scene_and_peer(request.params["channel_id"])
        if scene != "group":
            raise RuntimeError("Only group channels support mute")
        await net.call_api(
            "set_group_whole_mute",
            {"group_id": peer_id, "is_mute": request.params["duration"] > 0},
        )
        return

    @adapter.route(Api.GUILD_GET)
    async def guild_get(request: Request[GuildGetParam]):
        net = net_getter(request.self_id)
        guild_id = int(request.params["guild_id"])
        result = await net.call_api("get_group_info", {"group_id": guild_id})
        if not result:
            raise RuntimeError("Failed to get group info")
        return decode_guild(result["group"])

    @adapter.route(Api.GUILD_LIST)
    async def guild_list(request: Request[GuildListParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_group_list", {})
        groups = [decode_guild(item) for item in result.get("groups", [])] if result else []
        return PageResult(groups)

    @adapter.route(Api.GUILD_MEMBER_GET)
    async def guild_member_get(request: Request[GuildMemberGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_group_member_info",
            {"group_id": int(request.params["guild_id"]), "user_id": int(request.params["user_id"])},
        )
        if not result:
            raise RuntimeError("Failed to get group member")
        return decode_member(result["member"])

    @adapter.route(Api.GUILD_MEMBER_LIST)
    async def guild_member_list(request: Request[GuildXXXListParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_group_member_list", {"group_id": int(request.params["guild_id"])})
        members = [decode_member(item) for item in result.get("members", [])] if result else []
        return PageResult(members)

    @adapter.route(Api.GUILD_MEMBER_KICK)
    async def guild_member_kick(request: Request[GuildMemberKickParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "kick_group_member",
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
            "set_group_member_mute",
            {
                "group_id": int(request.params["guild_id"]),
                "user_id": int(request.params["user_id"]),
                "duration": int(request.params["duration"] / 1000),
            },
        )
        return

    @adapter.route(Api.GUILD_MEMBER_APPROVE)
    async def guild_member_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        message_id = request.params["message_id"]
        notification_seq, notification_type, group_id, is_filtered = message_id.split("|")
        params = {
            "notification_seq": int(notification_seq),
            "notification_type": notification_type,
            "group_id": int(group_id),
            "is_filtered": bool(int(is_filtered)),
        }
        if request.params["approve"]:
            await net.call_api("accept_group_request", params)
        else:
            params["reason"] = request.params.get("comment")
            await net.call_api("reject_group_request", params)
        return

    @adapter.route(Api.GUILD_APPROVE)
    async def guild_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        group_id, invitation_seq = request.params["message_id"].split("|")
        payload = {"group_id": int(group_id), "invitation_seq": int(invitation_seq)}
        if request.params["approve"]:
            await net.call_api("accept_group_invitation", payload)
        else:
            await net.call_api("reject_group_invitation", payload)
        return

    @adapter.route(Api.REACTION_CREATE)
    async def reaction_create(request: Request[ReactionCreateParam]):
        net = net_getter(request.self_id)
        scene, peer_id = get_scene_and_peer(request.params["channel_id"])
        if scene != "group":
            raise RuntimeError("Reactions only supported in group channels")
        await net.call_api(
            "send_group_message_reaction",
            {
                "group_id": peer_id,
                "message_seq": int(request.params["message_id"]),
                "reaction": request.params["emoji_id"],
                "is_add": True,
            },
        )
        return

    @adapter.route(Api.REACTION_DELETE)
    async def reaction_delete(request: Request[ReactionDeleteParam]):
        net = net_getter(request.self_id)
        scene, peer_id = get_scene_and_peer(request.params["channel_id"])
        if scene != "group":
            raise RuntimeError("Reactions only supported in group channels")
        await net.call_api(
            "send_group_message_reaction",
            {
                "group_id": peer_id,
                "message_seq": int(request.params["message_id"]),
                "reaction": request.params["emoji_id"],
                "is_add": False,
            },
        )
        return

    @adapter.route(Api.USER_GET)
    async def user_get(request: Request[UserGetParam]):
        net = net_getter(request.self_id)
        user_id = request.params["user_id"]
        profile = await net.call_api("get_user_profile", {"user_id": int(user_id)})
        if not profile:
            raise RuntimeError("Failed to get user profile")
        return decode_user_profile(profile, user_id)

    @adapter.route(Api.FRIEND_LIST)
    async def friend_list(request: Request[FriendListParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_friend_list", {})
        friends = [decode_friend(item) for item in result.get("friends", [])] if result else []
        return PageResult(friends)

    @adapter.route(Api.FRIEND_APPROVE)
    async def friend_approve(request: Request[ApproveParam]):
        net = net_getter(request.self_id)
        initiator_uid, is_filtered = request.params["message_id"].split("|")
        payload = {"initiator_uid": initiator_uid, "is_filtered": bool(int(is_filtered))}
        if request.params["approve"]:
            await net.call_api("accept_friend_request", payload)
        else:
            payload["reason"] = request.params.get("comment")
            await net.call_api("reject_friend_request", payload)
        return

    @adapter.route("*")
    async def internal_api(request: Request[dict]):
        net = net_getter(request.self_id)
        return await net.call_api(request.action.removeprefix("internal/"), request.params)
