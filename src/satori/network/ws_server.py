from __future__ import annotations

import asyncio

from starlette.websockets import WebSocket

from satori.model import Opcode


class WsServerConnection:
    connection: WebSocket

    def __init__(self, connection: WebSocket):
        self.connection = connection
        self.close_signal: asyncio.Event = asyncio.Event()

    @property
    def id(self):
        return self.connection.headers["X-Self-ID"]

    @property
    def alive(self) -> bool:
        return not self.close_signal.is_set()

    async def heartbeat(self):
        async for msg in self.connection.iter_json():
            if not isinstance(msg, dict) or msg.get("op") != Opcode.PING:
                continue
            await self.connection.send_json({"op": Opcode.PONG})
        else:
            await self.connection_closed()

    async def connection_closed(self):
        self.close_signal.set()

    async def wait_for_available(self):
        return

    async def send(self, payload: dict) -> None:
        return await self.connection.send_json(payload)
