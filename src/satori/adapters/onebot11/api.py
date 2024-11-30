from typing import Callable

from satori import Api
from satori.model import LoginPreview
from satori.server import Adapter, Request
from satori.server.route import MessageParam

from .message import OneBot11MessageEncoder
from .utils import OneBotNetwork


def apply(
    adapter: Adapter, net_getter: Callable[[str], OneBotNetwork], login_getter: Callable[[str], LoginPreview]
):
    @adapter.route(Api.MESSAGE_CREATE)
    async def message_create(request: Request[MessageParam]):
        net = net_getter(request.self_id)
        login = login_getter(request.self_id)
        encoder = OneBot11MessageEncoder(login, net, request.params["channel_id"])
        await encoder.send(request.params["content"])
        return encoder.results
