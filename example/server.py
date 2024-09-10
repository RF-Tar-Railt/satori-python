import asyncio
from datetime import datetime

from satori import Api, Channel, ChannelType, Event, Login, LoginStatus, MessageObject, Text, User
from satori.server import Request, Server, route

server = Server(host="localhost", port=12345, path="foo")


class ExampleProvider:
    @property
    def id(self):
        return "example"

    def authenticate(self, token) -> bool:
        return True

    @staticmethod
    def proxy_urls():
        return []

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "example" and self_id == "1234567890"

    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes:
        raise NotImplementedError

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example", user=User("1234567890"))]

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
                message=MessageObject(f"msg_{seq}", "/hitokoto"),
            )
            seq += 1


server.apply(ExampleProvider())

sent = True


@server.route(Api.CHANNEL_GET)
async def handle1(request: Request[route.ChannelParam]):
    global sent

    async def _():
        await asyncio.sleep(5)
        await server.connections[0].connection.close()

    if not sent:
        _t = asyncio.create_task(_())
        sent = True
    return Channel("1234567890", ChannelType.TEXT, "test").dump()


@server.route(Api.MESSAGE_CREATE)
async def handle2(request: Request[route.MessageParam]):
    return [MessageObject.from_elements("1234", [Text("example")])]


server.run()
