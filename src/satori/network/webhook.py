from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web
from launart import Service
from launart.manager import Launart
from launart.utilles import any_completed
from loguru import logger

from satori.config import WebhookInfo
from satori.model import Event, Opcode

from .base import BaseNetwork


class WebhookNetwork(BaseNetwork[WebhookInfo], Service):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}
    wsgi: web.Application | None = None

    @property
    def id(self):
        return f"satori/network/webhook#{self.config.identity}"

    async def handle_request(self, req: web.Request):
        # req: HttpRequest = await io.extra(HttpRequest)
        # if req.headers.get("qq") != str(self.info.account):
        #     return
        # for k, v in self.info.headers.items():
        #     if req.headers.get(k) != v:
        #         return "Authorization failed", {"status": 401}
        # data = Json.deserialize((await io.read()).decode("utf-8"))
        # assert isinstance(data, dict)
        data = await req.json()
        op = data["op"]
        if op == Opcode.EVENT:
            body = data["body"]

            async def event_parse_task(raw: dict):
                try:
                    event = Event.parse(raw)
                    await self.app.post(event)
                except Exception as e:
                    logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")

            asyncio.create_task(event_parse_task(body))
            return web.Response()
        logger.debug(f"Received payload: {data}")
        self.status.connected = True
        self.status.alive = True
        return web.Response()

    @property
    def alive(self):
        return self.wsgi is not None

    async def wait_for_available(self):
        await self.status.wait_for_available()

    async def daemon(self, manager: Launart, site: web.TCPSite):
        while not manager.status.exiting:
            await site.start()
            self.close_signal.clear()
            close_task = asyncio.create_task(self.close_signal.wait())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            done, pending = await any_completed(
                sigexit_task,
                close_task,
            )
            if sigexit_task in done:
                logger.info(f"{self} Webhook server exiting...")
                self.close_signal.set()
                for v in list(self.app.accounts.values()):
                    if v.identity in self.accounts:
                        del self.accounts[v.identity]
                return
            if close_task in done:
                await site.stop()
                logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")
                accounts = {str(i) for i in self.accounts.keys()}
                for n in list(self.app.accounts.keys()):
                    logger.debug(f"Unregistering satori account {n}...")
                    account = self.app.accounts[n]
                    account.connected.clear()
                    if n in accounts:
                        del self.app.accounts[n]
                self.accounts.clear()
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")
                continue

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            logger.info(f"starting server on {self.config.self_host}:{self.config.self_port}")
            self.session = aiohttp.ClientSession()
            self.wsgi = web.Application(logger=logger)
            self.wsgi.router.freeze = lambda: None  # monkey patch
            self.wsgi.router.add_post("/v1/events", self.handle_request)
            runner = web.AppRunner(self.wsgi)
            await runner.setup()
            site = web.TCPSite(runner, self.config.self_host, self.config.self_port)

        async with self.stage("blocking"):
            await self.daemon(manager, site)

        async with self.stage("cleanup"):
            await site.stop()
            await self.wsgi.shutdown()
            await self.wsgi.cleanup()
            await self.session.close()
