from collections.abc import Callable

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

from .message import MilkyMessageEncoder, parse_message_object
from .utils import GROUP_AVATAR_URL, USER_AVATAR_URL, MilkyNetwork

# Milky-specific APIs that can be called directly
INTERNAL_API = [
    "get_login_info",
    "get_status",
    "get_version_info",
    # Add more milky-specific APIs as needed
]


def apply(adapter: Adapter, net_getter: Callable[[str], MilkyNetwork], login_getter: Callable[[str], Login]):
    encoder = MilkyMessageEncoder()

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        net = net_getter(request.self_id)
        encoded = encoder.encode(request.params["content"])
        
        # Adapt to milky protocol message sending format
        result = await net.call_api(
            "send_message",
            {
                "channel_id": request.params["channel_id"],
                "message": encoded,
            },
        )
        
        if result:
            return [parse_message_object(result)]
        return []

    @adapter.route(Api.MESSAGE_GET)
    async def message_get(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_message",
            {
                "message_id": request.params["message_id"],
            },
        )
        
        if result:
            return parse_message_object(result)
        return None

    @adapter.route(Api.MESSAGE_DELETE)
    async def message_delete(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        await net.call_api(
            "delete_message",
            {
                "message_id": request.params["message_id"],
            },
        )
        return

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_channel_info",
            {
                "channel_id": request.params["channel_id"],
            },
        )
        
        if result:
            return Channel(
                id=str(result["channel_id"]),
                type=ChannelType.TEXT,
                name=result.get("channel_name", ""),
            )
        return None

    @adapter.route(Api.CHANNEL_LIST)
    async def channel_list(request: Request[ChannelListParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_channel_list", {"guild_id": request.params["guild_id"]})
        
        if result:
            return PageResult(
                data=[
                    Channel(
                        id=str(channel["channel_id"]),
                        type=ChannelType.TEXT,
                        name=channel.get("channel_name", ""),
                    )
                    for channel in result
                ]
            )
        return PageResult(data=[])

    @adapter.route(Api.USER_GET)
    async def user_get(request: Request[UserGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_user_info",
            {
                "user_id": request.params["user_id"],
            },
        )
        
        if result:
            return User(
                id=str(result["user_id"]),
                name=result.get("nickname", ""),
                avatar=USER_AVATAR_URL.format(uin=result["user_id"]),
            )
        return None

    @adapter.route(Api.GUILD_GET)
    async def guild_get(request: Request[GuildGetParam]):
        net = net_getter(request.self_id)
        result = await net.call_api(
            "get_guild_info",
            {
                "guild_id": request.params["guild_id"],
            },
        )
        
        if result:
            return Guild(
                id=str(result["guild_id"]),
                name=result.get("guild_name", ""),
                avatar=GROUP_AVATAR_URL.format(group=result["guild_id"]),
            )
        return None

    @adapter.route(Api.GUILD_LIST)
    async def guild_list(request: Request[GuildListParam]):
        net = net_getter(request.self_id)
        result = await net.call_api("get_guild_list")
        
        if result:
            return PageResult(
                data=[
                    Guild(
                        id=str(guild["guild_id"]),
                        name=guild.get("guild_name", ""),
                        avatar=GROUP_AVATAR_URL.format(group=guild["guild_id"]),
                    )
                    for guild in result
                ]
            )
        return PageResult(data=[])

    # Handle internal APIs directly
    for api in INTERNAL_API:
        @adapter.route(api)
        async def internal_api(request: Request[dict]):
            net = net_getter(request.self_id)
            return await net.call_api(api, request.params)