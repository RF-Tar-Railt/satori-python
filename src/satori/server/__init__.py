from __future__ import annotations

import asyncio
import functools
import mimetypes
import secrets
import signal
import threading
import urllib.parse
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import print_exc
from typing import Any, cast

import aiohttp
from creart import it
from graia.amnesia.builtins.asgi import UvicornASGIService
from launart import Launart, Service, any_completed
from loguru import logger
from starlette.applications import Starlette
from starlette.datastructures import FormData as FormData
from starlette.requests import Request as StarletteRequest
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect
from yarl import URL

from satori.config import WebhookInfo
from satori.const import Api
from satori.model import Event, ModelBase, Opcode

from .adapter import Adapter as Adapter
from .conection import WebsocketConnection
from .formdata import parse_content_disposition as parse_content_disposition
from .model import Provider as Provider
from .model import Request as Request
from .model import Router as Router
from .route import RouteCall as RouteCall
from .route import RouterMixin as RouterMixin
from .utils import Deque


async def _request_handler(method: str, request: StarletteRequest, func: RouteCall):
    if method == Api.UPLOAD_CREATE.value:
        async with request.form() as form:
            res = await func(
                Request(
                    cast(dict, request.headers.mutablecopy()),
                    method,
                    form,
                )
            )
            return JSONResponse(content=res)
    res = await func(
        Request(
            cast(dict, request.headers.mutablecopy()),
            method,
            await request.json(),
        )
    )
    if isinstance(res, ModelBase):
        return JSONResponse(content=res.dump())
    if res and isinstance(res, list) and isinstance(res[0], ModelBase):
        return JSONResponse(content=[_.dump() for _ in res])  # type: ignore
    return res if isinstance(res, Response) else JSONResponse(content=res)


