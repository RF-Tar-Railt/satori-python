from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Any, Awaitable, Callable, Iterable

from creart import it
from graia.amnesia.builtins.asgi import UvicornASGIService
from launart import Launart, Service, any_completed
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from .adapter import Adapter
from .model import Event, Opcode
from .network.ws_server import WsServerConnection


class Server(Service):
    id = "satori-python.server"
    required: set[str] = {"asgi.service/uvicorn"}
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    adapters: list[Adapter]
    connections: list[WsServerConnection]

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5140,
        version: str = "v1",
    ):
        self.connections = []
        manager = it(Launart)
        manager.add_component(UvicornASGIService(host, port))
        self.ws_route = WebSocketRoute(f"/{version}/events", self.websocket_server_handler)
        self.adapters = []
        self.handlers = {}
        super().__init__()

    def apply(self, adapter: Adapter):
        self.adapters.append(adapter)
        adapter.bind_event_callback(self.event_callback)

    def override(self, path: str):
        def wrapper(func: Callable[[Headers, Any], Awaitable[Any]]):
            async def handler(request: Request):
                res = await func(request.headers, await request.json())
                return res if isinstance(res, Response) else JSONResponse(content=res)

            self.handlers[path] = handler
            return func

        return wrapper

    async def event_callback(self, event: Event):
        for connection in self.connections:
            await connection.send({"op": Opcode.EVENT, "body": event.dump()})

    async def websocket_server_handler(self, ws: WebSocket):
        await ws.accept()
        connection = WsServerConnection(ws)
        identity = await ws.receive_json()
        if not isinstance(identity, dict) or identity.get("op") != Opcode.IDENTIFY:
            return await ws.close(code=3000, reason="Unauthorized")
        token = identity["body"]["token"]
        logins = []
        for adapter in self.adapters:
            if not adapter.authenticate(token):
                return await ws.close(code=3000, reason="Unauthorized")
            logins.extend(await adapter.get_logins())
        await connection.send({"op": Opcode.READY, "body": {"logins": [lo.dump() for lo in logins]}})
        self.connections.append(connection)

        try:
            await any_completed(connection.heartbeat(), connection.close_signal.wait())
        finally:
            self.connections.remove(connection)

    async def http_server_handler(self, request: Request):
        if not self.adapters:
            return Response(status_code=404)
        for adapter in self.adapters:
            if adapter.validate_headers(request.headers):
                res = await adapter.call_api(
                    request.headers, request.path_params["method"], await request.json()
                )
                return res if isinstance(res, Response) else JSONResponse(content=res)
        return Response(status_code=401)

    async def launch(self, manager: Launart):
        for adapter in self.adapters:
            manager.add_component(adapter)

        async with self.stage("preparing"):
            asgi_service = manager.get_component(UvicornASGIService)
            app = Starlette(
                routes=[
                    self.ws_route,
                    *(
                        Route(f"/v1/{method}", handler, methods=["POST"])
                        for method, handler in self.handlers.items()
                    ),
                    Route("/v1/{method:path}", self.http_server_handler, methods=["POST"]),
                ]
            )
            asgi_service.middleware.mounts[""] = app  # type: ignore

        async with self.stage("blocking"):
            await any_completed(
                manager.status.wait_for_sigexit(),
                *(adapter.status.wait_for("blocking-completed") for adapter in self.adapters),
            )

        async with self.stage("cleanup"):
            with suppress(KeyError):
                del asgi_service.middleware.mounts[""]

    def run(
        self,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        manager = it(Launart)
        manager.add_component(self)
        manager.launch_blocking(loop=loop, stop_signal=stop_signal)
