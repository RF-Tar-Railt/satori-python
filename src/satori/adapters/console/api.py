from typing import TYPE_CHECKING

from satori.const import Api
from satori.model import Channel, ChannelType, Guild, Member, MessageObject, PageDequeResult, PageResult, User
from satori.server import Request
from satori.server.route import (
    ChannelListParam,
    ChannelParam,
    FriendListParam,
    GuildGetParam,
    GuildListParam,
    GuildMemberGetParam,
    GuildXXXListParam,
    MessageListParam,
    MessageOpParam,
    MessageParam,
    MessageUpdateParam,
    UserChannelCreateParam,
    UserGetParam,
)

from .message import decode_message, encode_message

if TYPE_CHECKING:
    from .main import ConsoleAdapter


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
        message_id = await adapter.app.send_message(decode_message(content), target, bot)  # type: ignore
        return [MessageObject(message_id, content)]

    @adapter.route(Api.MESSAGE_GET)
    async def message_get(request: Request[MessageOpParam]) -> MessageObject:
        message_id = request.params["message_id"]
        channel_id = request.params["channel_id"]
        if channel_id.startswith("private:"):
            user_id = channel_id.split(":")[1]
            user = await adapter.app.backend.get_user(user_id)
            channel = await adapter.app.backend.create_dm(user)
        else:
            channel = await adapter.app.backend.get_channel(channel_id)
        event = await adapter.app.backend.get_chat(message_id, channel)
        if not event:
            raise ValueError(f"Message {message_id} not found in channel {channel_id}")
        return MessageObject(message_id, encode_message(event.message))

    @adapter.route(Api.MESSAGE_LIST)
    async def message_list(request: Request[MessageListParam]) -> PageDequeResult[MessageObject]:
        channel_id = request.params["channel_id"]
        if channel_id.startswith("private:"):
            user_id = channel_id.split(":")[1]
            user = await adapter.app.backend.get_user(user_id)
            channel = await adapter.app.backend.create_dm(user)
        else:
            channel = await adapter.app.backend.get_channel(channel_id)
        messages = await adapter.app.backend.get_chat_history(channel)
        return PageDequeResult(
            [
                MessageObject(
                    event.message_id,
                    encode_message(event.message),
                )
                for i, event in enumerate(messages)
            ]
        )

    @adapter.route(Api.MESSAGE_UPDATE)
    async def message_update(request: Request[MessageUpdateParam]) -> None:
        content = request.params["content"]
        message_id = request.params["message_id"]
        channel_id = request.params["channel_id"]
        if channel_id.startswith("private:"):
            user_id = channel_id.split(":")[1]
            user = await adapter.app.backend.get_user(user_id)
            channel = await adapter.app.backend.create_dm(user)
        else:
            channel = await adapter.app.backend.get_channel(channel_id)

        await adapter.app.edit_message(message_id, decode_message(content), channel)

    @adapter.route(Api.MESSAGE_DELETE)
    async def message_delete(request: Request[MessageOpParam]) -> None:
        message_id = request.params["message_id"]
        channel_id = request.params["channel_id"]
        if channel_id.startswith("private:"):
            user_id = channel_id.split(":")[1]
            user = await adapter.app.backend.get_user(user_id)
            channel = await adapter.app.backend.create_dm(user)
        else:
            channel = await adapter.app.backend.get_channel(channel_id)

        await adapter.app.recall_message(message_id, channel)

    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return adapter.app.backend.logins[request.self_id]

    @adapter.route("bell")
    async def bell(request: Request):
        await adapter.app.toggle_bell()
        return
