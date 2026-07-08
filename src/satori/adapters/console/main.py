from __future__ import annotations

import asyncio
from dataclasses import dataclass

from creart import it
from launart import Launart, any_completed
from launart.status import Phase
from nonechat import ConsoleSetting, Frontend
from starlette.responses import JSONResponse, Response

from satori.server import Adapter as BaseAdapter
from satori.server import Request
from satori.server.adapter import LoginType

from .api import apply
from .backend import SatoriConsoleBackend


@dataclass
class ConsoleConfig(ConsoleSetting):
    logger_id: int = -1
    """Loguru logger 的 handler id，用以将控制台输出重定向到 Satori Console 中。"""


class ConsoleAdapter(BaseAdapter[ConsoleConfig]):
    def __init__(
        self,
        config: ConsoleConfig | None = None,
    ):
        kwargs = locals().copy()
        kwargs.pop("self")
        kwargs.pop("logger_id")
        kwargs.pop("__class__")
        super().__init__()
        self.config = config or ConsoleConfig()
        self.app = Frontend(
            SatoriConsoleBackend,
            self.config,
        )
        self.app.backend.set_adapter(self)
        apply(self)

    @property
    def id(self):
        return f"satori-python.adapter.console#{id(self)}"

    def get_platform(self) -> str:
        return "console"

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "console" and self_id in self.app.backend.logins

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            api = path[5:]
            data = await request.origin.json()
            if api == "send_msg":
                await self.app.send_message(**data)
                return JSONResponse({})
            if api == "bell":
                await self.app.toggle_bell()
                return JSONResponse({})
            else:
                return Response(f"Unknown API: {api}", status_code=404)
        async with self.server.session.get(path) as resp:
            return Response(await resp.read())

    async def get_logins(self) -> list[LoginType]:
        return list(self.app.backend.logins.values())

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
            task = it(asyncio.AbstractEventLoop).create_task(self.app.run_async())
            await any_completed(
                manager.status.wait_for_sigexit(),
                task,
            )

        async with self.stage("cleanup"):
            self.app.exit()
            if task:
                await task


Adapter = ConsoleAdapter
