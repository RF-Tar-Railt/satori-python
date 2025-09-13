from adapter import ExampleAdapter

from satori import Api, Channel, ChannelType
from satori.server import Response, Server, StarletteRequest

server = Server(host="localhost", port=12345, path="foo")
server.apply(ExampleAdapter())


@server.route(Api.CHANNEL_GET)
async def handle(*args, **kwargs):
    return Channel("1234567890", ChannelType.TEXT, "test").dump()


@server.asgi_route("/api/v1/test")
async def exam_route(request: StarletteRequest):
    return Response(str(dict(request.items())))


server.run()
