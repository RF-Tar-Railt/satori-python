from __future__ import annotations

import asyncio

import aiohttp
from launart import Launart, any_completed
from loguru import logger

from satori.reconnect import RECONNECT_STABLE_SECONDS, ReconnectPolicy, is_normal_close, is_server_shutdown
from satori.utils import decode

from .base import MilkyBaseAdapter, MilkyBaseConfig


class MilkyWebsocketAdapter(MilkyBaseAdapter):

    connection: aiohttp.ClientWebSocketResponse | None

    def __init__(
        self,
        config: MilkyBaseConfig,
    ):
        super().__init__(config)
        base_path = self.base_url.path.rstrip("/")
        ws_scheme = "wss" if self.base_url.scheme == "https" else "ws"
        self.event_url = self.base_url.with_scheme(ws_scheme).with_path(f"{base_path}/event")
        if config.token_in_query and self.token:
            self.event_url = self.event_url.update_query(access_token=self.token)
        self.connection = None
        self.close_signal = asyncio.Event()

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.connection_daemon(manager, self.session)

        async with self.stage("cleanup"):
            if self.connection and not self.connection.closed:
                await self.connection.close()
            if self.session:
                await self.session.close()
            self.connection = None
            self.session = None
            await self._handle_disconnect()

    async def connection_daemon(self, manager: Launart, session: aiohttp.ClientSession):
        policy = ReconnectPolicy()
        while not manager.status.exiting:
            await self._mark_reconnecting()
            headers = self.headers.copy()
            if self.token:
                headers.setdefault("Authorization", f"Bearer {self.token}")
            try:
                self.connection = await session.ws_connect(self.event_url, headers=headers)
            except Exception as e:
                logger.error(f"Milky adapter websocket connect failed: {e}")
                if not await policy.sleep():
                    logger.error("Milky adapter reconnect attempts exhausted, marking logins offline")
                    await self._mark_offline()
                    return
                continue
            logger.info("Milky adapter websocket connected")
            connected_at = asyncio.get_running_loop().time()
            self.close_signal.clear()
            await self.refresh_login()
            receiver_task = asyncio.create_task(self.message_handle())
            close_task = asyncio.create_task(self.close_signal.wait())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())

            done, pending = await any_completed(receiver_task, close_task, sigexit_task)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if sigexit_task in done:
                break
            code = self.connection.close_code if self.connection else None
            if is_normal_close(code):
                logger.info(f"Milky adapter websocket closed by server (code={code}), login removed")
                await self._handle_disconnect()
                if not is_server_shutdown(code):
                    return
            if asyncio.get_running_loop().time() - connected_at >= RECONNECT_STABLE_SECONDS:
                policy.reset()
            logger.warning("Milky adapter websocket closed, reconnecting")
            if self.connection and not self.connection.closed:
                await self.connection.close()
            self.close_signal.set()
            await self._mark_reconnecting()
            if not await policy.sleep():
                logger.error("Milky adapter reconnect attempts exhausted, marking logins offline")
                await self._mark_offline()
                return
        await self._handle_disconnect()

    async def message_handle(self):
        assert self.connection is not None
        async for msg in self.connection:
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                self.close_signal.set()
                break
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                data = decode(msg.data)
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"Failed to decode milky event: {e}")
                continue
            if not isinstance(data, dict):
                continue
            await self.handle_event(data)

    async def _handle_disconnect(self):
        await super()._handle_disconnect()
        if self.connection and not self.connection.closed:
            await self.connection.close()
        self.close_signal.set()


__all__ = ["MilkyWebsocketAdapter"]
