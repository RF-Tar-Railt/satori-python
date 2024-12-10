from __future__ import annotations

import asyncio

from aiohttp import web
from launart.manager import Launart
from loguru import logger

from satori.model import Event, LoginStatus, MetaPayload, Opcode

from ..account import Account
from ..config import WebhookInfo as WebhookInfo
from .base import BaseNetwork


class WebhookNetwork(BaseNetwork[WebhookInfo]):
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
        op_code = int(header.get("Satori-OpCode", "0"))
        body = await req.json()
        if op_code == Opcode.META:
            payload = MetaPayload.parse(body)
            self.proxy_urls = payload.proxy_urls
            return web.Response()
        if op_code != Opcode.EVENT:
            return web.Response(status=202)
        # if "X-Platform" in header and "X-Self-ID" in header:
        #     platform = header["X-Platform"]
        #     self_id = header["X-Self-ID"]
        # elif "Satori-Platform" in header and "Satori-Login-ID" in header:
        #     platform = header["Satori-Platform"]
        #     self_id = header["Satori-Login-ID"]
        # else:
        #     return web.Response(status=400)
        try:
            event = Event.parse(body)
        except Exception as e:
            if (
                "self_id" in body
                or ("login" in body and "self_id" in body["login"])
                or ("login" in body and "user" in body["login"] and "self_id" in body["login"]["user"])
            ):
                logger.warning(f"Failed to parse event: {body}\nCaused by {e!r}")
            else:
                logger.trace(f"Failed to parse event: {body}\nCaused by {e!r}")
            return web.Response(status=500, reason=f"Failed to parse event caused by {e!r}")
        else:
            logger.trace(f"Received event: {event}")
            self.sequence = event.sn
        login_sn = f"{event.login.sn}@{id(self)}"
        if login_sn in self.app.accounts:
            account = self.app.accounts[login_sn]
            account.connected.set()
            account.config = self.config
        else:
            account = Account(event.login, self.config, self.proxy_urls)
            logger.info(f"account registered: {account}")
            account.connected.set()
            self.app.accounts[login_sn] = account
            self.accounts[login_sn] = account
            await self.app.account_update(account, LoginStatus.ONLINE)
        asyncio.create_task(self.app.post(event, self))
        return web.Response()

    @property
    def alive(self):
        return self.wsgi is not None

    async def wait_for_available(self):
        await self.status.wait_for_available()

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            logger.info(f"starting server on {self.config.identity}")
            self.wsgi = web.Application(logger=logger)  # type: ignore
            self.wsgi.router.freeze = lambda: None  # monkey patch
            self.wsgi.router.add_post(self.config.path, self.handle_request)
            runner = web.AppRunner(self.wsgi)
            await runner.setup()
            site = web.TCPSite(runner, self.config.host, self.config.port)

        async with self.stage("blocking"):
            await site.start()
            await manager.status.wait_for_sigexit()
            logger.info(f"{self.id} Webhook server exiting...")
            self.close_signal.set()
            for v in list(self.app.accounts.values()):
                if (identity := f"{v.sn}@{id(self)}") in self.accounts:
                    v.connected.clear()
                    await self.app.account_update(v, LoginStatus.OFFLINE)
                    del self.app.accounts[identity]
                    del self.accounts[identity]

        async with self.stage("cleanup"):
            await site.stop()
            await self.wsgi.shutdown()
            await self.wsgi.cleanup()
