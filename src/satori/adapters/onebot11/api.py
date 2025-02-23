from typing import Callable

from satori import Api
from satori.model import Login, MessageObject
from satori.server import Adapter, Request
from satori.server.route import MessageOpParam, MessageParam

from .message import OneBot11MessageEncoder, decode
from .utils import OneBotNetwork


def apply(adapter: Adapter, net_getter: Callable[[str], OneBotNetwork], login_getter: Callable[[str], Login]):
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
        assert result
        return MessageObject(
            request.params["message_id"],
            await decode(result["message"], net),
            # TODO: info of guild, channel, user
        )

    @adapter.route(Api.MESSAGE_DELETE)
    async def message_delete(request: Request[MessageOpParam]):
        net = net_getter(request.self_id)
        await net.call_api("delete_msg", {"message_id": int(request.params["message_id"])})
        return