class Server(Service, RouterMixin):
    id = "satori-python.server"
    required: set[str] = {"asgi.service/uvicorn"}
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    version: str
    providers: list[Provider]
    routers: list[Router]
    _adapters: list[Adapter]
    connections: list[WebsocketConnection]
    session: aiohttp.ClientSession

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5140,
        path: str = "",
        version: str = "v1",
        webhooks: list[WebhookInfo] | None = None,
        stream_threshold: int = 16 * 1024 * 1024,
        stream_chunk_size: int = 64 * 1024,
    ):
        self.connections = []
        manager = it(Launart)
        manager.add_component(UvicornASGIService(host, port))
        self.version = version
        self.path = path
        if self.path and not self.path.startswith("/"):
            self.path = f"/{self.path}"
        self.url_base = f"http://{host}:{port}{self.path}/{version}"
        self._adapters = []
        self.providers = []
        self.routers = []
        self.routes = {}
        self.webhooks = webhooks or []
        self._tempdir = TemporaryDirectory()
        self._sequence = 0
        self._event_cache = Deque(maxlen=100)
        self.stream_threshold = stream_threshold
        self.stream_chunk_size = stream_chunk_size
        self.resources: dict[str, Path] = {}
        super().__init__()

    def apply(self, item: Provider | Router | Adapter):
        if isinstance(item, Adapter):
            item.ensure_server(self)
            self._adapters.append(item)
            self.providers.append(item)
        elif isinstance(item, Provider):
            self.providers.append(item)
        elif isinstance(item, Router):
            self.routers.append(item)
        else:
            raise TypeError(f"Unknown config type: {item}")

    def mount(self, route_path: str, file: Path):
        """在指定路径挂载静态文件"""
        self.resources[route_path] = file

    async def event_callback(self, event: Event):
        event.id = self._sequence
        self._event_cache.append(event)
        self._sequence += 1
        for connection in self.connections:
            try:
                await connection.send({"op": Opcode.EVENT, "body": event.dump()})
            except WebSocketDisconnect:
                break
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
                        "X-Platform": event.platform_,
                        "Satori-Platform": event.platform_,
                        "X-Self-ID": event.self_id_,
                        "Satori-Login-ID": event.self_id_,
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
        body = identity["body"]
        token = identity["body"].get("token")
        logins = []
        for provider in self.providers:
            if not provider.authenticate(token):
                return await ws.close(code=3000, reason="Unauthorized")
            _logins = await provider.get_logins()
            for _login in _logins:
                _login.proxy_urls.extend(provider.proxy_urls())
            logins.extend(_logins)
        sequence = body.get("sequence")
        if sequence is None:
            sequence = -1
        await connection.send({"op": Opcode.READY, "body": {"logins": [lo.dump() for lo in logins]}})
        self.connections.append(connection)
        logger.debug(f"New connection: {id(connection)}")
        heartbeat_task = asyncio.create_task(connection.heartbeat())
        close_task = asyncio.create_task(connection.close_signal.wait())
        try:
            if sequence > -1:
                for event in self._event_cache.after(sequence):
                    await connection.send({"op": Opcode.EVENT, "body": event.dump()})
                    await asyncio.sleep(0.1)
            await any_completed(heartbeat_task, close_task)
        finally:
            await connection.connection_closed()
            logger.debug(f"Connection closed: {id(connection)}")
            heartbeat_task.cancel()
            close_task.cancel()
            self.connections.remove(connection)

    async def admin_login_list_handler(self, request: StarletteRequest):
        logins = []
        for provider in self.providers:
            _logins = await provider.get_logins()
            for _login in _logins:
                _login.proxy_urls.extend(provider.proxy_urls())
            logins.extend(_logins)
        return JSONResponse(content=[lo.dump() for lo in logins])

    async def http_server_handler(self, request: StarletteRequest):
        if not self._adapters and not self.routes:
            return Response(status_code=404, content=request.path_params["method"])
        method = request.path_params["method"]
        if "X-Platform" not in request.headers and "Satori-Platform" not in request.headers:
            return Response(status_code=401, content="Missing header X-Platform or Satori-Platform")
        platform: str = request.headers.get("X-Platform") or request.headers.get("Satori-Platform")  # type: ignore
        if "X-Self-ID" not in request.headers and "Satori-Login-ID" not in request.headers:
            return Response(status_code=401, content="Missing header X-Self-ID or Satori-Login-ID")
        self_id: str = request.headers.get("X-Self-ID") or request.headers.get("Satori-Login-ID")  # type: ignore

        for _router in self._adapters:
            if method not in _router.routes:
                continue
            if not _router.ensure(platform, self_id):
                continue
            return await _request_handler(method, request, _router.routes[method])
        if method in self.routes:
            return await _request_handler(method, request, self.routes[method])
        for _router in self.routers:
            if method not in _router.routes:
                continue
            return await _request_handler(method, request, _router.routes[method])
        return Response(status_code=404, content=method)

    async def proxy_url_handler(self, request: StarletteRequest):
        url = request.path_params["upload_url"]
        try:
            content = await self.download(url)
            if isinstance(content, Path):
                return FileResponse(path=content)
            # if content size > stream_limit, use streaming response
            if len(content) > self.stream_threshold:

                async def iter_content(body: bytes):
                    for i in range(0, len(body), self.stream_chunk_size):
                        yield body[i : i + self.stream_chunk_size]

                return StreamingResponse(content=iter_content(content))
            return Response(content=content)
        except FileNotFoundError as e404:
            return Response(status_code=404, content=str(e404))
        except ValueError as e403:
            return Response(status_code=403, content=str(e403))
        except TypeError as e400:
            return Response(status_code=400, content=str(e400))
        except Exception as e:
            logger.error(repr(e))
            return Response(status_code=500, content=repr(e))

    async def download(self, url: str):
        url = url.replace(":/", "://", 1).replace(":///", "://", 1)
        pr = urllib.parse.urlparse(url)
        if pr.scheme == "upload":
            if pr.netloc == "temp":
                _, inst, filename = pr.path.split("/", 2)
                if inst == f"{self.id}:{id(self)}":
                    file = Path(self._tempdir.name) / filename
                    if file.exists():
                        return file
                raise FileNotFoundError(f"{filename} not found")
        for provider in self.providers:
            if pr.scheme == "upload":
                platform = pr.netloc
                _, self_id, path = pr.path.split("/", 2)
                if provider.ensure(platform, self_id):
                    return await provider.download_uploaded(platform, self_id, path)

            for proxy_url_pf in provider.proxy_urls():
                if not url.startswith(proxy_url_pf):
                    continue
                resp = await provider.download_proxied(proxy_url_pf, url)
                if resp is None:
                    continue
                return resp
        raise ValueError(f"Unknown proxy url: {url}")

    def get_local_file(self, url: str):
        url = url.split("/")[-1]
        file = Path(self._tempdir.name) / url
        if file.exists():
            return file.read_bytes()

    async def _default_upload_create_handler(self, request: Request[FormData]):
        res = {}
        root = Path(self._tempdir.name)
        for _, data in request.params.items():
            if isinstance(data, str):
                continue
            ext = data.headers["content-type"]
            disp = parse_content_disposition(data.headers["content-disposition"])
            fid = secrets.token_urlsafe(16)
            if "filename" in disp:
                filename = f"{fid}-{disp['filename']}"
            else:
                filename = f"{fid}-{disp['name']}{mimetypes.guess_extension(ext) or '.png'}"
            file = root / filename
            with file.resolve().open("wb+") as f:
                f.write(await data.read())

            res[disp["name"]] = f"upload://temp/{self.id}:{id(self)}/{filename}"

            loop = asyncio.get_running_loop()
            loop.call_later(600, file.unlink, True)
        return res

    async def launch(self, manager: Launart):
        self.session = aiohttp.ClientSession()
        for _adapter in self._adapters:
            manager.add_component(_adapter)

        if Api.UPLOAD_CREATE.value not in self.routes and not self._adapters:
            self.routes[Api.UPLOAD_CREATE.value] = self._default_upload_create_handler

        async with self.stage("preparing"):
            asgi_service = manager.get_component(UvicornASGIService)
            app = Starlette(
                routes=[
                    WebSocketRoute(f"{self.path}/{self.version}/events", self.websocket_server_handler),
                    Route(
                        f"{self.path}/{self.version}/admin/login.list",
                        self.admin_login_list_handler,
                        methods=["POST"],
                    ),
                    Route(
                        f"{self.path}/{self.version}/proxy/{{upload_url:path}}",
                        self.proxy_url_handler,
                        methods=["GET"],
                    ),
                    Route(
                        f"{self.path}/{self.version}/{{method:path}}",
                        self.http_server_handler,
                        methods=["POST"],
                    ),
                ]
            )
            for path, file in self.resources.items():
                app.mount(path, StaticFiles(directory=file.parent, html=file.suffix == ".html"))
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
            self._tempdir.cleanup()

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

    async def run_async(
        self,
        manager: Launart | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        if manager is None:
            manager = it(Launart)
        manager.add_component(self)
        handled_signals: dict[signal.Signals, Any] = {}
        launch_task = asyncio.create_task(manager.launch(), name="amnesia-launch")
        signal_handler = functools.partial(manager._on_sys_signal, main_task=launch_task)
        if threading.current_thread() is threading.main_thread():  # pragma: worst case
            try:
                for sig in stop_signal:
                    handled_signals[sig] = signal.getsignal(sig)
                    signal.signal(sig, signal_handler)
            except ValueError:  # pragma: no cover
                # `signal.signal` may throw if `threading.main_thread` does
                # not support signals
                handled_signals.clear()
        await launch_task
        for sig, handler in handled_signals.items():
            if signal.getsignal(sig) is signal_handler:
                signal.signal(sig, handler)
