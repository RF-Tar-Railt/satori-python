from __future__ import annotations

from collections.abc import Callable

from satori import Api
from satori.model import Channel, ChannelType, Login, User
from satori.server import Adapter, Request
from satori.server.route import ChannelParam, MessageParam, UserChannelCreateParam, UserOpParam

from .message import WxClawMessageEncoder
from .network import WxClawNetwork


def _direct_channel(channel_id: str) -> Channel:
    if not channel_id.startswith("private:") or not channel_id.removeprefix("private:"):
        raise ValueError("WxClaw only supports direct channels with the 'private:' prefix")
    return Channel(channel_id, ChannelType.DIRECT)


def apply(
    adapter: Adapter,
    net_getter: Callable[[str], WxClawNetwork],
    login_getter: Callable[[str], Login],
):
    @adapter.route(Api.LOGIN_GET)
    async def login_get(request: Request):
        return login_getter(request.self_id)

    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        network = net_getter(request.self_id)
        login = login_getter(request.self_id)
        encoder = WxClawMessageEncoder(
            login,
            network,
            request.params["channel_id"],
            request.params.get("referrer"),
        )
        return await encoder.send(request.params["content"])

    @adapter.route(Api.CHANNEL_GET)
    async def channel_get(request: Request[ChannelParam]):
        return _direct_channel(request.params["channel_id"])

    @adapter.route(Api.USER_CHANNEL_CREATE)
    async def user_channel_create(request: Request[UserChannelCreateParam]):
        return Channel(f"private:{request.params['user_id']}", ChannelType.DIRECT)

    @adapter.route(Api.USER_GET)
    async def user_get(request: Request[UserOpParam]):
        user_id = request.params["user_id"]
        return User(user_id, user_id)

    @adapter.route("*")
    async def internal_api(request: Request[dict]):
        network = net_getter(request.self_id)
        action = request.action.removeprefix("internal/")
        return await network.call_internal(action, request.params)
