import asyncio
from datetime import datetime

from satori import Api, Channel, ChannelType, Event, Login, LoginStatus, User, MessageObject, Text
from satori.server import Server, Request, route

server = Server(host="localhost", port=12345, path="foo")


class ExampleProvider:
    def authenticate(self, token: str) -> bool:
        return True

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example")]

    async def publisher(self):
        seq = 0
        while True:
            await asyncio.sleep(2)
            yield Event(
                seq,
                "message-created",
                "example",
                "1234567890",
                datetime.now(),
                channel=Channel("345678", ChannelType.TEXT),
                user=User("9876543210"),
                message=MessageObject(
                    f"msg_{seq}", "test"
                )
            )
            seq += 1


server.apply(ExampleProvider())


@server.route(Api.CHANNEL_GET)
async def handle1(request: Request[route.ChannelParam]):
    return Channel("1234567890", ChannelType.TEXT, "test").dump()


@server.route(Api.MESSAGE_CREATE)
async def handle2(request: Request[route.MessageParam]):
    a = request.params["content"]
    return [MessageObject.from_elements("1234", [Text("example")])]


server.run()
