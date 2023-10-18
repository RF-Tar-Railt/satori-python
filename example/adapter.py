import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable

from launart import Launart, any_completed
from starlette.datastructures import Headers

from satori import Adapter, Channel, ChannelType, Event, User
from satori.model import Login, LoginStatus


class ExampleAdapter(Adapter):

    @property
    def required(self):
        return set()

    @property
    def stages(self):
        return {"blocking"}

    def get_platform(self) -> str:
        return "example"

    def bind_event_callback(self, callback: Callable[[Event], Awaitable[Any]]):
        self.event_callback = callback

    def validate_headers(self, headers: Headers) -> bool:
        return headers["X-Platform"] == self.get_platform()

    def authenticate(self, token: str) -> bool:
        return True

    async def get_logins(self):
        return [Login(LoginStatus.ONLINE, self_id="1234567890", platform="example")]

    async def call_api(self, headers: Headers, action: str, params=None) -> Any:
        print(headers, action, params)
        return [{"id": "1234", "content": "example"}]

    async def daemon(self):
        seq = 0
        while True:
            await asyncio.sleep(2)
            await self.event_callback(
                Event(
                    seq,
                    "example",
                    self.get_platform(),
                    "1234567890",
                    datetime.now(),
                    channel=Channel(
                        "1234567890",
                        ChannelType.DIRECT,
                    ),
                    user=User(
                        "1234567890",
                    ),
                )
            )
            seq += 1

    async def launch(self, manager: Launart):
        async with self.stage("blocking"):
            await any_completed(
                manager.status.wait_for_sigexit(),
                self.daemon(),
            )
