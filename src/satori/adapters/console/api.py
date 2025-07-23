from typing import TYPE_CHECKING

from nonechat.message import ConsoleMessage, Markdown
from nonechat.message import Text as ConsoleText

from satori.const import Api
from satori.element import At, Text, transform
from satori.model import Channel, ChannelType, Guild, Member, MessageObject, PageResult, User
from satori.parser import parse
from satori.server import Request
from satori.server.route import (
    ChannelListParam,
    ChannelParam,
    FriendListParam,
    GuildGetParam,
    GuildListParam,
    GuildMemberGetParam,
    GuildXXXListParam,
    MessageParam,
    UserChannelCreateParam,
    UserGetParam,
)

if TYPE_CHECKING:
    from .main import ConsoleAdapter


def decode(content: str) -> ConsoleMessage:
    elements = []
    msg = transform(parse(content))
    for seg in msg:
        if isinstance(seg, Text):
            elements.append(ConsoleText(seg.text))
        elif isinstance(seg, At):
            elements.append(ConsoleText(f"@{seg.id}"))
        else:
            elements.append(Markdown(str(seg)))
    return ConsoleMessage(elements)


def apply(adapter: "ConsoleAdapter"):
    @adapter.route(Api.USER_GET)
    async def user_get(request: Request[UserGetParam]) -> User:
        user_id = request.params["user_id"]
        ans = await adapter.app.backend.get_user(user_id)
        return User(
            ans.id,
            ans.nickname,
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(ans.avatar):x}.png",
        )

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]) -> Channel:
        channel_id = request.params["channel_id"]
        ans = await adapter.app.backend.get_channel(channel_id)
        if not ans:
            raise ValueError(f"Channel {channel_id} not found")
        return Channel(
            ans.id,
            ChannelType.TEXT,
            ans.name,
        )

    @adapter.route(Api.GUILD_GET)
    async def guild_get(request: Request[GuildGetParam]) -> Guild:
        guild_id = request.params["guild_id"]
        ans = await adapter.app.backend.get_channel(guild_id)
        return Guild(
            ans.id,
            ans.name,
            f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(ans.avatar):x}.png",
        )

    @adapter.route(Api.FRIEND_LIST)
    async def friend_list(request: Request[FriendListParam]) -> PageResult[User]:
        return PageResult(
            [
                User(
                    user.id,
                    user.nickname,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
                )
                for user in await adapter.app.backend.list_users()
            ]
        )

    @adapter.route(Api.GUILD_LIST)
    async def guild_list(request: Request[GuildListParam]) -> PageResult[Guild]:
        return PageResult(
            [
                Guild(
                    channel.id,
                    channel.name,
                    f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(channel.avatar):x}.png",
                )
                for channel in await adapter.app.backend.list_channels()
            ]
        )

    @adapter.route(Api.CHANNEL_LIST)
    async def channel_list(request: Request[ChannelListParam]) -> PageResult[Channel]:
        return PageResult(
            [
                Channel(
                    channel.id,
                    ChannelType.TEXT,
                    channel.name,
                )
                for channel in await adapter.app.backend.list_channels()
            ]
        )

    @adapter.route(Api.GUILD_MEMBER_GET)
    async def guild_member_get(request: Request[GuildMemberGetParam]) -> Member:
        user_id = request.params["user_id"]
        ans = await adapter.app.backend.get_user(user_id)
        user = User(
            ans.id,
            ans.nickname,
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(ans.avatar):x}.png",
        )
        return Member(user, user.name, user.avatar)

    @adapter.route(Api.GUILD_MEMBER_LIST)
    async def guild_member_list(request: Request[GuildXXXListParam]) -> PageResult[Member]:
        members = [
            Member(
                User(
                    user.id,
                    user.nickname,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
                ),
                user.nickname,
                f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
            )
            for user in await adapter.app.backend.list_users()
        ]
        return PageResult(members)

    @adapter.route(Api.USER_CHANNEL_CREATE)
    async def user_channel_create(request: Request[UserChannelCreateParam]) -> Channel:
        user_id = request.params["user_id"]
        user = await adapter.app.backend.get_user(user_id)
        channel = Channel(
            id=f"private:{user.id}",
            type=ChannelType.DIRECT,
            name=user.nickname,
        )
        return channel

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        content = request.params["content"]
        channel_id = request.params["channel_id"]

        if channel_id.startswith("private:"):
            user_id = channel_id.split(":")[1]
            user = await adapter.app.backend.get_user(user_id)
            target = await adapter.app.backend.create_dm(user)
        else:
            target = await adapter.app.backend.get_channel(channel_id)

        bot = next((b for b in await adapter.app.backend.list_bots() if b.id == request.self_id), None)
        await adapter.app.send_message(decode(content), target, bot)  # type: ignore
        return [MessageObject("", content)]

    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return adapter.app.backend.logins[request.self_id]

    @adapter.route("bell")
    async def bell(request: Request):
        await adapter.app.toggle_bell()
        return
