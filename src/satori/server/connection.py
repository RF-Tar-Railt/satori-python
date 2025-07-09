from __future__ import annotations

import asyncio

from loguru import logger
from starlette.websockets import WebSocket, WebSocketDisconnect

from satori.model import Opcode


class WebsocketConnection:
    connection: WebSocket

    def __init__(self, connection: WebSocket):
        self.connection = connection
        self.close_signal: asyncio.Event = asyncio.Event()

    @property
    def alive(self) -> bool:
        return not self.close_signal.is_set()

    async def heartbeat(self):
        while True:
            try:
                msg = await asyncio.wait_for(self.connection.receive_json(), timeout=12)
                if not isinstance(msg, dict) or msg.get("op") != Opcode.PING:
                    continue
                await self.connection.send_json({"op": Opcode.PONG})
            except asyncio.TimeoutError:
                logger.warning(f"Connection {id(self)} heartbeat timeout, closing connection.")
                await self.connection.close()
                await self.connection_closed()
                break
            except WebSocketDisconnect:
                return

    async def connection_closed(self):
        self.close_signal.set()

    async def wait_for_available(self):
        return

    async def send(self, payload: dict) -> None:
        return await self.connection.send_json(payload)
