from __future__ import annotations

import asyncio

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


class ConsoleAdapter(BaseAdapter):
    def __init__(
        self,
        logger_id: int = -1,
        title: str = "Console",
        sub_title: str = "powered by Textual",
        room_title: str | None = None,
        icon: str | None = None,
        toolbar_exit: str = "⛔",
        toolbar_clear: str = "🗑️",
        toolbar_setting: str = "⚙️",
        toolbar_log: str = "📝",
        toolbar_fold: str = "⏪",
        toolbar_expand: str = "⏩",
        user_avatar: str = "👤",
        user_name: str = "User",
        bot_avatar: str = "🤖",
        bot_name: str = "Bot",
        new_message_color: str = "lime blink",
    ):
        kwargs = locals().copy()
        kwargs.pop("self")
        kwargs.pop("logger_id")
        kwargs.pop("__class__")
        super().__init__()
        self.app = Frontend(
            SatoriConsoleBackend,
            ConsoleSetting(**kwargs),
        )
        self.app.backend.set_adapter(self)
        self._logger_id = logger_id
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
