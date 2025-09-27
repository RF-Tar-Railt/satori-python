from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime
from typing import cast

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse
from launart import Launart, any_completed
from launart.status import Phase
from loguru import logger
from starlette.responses import JSONResponse, Response
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


class MilkyAdapter(BaseAdapter):
    """Milky protocol adapter for satori-python."""

    session: ClientSession
    connection: ClientWebSocketResponse | None

    def __init__(
        self,
        endpoint: str | URL,
        access_token: str | None = None,
    ):
        super().__init__()
        self.endpoint = URL(endpoint)
        self.access_token = access_token
        self.close_signal = asyncio.Event()
        self.response_waiters: dict[str, asyncio.Future] = {}
        self.logins: dict[str, Login] = {}

        apply(self, lambda _: self, lambda _: self.logins.get(_))

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

    async def message_receive(self):
        if not self.connection:
            return
        
        try:
            async for msg in self.connection:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = decode(msg.data)
                    yield data
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.connection.exception()}")
                    break
        except Exception as e:
            logger.error(f"Error in message_receive: {e}")
        finally:
            self.close_signal.set()

    async def message_handle(self):
        async for data in self.message_receive():
            if echo := data.get("echo"):
                if future := self.response_waiters.get(echo):
                    future.set_result(data)
                continue

            async def event_parse_task(data: dict):
                event_type = milky_event_type(data)
                
                # Handle connection events
                if event_type.startswith("meta.connect"):
                    self_id = str(data.get("self_id", ""))
                    if self_id and self_id not in self.logins:
                        # Get login info from milky protocol
                        self_info = await self.call_api("get_login_info")
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
                        self.logins[self_id] = login
                        await self.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                
                # Handle heartbeat
                elif event_type.startswith("meta.heartbeat"):
                    self_id = str(data.get("self_id", ""))
                    if self_id and self_id not in self.logins:
                        self_info = await self.call_api("get_login_info")
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
                        self.logins[self_id] = login
                        await self.server.post(Event(EventType.LOGIN_ADDED, datetime.now(), login))
                    logger.trace(f"received heartbeat from {self_id}")
                
                # Handle other events
                else:
                    self_id = str(data.get("self_id", ""))
                    if self_id not in self.logins:
                        logger.warning(f"received event from unknown self_id: {data}")
                        return
                    
                    login = self.logins[self_id]
                    if event_handler := events.get(event_type):
                        event = await event_handler(login, self, data)
                        if event:
                            await self.server.post(event)

            asyncio.create_task(event_parse_task(data))

    async def call_api(self, action: str, params: dict | None = None) -> dict | None:
        if not self.connection:
            raise ActionFailed("No connection available")
        
        # Generate unique echo ID
        echo = str(id(params)) if params else str(asyncio.get_event_loop().time())
        
        # Prepare request data
        request_data = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }
        
        # Create future for response
        future = asyncio.Future()
        self.response_waiters[echo] = future
        
        try:
            # Send request
            await self.connection.send_str(encode(request_data))
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=30.0)
            
            if response.get("status") == "failed":
                raise ActionFailed(response.get("msg", "Unknown error"))
            
            return response.get("data")
        
        except asyncio.TimeoutError:
            raise ActionFailed(f"API call {action} timed out")
        finally:
            self.response_waiters.pop(echo, None)

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = ClientSession()

        async with self.stage("blocking"):
            while not manager.status.exiting:
                try:
                    headers = {}
                    if self.access_token:
                        headers["Authorization"] = f"Bearer {self.access_token}"
                    
                    self.connection = await self.session.ws_connect(
                        str(self.endpoint), 
                        headers=headers,
                        heartbeat=30
                    )
                    
                    logger.info(f"Connected to milky server at {self.endpoint}")
                    
                    # Handle messages
                    await any_completed(
                        manager.status.wait_for_sigexit(),
                        self.message_handle(),
                        self.close_signal.wait(),
                    )
                    
                except Exception as e:
                    logger.error(f"Connection error: {e}")
                    await asyncio.sleep(5)  # Retry after 5 seconds
                finally:
                    if self.connection and not self.connection.closed:
                        await self.connection.close()
                    self.connection = None
                    self.close_signal.clear()

        async with self.stage("cleanup"):
            if self.connection and not self.connection.closed:
                await self.connection.close()
            if hasattr(self, "session"):
                await self.session.close()


# Alias for easier import
Adapter = MilkyAdapter