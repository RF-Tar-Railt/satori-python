from collections.abc import Callable

from satori import Api, Login
from satori.adapters.qqbot.utils import QQBotNetwork
from satori.server import Adapter, Request
from satori.server.route import MessageParam

from .message import QQGroupMessageEncoder, QQGuildMessageEncoder


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
