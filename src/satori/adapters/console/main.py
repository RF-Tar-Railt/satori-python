import asyncio

from launart import Launart
from launart.status import Phase
from nonechat import ConsoleSetting, Frontend
from starlette.responses import JSONResponse, Response

from satori.server import Adapter as BaseAdapter
from satori.server import Request
from satori.server.adapter import LoginType

from .api import apply
from .backend import SatoriConsoleBackend


class ConsoleAdapter(BaseAdapter):
    def __init__(self, **kwargs):
        super().__init__()
        self.app = Frontend(
            SatoriConsoleBackend,
            ConsoleSetting(**kwargs),
        )
        self.app.backend.set_adapter(self)
        self.queue = asyncio.Queue()
        apply(self)

    @property
    def id(self):
        return f"satori-python.adapter.console#{id(self)}"

    def get_platform(self) -> str:
        return "console"

    async def publisher(self):
        while True:
            event = await self.queue.get()
            yield event

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "console" and self_id == self.app.backend.bot.id

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            api = path[5:]
            data = await request.origin.json()
            if api == "send_msg":
                self.app.send_message(**data)
                return JSONResponse({})
            if api == "bell":
                await self.app.toggle_bell()
                return JSONResponse({})
            else:
                return Response(f"Unknown API: {api}", status_code=404)
        async with self.server.session.get(path) as resp:
            return Response(await resp.read())

    async def get_logins(self) -> list[LoginType]:
        return [self.app.backend.login]

    @property
    def required(self) -> set[str]:
        return {
            "satori-python.server",
        }

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    async def launch(self, manager: Launart):

        async with self.stage("preparing"):
            ...

        async with self.stage("blocking"):
            task = asyncio.create_task(self.app.run_async())
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            self.app.exit()
            if task:
                await task
