import asyncio
from datetime import datetime

from launart import Launart

from satori import Api, Channel, ChannelType, Event, User
from satori.model import Login, LoginStatus, MessageObject
from satori.server import Adapter, Request, route


class ExampleAdapter(Adapter):
    async def download_uploaded(self, platform: str, self_id: str, path: str) -> bytes:
        raise NotImplementedError

    @property
    def required(self):
        return set()

    @property
    def stages(self):
        return {"blocking"}

    def get_platform(self) -> str:
        return "example"

    # def validate_headers(self, headers: dict) -> bool:
    #     return headers["X-Platform"] == self.get_platform()

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == self.get_platform() and self_id == "1234567890"

    def authenticate(self, token: str) -> bool:
        return True

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example")]

    def __init__(self):
        super().__init__()

        @self.route(Api.MESSAGE_CREATE)
        async def _(request: Request[route.MessageParam]):
            return [MessageObject("1234", request.params["content"])]

    async def publisher(self):
        seq = 0
        while True:
            await asyncio.sleep(2)
            yield Event(
                seq,
                "message-created",
                self.get_platform(),
                "1234567890",
                datetime.now(),
                channel=Channel("345678", ChannelType.TEXT),
                user=User("9876543210"),
                message=MessageObject(f"msg_{seq}", "test"),
            )
            seq += 1

    async def launch(self, manager: Launart):
        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()
