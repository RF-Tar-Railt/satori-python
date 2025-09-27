from __future__ import annotations

import asyncio
from datetime import datetime

from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from yarl import URL

from satori import Event, EventType, LoginStatus
from satori.exception import ActionFailed
from satori.model import Login, User
from satori.server import Request
from satori.server.adapter import Adapter as BaseAdapter
from satori.utils import decode, encode

from .api import apply
from .events.base import events
from .utils import USER_AVATAR_URL, milky_event_type


class _Connection:
    def __init__(self, adapter: MilkyReverseAdapter, ws: WebSocket):
        self.adapter = adapter
        self.ws = ws
        self.close_signal = asyncio.Event()
        self.response_waiters: dict[str, asyncio.Future] = {}

    async def message_receive(self):
        async for msg in self.ws.iter_text():
            yield self, decode(msg)
        else:
            self.close_signal.set()

    async def message_handle(self):
        async for connection, data in self.message_receive():
            if echo := data.get("echo"):
                if future := self.response_waiters.get(echo):
                    future.set_result(data)
                continue

            async def event_parse_task(data: dict):
                event_type = milky_event_type(data)
                
                # Handle connection/lifecycle events
                if event_type.startswith("meta.connect"):
                    self_id = str(data.get("self_id", ""))
                    if self_id and self_id not in self.adapter.logins:
                        # Get login info
                        self_info = await connection.call_api("get_login_info")
                        login = Login(
                            0,
                            LoginStatus.ONLINE,
                            "milky",
                            platform="milky",
                            user=User(
                                self_id,
                                (self_info or {}).get("nickname", ""),
                                avatar=USER_AVATAR_URL.format(uin=self_id),
                            ),
                            features=["guild.plain"],
                        )
                        self.adapter.logins[self_id] = login
                        await self.adapter.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                
                elif event_type.startswith("meta.heartbeat"):
                    self_id = str(data.get("self_id", ""))
                    if self_id and self_id not in self.adapter.logins:
                        self_info = await connection.call_api("get_login_info")
                        login = Login(
                            0,
                            LoginStatus.ONLINE,
                            "milky",
                            platform="milky",
                            user=User(
                                self_id,
                                (self_info or {}).get("nickname", ""),
                                avatar=USER_AVATAR_URL.format(uin=self_id),
                            ),
                            features=["guild.plain"],
                        )
                        self.adapter.logins[self_id] = login
                        await self.adapter.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                    logger.trace(f"received heartbeat from {self_id}")
                
                else:
                    self_id = str(data.get("self_id", ""))
                    if self_id not in self.adapter.logins:
                        logger.warning(f"received event from unknown self_id: {data}")
                        return
                    
                    login = self.adapter.logins[self_id]
                    if event_handler := events.get(event_type):
                        event = await event_handler(login, connection, data)
                        if event:
                            await self.adapter.server.post(event)

            asyncio.create_task(event_parse_task(data))

    async def call_api(self, action: str, params: dict | None = None) -> dict | None:
        echo = str(id(params)) if params else str(asyncio.get_event_loop().time())
        
        request_data = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }
        
        future = asyncio.Future()
        self.response_waiters[echo] = future
        
        try:
            await self.ws.send_text(encode(request_data))
            response = await asyncio.wait_for(future, timeout=30.0)
            
            if response.get("status") == "failed":
                raise ActionFailed(response.get("msg", "Unknown error"))
            
            return response.get("data")
        
        except asyncio.TimeoutError:
            raise ActionFailed(f"API call {action} timed out")
        finally:
            self.response_waiters.pop(echo, None)


class MilkyReverseAdapter(BaseAdapter):
    """Milky reverse (webhook/websocket) adapter."""

    def __init__(self, path: str = "/milky"):
        super().__init__()
        self.path = path
        self.connections: dict[str, _Connection] = {}
        self.logins: dict[str, Login] = {}

        apply(self, lambda self_id: self.connections.get(self_id), lambda self_id: self.logins.get(self_id))

    def ensure(self, platform: str, self_id: str) -> bool:
        return platform == "milky" and self_id in self.logins

    async def get_logins(self) -> list[Login]:
        logins = list(self.logins.values())
        for index, login in enumerate(logins):
            login.sn = index
        return logins

    @property
    def required(self) -> set[str]:
        return {"satori-python.server"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    def get_platform(self) -> str:
        return "milky"

    async def handle_internal(self, request: Request, path: str) -> Response:
        return Response("Not implemented", status_code=404)

    def get_routes(self):
        async def milky_ws_handler(websocket: WebSocket):
            await websocket.accept()
            connection = _Connection(self, websocket)
            
            # Store connection temporarily
            connection_id = str(id(connection))
            self.connections[connection_id] = connection
            
            try:
                await connection.message_handle()
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
            finally:
                self.connections.pop(connection_id, None)

        return [WebSocketRoute(self.path, milky_ws_handler)]

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            pass

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            for connection in list(self.connections.values()):
                if not connection.ws.client_state.disconnected:
                    await connection.ws.close()


# Alias for easier import
Adapter = MilkyReverseAdapter