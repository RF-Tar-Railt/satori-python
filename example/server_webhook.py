from adapter import ExampleAdapter

from satori import Api, Channel, ChannelType
from satori.server import Server, WebhookEndpoint

server = Server(host="localhost", port=12345, webhooks=[WebhookEndpoint("http://localhost:8080/bar")])
server.apply(ExampleAdapter())


@server.route(Api.CHANNEL_GET)
async def handle(*args, **kwargs):
    return Channel("1234567890", ChannelType.TEXT, "test").dump()


server.run()
