from __future__ import annotations

import asyncio

from aiohttp import web
from launart import Service
from launart.manager import Launart
from launart.utilles import any_completed
from loguru import logger

from satori.account import Account
from satori.config import WebhookInfo
from satori.model import Event, LoginStatus, Opcode

from .base import BaseNetwork


class WebhookNetwork(BaseNetwork[WebhookInfo], Service):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}
    wsgi: web.Application | None = None

    @property
    def id(self):
        return f"satori/network/webhook/{self.config.identity}#{id(self)}"

    async def handle_request(self, req: web.Request):
        header = req.headers
        auth = header["Authorization"]
        if not auth.startswith("Bearer"):
            return web.Response(status=401)
        token = auth.split(" ", 1)[1]
        if self.config.token and self.config.token != token:
            return web.Response(status=401)
        platform = header["X-Platform"]
        self_id = header["X-Self-ID"]
        identity = f"{platform}/{self_id}"
        if identity in self.app.accounts:
            account = self.app.accounts[identity]
            self.accounts[identity] = account
            account.connected.set()
            account.config = self.config
        else:
            account = Account(platform, self_id, self.config)
            logger.info(f"account registered: {account}")
            account.connected.set()
            self.app.accounts[identity] = account
            self.accounts[identity] = account
            await self.app.account_update(account, LoginStatus.ONLINE)
        data = await req.json()
        op = data["op"]
        if op != Opcode.EVENT:
            return web.Response(status=202)
        body = data["body"]

        async def event_parse_task(raw: dict):
            try:
                event = Event.parse(raw)
            except Exception as e:
                logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")
            else:
                self.sequence = event.id
                await self.app.post(event)

        asyncio.create_task(event_parse_task(body))
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
                        v.connected.clear()
                        del self.accounts[v.identity]
                return
            if close_task in done:
                await site.stop()
                logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")
                for k in self.accounts.keys():
                    logger.debug(f"Unregistering satori account {k}...")
                    account = self.app.accounts[k]
                    account.connected.clear()
                    await self.app.account_update(account, LoginStatus.DISCONNECT)
                self.accounts.clear()
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")
                continue

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            logger.info(f"starting server on {self.config.port}:{self.config.host}")
            self.wsgi = web.Application(logger=logger)
            self.wsgi.router.freeze = lambda: None  # monkey patch
            self.wsgi.router.add_post(self.config.path, self.handle_request)
            runner = web.AppRunner(self.wsgi)
            await runner.setup()
            site = web.TCPSite(runner, self.config.host, self.config.port)

        async with self.stage("blocking"):
            await self.daemon(manager, site)

        async with self.stage("cleanup"):
            await site.stop()
            await self.wsgi.shutdown()
            await self.wsgi.cleanup()
