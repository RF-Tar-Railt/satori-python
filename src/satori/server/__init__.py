from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from traceback import print_exc
from typing import Any, Awaitable, Callable, Iterable, cast, overload, Literal

import aiohttp
from creart import it
from graia.amnesia.builtins.asgi import UvicornASGIService
from launart import Launart, Service, any_completed
from loguru import logger
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from yarl import URL

from satori.config import WebhookInfo
from satori.const import Api
from satori.model import Event, Opcode, ModelBase

from . import route
from .adapter import Adapter as Adapter
from .conection import WebsocketConnection
from .model import Provider
from .model import Request as Request
from .model import Router


class Server(Service):
    id = "satori-python.server"
    required: set[str] = {"asgi.service/uvicorn"}
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    version: str
    providers: list[Provider]
    routers: list[Router]
    _adapters: list[Adapter]
    connections: list[WebsocketConnection]

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5140,
        path: str = "",
        version: str = "v1",
        webhooks: list[WebhookInfo] | None = None,
    ):
        self.connections = []
        manager = it(Launart)
        manager.add_component(UvicornASGIService(host, port))
        self.version = version
        self.path = path
        if self.path and not self.path.startswith("/"):
            self.path = f"/{self.path}"
        self._adapters = []
        self.providers = []
        self.routers = []
        self.routes = []
        self.webhooks = webhooks or []
        self.session = aiohttp.ClientSession()
        super().__init__()

    def apply(self, item: Provider | Router | Adapter):
        if isinstance(item, Adapter):
            self._adapters.append(item)
            self.routers.append(item)
            self.providers.append(item)
        elif isinstance(item, Provider):
            self.providers.append(item)
        elif isinstance(item, Router):
            self.routers.append(item)
        else:
            raise TypeError(f"Unknown config type: {item}")
        
    @overload
    def route(self, path: Literal[Api.MESSAGE_CREATE]) -> Callable[[route.MESSAGE_CREATE], route.MESSAGE_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_UPDATE]) -> Callable[[route.MESSAGE_UPDATE], route.MESSAGE_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_GET]) -> Callable[[route.MESSAGE_GET], route.MESSAGE_GET]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_DELETE]) -> Callable[[route.MESSAGE_DELETE], route.MESSAGE_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.MESSAGE_LIST]) -> Callable[[route.MESSAGE_LIST], route.MESSAGE_LIST]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_GET]) -> Callable[[route.CHANNEL_GET], route.CHANNEL_GET]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_LIST]) -> Callable[[route.CHANNEL_LIST], route.CHANNEL_LIST]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_CREATE]) -> Callable[[route.CHANNEL_CREATE], route.CHANNEL_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_UPDATE]) -> Callable[[route.CHANNEL_UPDATE], route.CHANNEL_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_DELETE]) -> Callable[[route.CHANNEL_DELETE], route.CHANNEL_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.CHANNEL_MUTE]) -> Callable[[route.CHANNEL_MUTE], route.CHANNEL_MUTE]: ...

    @overload
    def route(self, path: Literal[Api.USER_CHANNEL_CREATE]) -> Callable[[route.ROUTE_USER_CHANNEL_CREATE], route.ROUTE_USER_CHANNEL_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_GET]) -> Callable[[route.GUILD_GET], route.GUILD_GET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_LIST]) -> Callable[[route.GUILD_LIST], route.GUILD_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_APPROVE]) -> Callable[[route.APPROVE], route.APPROVE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_LIST]) -> Callable[[route.GUILD_MEMBER_LIST], route.GUILD_MEMBER_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_GET]) -> Callable[[route.GUILD_MEMBER_GET], route.GUILD_MEMBER_GET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_KICK]) -> Callable[[route.GUILD_MEMBER_KICK], route.GUILD_MEMBER_KICK]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_MUTE]) -> Callable[[route.GUILD_MEMBER_MUTE], route.GUILD_MEMBER_MUTE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_APPROVE]) -> Callable[[route.APPROVE], route.APPROVE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_ROLE_SET]) -> Callable[[route.GUILD_MEMBER_ROLE_SET], route.GUILD_MEMBER_ROLE_SET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_MEMBER_ROLE_UNSET]) -> Callable[[route.GUILD_MEMBER_ROLE_UNSET], route.GUILD_MEMBER_ROLE_UNSET]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_LIST]) -> Callable[[route.GUILD_ROLE_LIST], route.GUILD_ROLE_LIST]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_CREATE]) -> Callable[[route.GUILD_ROLE_CREATE], route.GUILD_ROLE_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_UPDATE]) -> Callable[[route.GUILD_ROLE_UPDATE], route.GUILD_ROLE_UPDATE]: ...

    @overload
    def route(self, path: Literal[Api.GUILD_ROLE_DELETE]) -> Callable[[route.GUILD_ROLE_DELETE], route.GUILD_ROLE_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_CREATE]) -> Callable[[route.REACTION_CREATE], route.REACTION_CREATE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_DELETE]) -> Callable[[route.REACTION_DELETE], route.REACTION_DELETE]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_CLEAR]) -> Callable[[route.REACTION_CLEAR], route.REACTION_CLEAR]: ...

    @overload
    def route(self, path: Literal[Api.REACTION_LIST]) -> Callable[[route.REACTION_LIST], route.REACTION_LIST]: ...

    @overload
    def route(self, path: Literal[Api.LOGIN_GET]) -> Callable[[route.LOGIN_GET], route.LOGIN_GET]: ...

    @overload
    def route(self, path: Literal[Api.USER_GET]) -> Callable[[route.USER_GET], route.USER_GET]: ...

    @overload
    def route(self, path: Literal[Api.FRIEND_LIST]) -> Callable[[route.FRIEND_LIST], route.FRIEND_LIST]: ...

    @overload
    def route(self, path: Literal[Api.FRIEND_APPROVE]) -> Callable[[route.APPROVE], route.APPROVE]: ...
    
    @overload
    def route(self, path: str) -> Callable[[route.INTERAL], route.INTERAL]:
        ...

    def route(self, path: str | Api) -> Callable[[route.Router], route.Router]:
        """注册一个路由

        Args:
            path (str | Api): 路由路径；若 path 不属于 Api，则会被认为是内部接口
        """

        def wrapper(func: route.INTERAL):
            async def handler(request: StarletteRequest):
                res = await func(
                    Request(
                        cast(dict, request.headers.mutablecopy()),
                        path if isinstance(path, str) else path.value,
                        await request.json(),
                    )
                )
                if isinstance(res, ModelBase):
                    return JSONResponse(content=res.dump())
                if res and isinstance(res, list) and isinstance(res[0], ModelBase):
                    return JSONResponse(content=[_.dump() for _ in res])  # type: ignore
                return res if isinstance(res, Response) else JSONResponse(content=res)

            if isinstance(path, Api):
                self.routes.append(
                    Route(f"{self.path}/{self.version}/{path.value}", handler, methods=["POST"])
                )
            else:
                self.routes.append(
                    Route(f"{self.path}/{self.version}/internal/{path}", handler, methods=["POST"])
                )
            return func

        return wrapper

    async def event_callback(self, event: Event):
        for connection in self.connections:
            try:
                await connection.send({"op": Opcode.EVENT, "body": event.dump()})
            except Exception as e:
                print_exc()
                logger.error(e)
        for hook in self.webhooks:
            try:
                async with self.session.post(
                    URL(f"http://{hook.identity}"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {hook.token or ''}",
                        "X-Platform": event.platform,
                        "X-Self-ID": event.self_id,
                    },
                    json={"op": Opcode.EVENT, "body": event.dump()},
                ) as resp:
                    resp.raise_for_status()
            except Exception as e:
                print_exc()
                logger.error(e)

    async def websocket_server_handler(self, ws: WebSocket):
        await ws.accept()
        connection = WebsocketConnection(ws)
        identity = await ws.receive_json()
        if not isinstance(identity, dict) or identity.get("op") != Opcode.IDENTIFY:
            return await ws.close(code=3000, reason="Unauthorized")
        token = identity["body"]["token"]
        logins = []
        for provider in self.providers:
            if not provider.authenticate(token):
                return await ws.close(code=3000, reason="Unauthorized")
            logins.extend(await provider.get_logins())
        await connection.send({"op": Opcode.READY, "body": {"logins": [lo.dump() for lo in logins]}})
        self.connections.append(connection)

        try:
            await any_completed(connection.heartbeat(), connection.close_signal.wait())
        finally:
            self.connections.remove(connection)

    async def http_server_handler(self, request: StarletteRequest):
        if not self.routers:
            return Response(status_code=404)
        for _router in self.routers:
            if _router.validate_headers(cast(dict, request.headers.mutablecopy())):
                method = request.path_params["method"]
                if method.startswith("internal/"):
                    res = await _router.call_internal_api(
                        Request(
                            cast(dict, request.headers.mutablecopy()),
                            method[len("internal/") :],
                            await request.json(),
                        )
                    )
                else:
                    res = await _router.call_api(
                        Request(
                            cast(dict, request.headers.mutablecopy()),
                            method,
                            await request.json(),
                        )
                    )
                return res if isinstance(res, Response) else JSONResponse(content=res)
        return Response(status_code=401)

    async def launch(self, manager: Launart):
        for _adapter in self._adapters:
            manager.add_component(_adapter)

        async with self.stage("preparing"):
            asgi_service = manager.get_component(UvicornASGIService)
            app = Starlette(
                routes=[
                    WebSocketRoute(f"{self.path}/{self.version}/events", self.websocket_server_handler),
                    *self.routes,
                    Route(
                        f"{self.path}/{self.version}/{{method:path}}",
                        self.http_server_handler,
                        methods=["POST"],
                    ),
                ]
            )
            asgi_service.middleware.mounts[""] = app  # type: ignore

        async def event_task(_provider: Provider):
            async for event in _provider.publisher():
                await self.event_callback(event)

        async with self.stage("blocking"):
            await any_completed(
                manager.status.wait_for_sigexit(),
                *(event_task(provider) for provider in self.providers),
                *(_adapter.status.wait_for("blocking-completed") for _adapter in self._adapters),
            )

        async with self.stage("cleanup"):
            with suppress(KeyError):
                del asgi_service.middleware.mounts[""]
            await self.session.close()

    def run(
        self,
        manager: Launart | None = None,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        if manager is None:
            manager = it(Launart)
        manager.add_component(self)
        manager.launch_blocking(loop=loop, stop_signal=stop_signal)

    async def run_async(self, manager: Launart | None = None):
        if manager is None:
            manager = it(Launart)
        manager.add_component(self)
        await manager.launch()