from typing import cast

from launart import Launart, any_completed
from launart.status import Phase
from starlette.datastructures import FormData
from starlette.responses import JSONResponse, Response

from satori import Api
from satori.client import App, WebsocketsInfo
from satori.exception import ActionFailed
from satori.server import Adapter as BaseAdapter
from satori.server import Request
from satori.server.adapter import LoginType
from satori.utils import decode


class SatoriAdapter(BaseAdapter):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5140,
        path: str = "",
        token: str | None = None,
        post_upload: bool = False,
    ):
        super().__init__()
        self.app = App(WebsocketsInfo(host, port, path, token), main_app=False)

        @self.app.register
        async def _(acc, event):
            await self.server.post(event)

        self.routes |= {api.value: self._handle_request for api in Api.__members__.values()}
        if not post_upload:
            self.routes.pop(Api.UPLOAD_CREATE.value, None)

    @property
    def id(self):
        return f"satori-python.adapter.satori#{id(self)}"

    @property
    def account(self):
        return next(iter(self.app.accounts.values()), None)

    def get_platform(self) -> str:
        if acc := self.account:
            return acc.self_info.platform
        return "satori"

    def ensure(self, platform: str, self_id: str) -> bool:
        if not (acc := self.account):
            return False
        return acc.platform == platform and acc.self_info.user.id == self_id

    async def _handle_request(self, request: Request):
        if not (acc := self.account):
            return Response("No account found", status_code=404)
        if request.action == Api.UPLOAD_CREATE.value:
            data = cast(FormData, request.params)
            files = {
                k: (
                    v
                    if isinstance(v, str)
                    else {"value": v.file.read(), "content_type": v.content_type, "filename": v.filename}
                )
                for k, v in data.items()
            }
            return await acc.protocol.call_api(request.action, files, multipart=True)
        return await acc.protocol.call_api(request.action, request.params)

    async def handle_internal(self, request: Request, path: str) -> Response:
        if path.startswith("_api"):
            if not (acc := self.account):
                return Response("No account found", status_code=404)
            try:
                return JSONResponse(
                    await acc.protocol.call_api(
                        path[5:], decode(await request.origin.body()), method=request.origin.method
                    )
                )
            except ActionFailed as e:
                return Response(str(e), status_code=500)
        if acc := self.account:
            return Response(await self.account.protocol.download(f"internal:{acc.platform}/{acc.self_id}/{path}"))
        async with self.server.session.get(path) as resp:
            return Response(await resp.read())

    async def get_logins(self) -> list[LoginType]:
        if not (acc := self.account):
            return []
        return [acc.self_info]

    @property
    def required(self) -> set[str]:
        return {
            "satori-python.server",
        }

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    async def launch(self, manager: Launart):
        manager.add_component(self.app.connections[0])

        async with self.stage("preparing"):
            pass

        async with self.stage("blocking"):
            await any_completed(
                self.app.connections[0].status.wait_for("blocking-completed"),
                manager.status.wait_for_sigexit(),
            )

        async with self.stage("cleanup"):
            pass


Adapter = SatoriAdapter
