import asyncio
from datetime import datetime

from satori import Api, Channel, ChannelType, Event, Login, LoginStatus, Server, User

server = Server(host="localhost", port=12345)


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
                "example",
                "example",
                "1234567890",
                datetime.now(),
                channel=Channel("1234567890", ChannelType.TEXT),
                user=User("1234567890"),
            )
            seq += 1


server.apply(ExampleProvider())


@server.route(Api.CHANNEL_GET)
async def handle1(*args, **kwargs):
    return Channel("1234567890", ChannelType.TEXT, "test").dump()


@server.route(Api.MESSAGE_CREATE)
async def handle2(*args, **kwargs):
    return [{"id": "1234", "content": "example"}]


server.run()
