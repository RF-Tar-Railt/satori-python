from collections.abc import Callable
from datetime import datetime

from satori import Api, At, Channel, ChannelType, Guild, Login, Member, MessageObject, PageResult, Role, Text
from satori.exception import BadRequestException, NotFoundException
from satori.server import Adapter, Request
from satori.server.route import (
    ChannelCreateParam,
    ChannelListParam,
    ChannelParam,
    ChannelUpdateParam,
    GuildGetParam,
    GuildListParam,
    GuildMemberGetParam,
    GuildMemberKickParam,
    GuildMemberMuteParam,
    GuildMemberRoleParam,
    GuildRoleCreateParam,
    GuildRoleDeleteParam,
    GuildRoleUpdateParam,
    GuildXXXListParam,
    MessageOpParam,
    MessageParam,
    ReactionCreateParam,
    ReactionDeleteParam,
    ReactionListParam,
    UserChannelCreateParam,
    UserGetParam,
)

from .message import QQGroupMessageEncoder, QQGuildMessageEncoder, decode_segments
from .utils import QQBotNetwork, decode_channel, decode_guild, decode_member, decode_user


def apply(
    adapter: Adapter, net_getter: Callable[[str, bool], QQBotNetwork], login_getter: Callable[[str, bool], Login]
):
    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return login_getter(request.self_id, request.platform == "qqguild")

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        login = login_getter(request.self_id, request.platform == "qqguild")
        # encoder = OneBot11MessageEncoder(login, net, request.params["channel_id"])
        if login.platform == "qqguild":
            encoder = QQGuildMessageEncoder(login, net, request.params["channel_id"], request.params.get("referrer"))
        else:
            encoder = QQGroupMessageEncoder(login, net, request.params["channel_id"], request.params.get("referrer"))
        await encoder.send(request.params["content"])
        return encoder.results

    @adapter.route(Api.USER_CHANNEL_CREATE)
    async def user_channel_create(request: Request[UserChannelCreateParam]):
        if request.platform == "qqguild":
            net = net_getter(request.self_id, request.platform == "qqguild")
            if "guild_id" not in request.params:
                raise BadRequestException("guild_id is required for qqguild's user.channel.create")
            guild_id = request.params["guild_id"]
            if "_" in guild_id:
                guild_id = guild_id.split("_")[0]
            res = await net.call_api(
                "post",
                "users/@me/dms",
                {"recipient_id": request.params["user_id"], "source_guild_id": request.params["guild_id"]},
            )
            return Channel(f"{res['guild_id']}_{guild_id}", ChannelType.TEXT)
        else:
            return Channel(f"private:{request.params['user_id']}", ChannelType.DIRECT)

    @adapter.route(Api.MESSAGE_DELETE)
    async def delete_message(request: Request[MessageOpParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            if "_" in request.params["channel_id"]:
                guild_id = request.params["channel_id"].split("_")[0]
                endpoint = f"dms/{guild_id}/messages/{request.params['message_id']}"
            else:
                endpoint = f"channels/{request.params['channel_id']}/messages/{request.params['message_id']}"
            await net.call_api("delete", endpoint, {"hidetip": "false"})
        else:
            if request.params["channel_id"].startswith("private:"):
                user_id = request.params["channel_id"][8:]
                endpoint = f"v2/users/{user_id}/messages/{request.params['message_id']}"
            else:
                endpoint = f"v2/groups/{request.params['channel_id']}/messages/{request.params['message_id']}"
            await net.call_api("delete", endpoint)

    @adapter.route(Api.MESSAGE_GET)
    async def get_message(request: Request[MessageOpParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            if "_" in request.params["channel_id"]:
                raise NotFoundException("user-channel is not supported for message.get")
            endpoint = f"channels/{request.params['channel_id']}/messages/{request.params['message_id']}"
            raw = await net.call_api("get", endpoint)
            guild = Guild(raw["guild_id"])
            channel = Channel(raw["channel_id"], ChannelType.TEXT, parent_id=guild.id)
            user = decode_user(raw["author"])
            member = Member(
                user,
                avatar=user.avatar,
                joined_at=datetime.fromisoformat(raw["member"]["joined_at"]),
            )
            msg = decode_segments(raw)
            if len(msg) >= 2 and isinstance(msg[0], At) and isinstance(msg[1], Text):
                text = msg[1].text.lstrip()
                if not text:
                    msg.pop(1)
                else:
                    msg[1] = Text(text)
            return MessageObject.from_elements(
                raw["id"],
                msg,
                channel=channel,
                guild=guild,
                member=member,
                user=user,
                created_at=(
                    datetime.fromtimestamp(int(raw["timestamp"]))
                    if isinstance(raw["timestamp"], (int, float)) or raw["timestamp"].isdigit()
                    else datetime.fromisoformat(str(raw["timestamp"]))
                ),
                referrer={
                    "msg_id": raw["id"],
                    "msg_seq": -1,
                },
            )
        raise NotFoundException("qq platform does not support message.get")

    @adapter.route(Api.USER_GET)
    async def guild_get_user(request: Request[UserGetParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            if "_" in request.params["user_id"]:
                guild_id, user_id = request.params["user_id"].split("_", maxsplit=1)
                res = await net.call_api(
                    "get",
                    f"guilds/{guild_id}/members/{user_id}",
                )
                return decode_user(res)
            raise NotFoundException("qqguild platform does not support user.get without guild_id")
        raise NotFoundException("qq platform does not support user.get")

    @adapter.route(Api.GUILD_GET)
    async def guild_get(request: Request[GuildGetParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            res = await net.call_api(
                "get",
                f"guilds/{request.params['guild_id']}",
            )
            return decode_guild(res)
        raise NotFoundException("qq platform does not support guild.get")

    @adapter.route(Api.GUILD_LIST)
    async def guild_list(request: Request[GuildListParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            res = await net.call_api(
                "get",
                "users/@me/guilds",
                {"after": request.params["next"]} if "next" in request.params else None,
            )
            guilds = [decode_guild(guild) for guild in res]
            return PageResult(guilds, next=guilds[-1].id if guilds else None)
        raise NotFoundException("qq platform does not support guild.list")

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            res = await net.call_api(
                "get",
                f"channels/{channel_id}",
            )
            return decode_channel(res)
        raise NotFoundException("qq platform does not support channel.get")

    @adapter.route(Api.CHANNEL_LIST)
    async def channel_list(request: Request[ChannelListParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            res = await net.call_api(
                "get",
                f"guilds/{guild_id}/channels",
            )
            channels = [decode_channel(channel) for channel in res]
            return PageResult(channels, next=None)
        raise NotFoundException("qq platform does not support channel.list")

    @adapter.route(Api.CHANNEL_CREATE)
    async def channel_create(request: Request[ChannelCreateParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            data = request.params["data"]
            res = await net.call_api(
                "post",
                f"guilds/{guild_id}/channels",
                {
                    "name": data["name"],
                    "type": {ChannelType.TEXT.value: 0, ChannelType.VOICE.value: 2, ChannelType.CATEGORY.value: 4}.get(
                        data.get("type", ChannelType.TEXT.value), 0
                    ),
                    "parent_id": data.get("parent_id"),
                    "sub_type": 0,
                    "speak_permission": 1,
                },
            )
            return decode_channel(res)
        raise NotFoundException("qq platform does not support channel.create")

    @adapter.route(Api.CHANNEL_UPDATE)
    async def channel_update(request: Request[ChannelUpdateParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            data = request.params["data"]
            await net.call_api(
                "patch",
                f"channels/{channel_id}",
                {
                    "name": data.get("name"),
                    "parent_id": data.get("parent_id"),
                },
            )
        else:
            raise NotFoundException("qq platform does not support channel.update")

    @adapter.route(Api.CHANNEL_DELETE)
    async def channel_delete(request: Request[ChannelParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            await net.call_api(
                "delete",
                f"channels/{channel_id}",
            )
        else:
            raise NotFoundException("qq platform does not support channel.delete")

    @adapter.route(Api.GUILD_MEMBER_GET)
    async def guild_get_member(request: Request[GuildMemberGetParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            res = await net.call_api(
                "get",
                f"guilds/{guild_id}/members/{request.params['user_id']}",
            )
            return decode_member(res)
        raise NotFoundException("qq platform does not support guild.member.get")

    @adapter.route(Api.GUILD_MEMBER_LIST)
    async def guild_list_member(request: Request[GuildXXXListParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            res = await net.call_api(
                "get",
                f"guilds/{guild_id}/members",
                {"limit": 400, "after": request.params["next"] if "next" in request.params else "0"},
            )
            members = [decode_member(member) for member in res]
            return PageResult(members, next=members[-1].user.id if members else None)  # type: ignore
        raise NotFoundException("qq platform does not support guild.member.list")

    @adapter.route(Api.GUILD_MEMBER_KICK)
    async def guild_kick_member(request: Request[GuildMemberKickParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            await net.call_api(
                "delete",
                f"guilds/{guild_id}/members/{request.params['user_id']}",
            )
        else:
            raise NotFoundException("qq platform does not support guild.member.kick")

    @adapter.route(Api.GUILD_MEMBER_MUTE)
    async def guild_mute_member(request: Request[GuildMemberMuteParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            await net.call_api(
                "patch",
                f"guilds/{guild_id}/members/{request.params['user_id']}/mute",
                {"mute_seconds": request.params.get("duration", 0) // 1000},
            )
        else:
            raise NotFoundException("qq platform does not support guild.member.mute")

    @adapter.route(Api.REACTION_LIST)
    async def reaction_list(request: Request[ReactionListParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            if ":" in request.params["emoji"]:
                type_, emoji_id = request.params["emoji"].split(":", maxsplit=1)
            else:
                type_, emoji_id = "1", request.params["emoji"]
            res = await net.call_api(
                "get",
                f"channels/{channel_id}/messages/{request.params['message_id']}/reactions/{type_}/{emoji_id}",
                {
                    "limit": 50,
                    "cookie": request.params.get("next"),
                },
            )
            users = [decode_user(user) for user in res["users"]]
            return PageResult(users, next=None if res["is_end"] else res["cookie"])
        raise NotFoundException("qq platform does not support reaction.list")

    @adapter.route(Api.REACTION_CREATE)
    async def reaction_create(request: Request[ReactionCreateParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            if ":" in request.params["emoji"]:
                type_, emoji_id = request.params["emoji"].split(":", maxsplit=1)
            else:
                type_, emoji_id = "1", request.params["emoji"]
            await net.call_api(
                "put",
                f"channels/{channel_id}/messages/{request.params['message_id']}/reactions/{type_}/{emoji_id}/",
            )
        else:
            raise NotFoundException("qq platform does not support reaction.create")

    @adapter.route(Api.REACTION_DELETE)
    async def reaction_delete(request: Request[ReactionDeleteParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            channel_id = request.params["channel_id"].split("_")[-1]
            if ":" in request.params["emoji"]:
                type_, emoji_id = request.params["emoji"].split(":", maxsplit=1)
            else:
                type_, emoji_id = "1", request.params["emoji"]
            await net.call_api(
                "delete",
                f"channels/{channel_id}/messages/{request.params['message_id']}/reactions/{type_}/{emoji_id}/",
            )
        else:
            raise NotFoundException("qq platform does not support reaction.delete")

    @adapter.route(Api.GUILD_ROLE_LIST)
    async def guild_list_role(request: Request[GuildXXXListParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            res = await net.call_api(
                "get",
                f"guilds/{guild_id}/roles",
            )
            roles = [Role(role["id"], role.get("name", "")) for role in res]
            return PageResult(roles, next=None)
        raise NotFoundException("qq platform does not support guild.role.list")

    @adapter.route(Api.GUILD_ROLE_CREATE)
    async def guild_create_role(request: Request[GuildRoleCreateParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            data = request.params["role"]
            res = await net.call_api(
                "post",
                f"guilds/{guild_id}/roles",
                {
                    "name": data.get("name"),
                    "color": data.get("color"),
                    "hoist": data.get("hoist"),
                },
            )
            return Role(res["role"]["id"], res["role"]["name"])
        raise NotFoundException("qq platform does not support guild.role.create")

    @adapter.route(Api.GUILD_ROLE_DELETE)
    async def guild_delete_role(request: Request[GuildRoleDeleteParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            await net.call_api(
                "delete",
                f"guilds/{guild_id}/roles/{request.params['role_id']}",
            )
        else:
            raise NotFoundException("qq platform does not support guild.role.delete")

    @adapter.route(Api.GUILD_ROLE_UPDATE)
    async def guild_update_role(request: Request[GuildRoleUpdateParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            data = request.params["role"]
            await net.call_api(
                "patch",
                f"guilds/{guild_id}/roles/{request.params['role_id']}",
                {
                    "name": data.get("name"),
                    "color": data.get("color"),
                    "hoist": data.get("hoist"),
                },
            )
        else:
            raise NotFoundException("qq platform does not support guild.role.update")

    @adapter.route(Api.GUILD_MEMBER_ROLE_SET)
    async def guild_add_member_role(request: Request[GuildMemberRoleParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            await net.call_api(
                "put",
                f"guilds/{guild_id}/members/{request.params['user_id']}/roles/{request.params['role_id']}",
            )
        else:
            raise NotFoundException("qq platform does not support guild.member.role.add")

    @adapter.route(Api.GUILD_MEMBER_ROLE_UNSET)
    async def guild_remove_member_role(request: Request[GuildMemberRoleParam]):
        net = net_getter(request.self_id, request.platform == "qqguild")
        if request.platform == "qqguild":
            guild_id = request.params["guild_id"].split("_")[0]
            await net.call_api(
                "delete",
                f"guilds/{guild_id}/members/{request.params['user_id']}/roles/{request.params['role_id']}",
            )
        else:
            raise NotFoundException("qq platform does not support guild.member.role.remove")
