from __future__ import annotations

import asyncio

import aiohttp
from launart import Launart, any_completed
from loguru import logger
from yarl import URL

from satori.utils import decode

from .base import MilkyBaseAdapter


class MilkySSEAdapter(MilkyBaseAdapter):

    def __init__(
        self,
        endpoint: str | URL,
        *,
        token: str | None = None,
        token_in_query: bool = False,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(endpoint, token=token, headers=headers)
        base_path = self.base_url.path.rstrip("/")
        self.event_url = self.base_url.with_path(f"{base_path}/event")
        if token_in_query and token:
            self.event_url = self.event_url.update_query(access_token=token)
        self.close_signal = asyncio.Event()

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.connection_daemon(manager, self.session)

        async with self.stage("cleanup"):
            if self.session:
                await self.session.close()
            self.session = None
            await self._handle_disconnect()

    async def connection_daemon(self, manager: Launart, session: aiohttp.ClientSession):
        while not manager.status.exiting:
            headers = self.headers.copy()
            headers["Accept"] = "text/event-stream"
            headers["Cache-Control"] = "no-cache"
            headers["Upgrade"] = "none"
            if self.token:
                headers.setdefault("Authorization", f"Bearer {self.token}")
            try:
                async with session.get(self.event_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Milky SSE adapter connect failed with status {response.status}")
                        await asyncio.sleep(5)
                        continue
                    logger.info("Milky SSE adapter connected")
                    self.close_signal.clear()
                    await self.refresh_login()

                    receiver_task = asyncio.create_task(self._read_sse_stream(response))
                    close_task = asyncio.create_task(self.close_signal.wait())
                    sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())

                    done, pending = await any_completed(receiver_task, close_task, sigexit_task)
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    if sigexit_task in done:
                        break
            except aiohttp.ClientError as e:
                logger.error(f"Milky SSE adapter connection error: {e}")
            except Exception as e:
                logger.error(f"Milky SSE adapter unexpected error: {e}")

            logger.warning("Milky SSE adapter connection closed, retrying in 5 seconds")
            await self._handle_disconnect()
            await asyncio.sleep(5)
        await self._handle_disconnect()

    async def _read_sse_stream(self, response: aiohttp.ClientResponse):
        """Read and parse SSE stream without external dependencies."""
        event_type: str | None = None
        data_buffer: list[str] = []

        async for line_bytes in response.content:
            line = line_bytes.decode("utf-8").rstrip("\r\n")

            if not line:
                # Empty line indicates end of event
                if data_buffer:
                    data_str = "\n".join(data_buffer)
                    await self._dispatch_sse_event(event_type, data_str)
                event_type = None
                data_buffer = []
                continue

            if line.startswith(":"):
                # Comment line, ignore
                continue

            if ":" in line:
                field, _, value = line.partition(":")
                # Remove leading space from value if present
                if value.startswith(" "):
                    value = value[1:]
            else:
                field = line
                value = ""

            if field == "event":
                event_type = value
            elif field == "data":
                data_buffer.append(value)
            elif field == "id":
                # Event ID, could be used for reconnection
                pass
            elif field == "retry":
                # Retry interval, could be implemented if needed
                pass

    async def _dispatch_sse_event(self, event_type: str | None, data: str):
        """Dispatch a parsed SSE event."""
        if not data or event_type != "milky_event":
            return
        try:
            payload = decode(data)
        except Exception as e:
            logger.error(f"Failed to decode SSE event data: {e}")
            return
        if not isinstance(payload, dict):
            return
        await self.handle_event(payload)

    async def _handle_disconnect(self):
        await super()._handle_disconnect()
        self.close_signal.set()


__all__ = ["MilkySSEAdapter"]
