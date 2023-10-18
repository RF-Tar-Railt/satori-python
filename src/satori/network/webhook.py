from __future__ import annotations

import json
import asyncio
from contextlib import suppress
from typing import cast

import aiohttp
from aiohttp import web
from loguru import logger
from launart import Service
from launart.manager import Launart
from launart.utilles import any_completed

from satori.account import Account
from satori.model import Opcode, LoginStatus, Event
from satori.config import WebhookInfo
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
    #
    #
    # async def _authenticate(self):
    #     """鉴权连接"""
    #     if not self.connection:
    #         raise RuntimeError("connection is not established")
    #     payload = {
    #         "op": Opcode.IDENTIFY,
    #         "body": {
    #             "token": self.config.token,
    #         },
    #     }
    #     if self.sequence > -1:
    #         payload["body"]["sequence"] = self.sequence
    #     try:
    #         await self.send(payload)
    #     except Exception as e:
    #         logger.error(f"Error while sending IDENTIFY event: {e}")
    #         return False
    #
    #     resp = await self.connection.receive_json()
    #     if resp["op"] != Opcode.READY:
    #         logger.error(f"Received unexpected payload: {resp}")
    #         return False
    #     for login in resp["body"]["logins"]:
    #         if "self_id" not in login:
    #             continue
    #         platform = login.get("platform", "satori")
    #         self_id = login["self_id"]
    #         identity = f"{platform}/{self_id}"
    #         if identity in self.app.accounts:
    #             account = self.app.accounts[identity]
    #             if login["status"] == LoginStatus.ONLINE:
    #                 account.connected.set()
    #             else:
    #                 account.connected.clear()
    #             account.client = self
    #         else:
    #             account = Account(platform, self_id, self)
    #             logger.info(f"account registered: {account}")
    #             account.connected.set() if login[
    #                 "status"
    #             ] == LoginStatus.ONLINE else account.connected.clear()
    #             self.app.accounts[identity] = account
    #             self.accounts[identity] = account
    #
    #     if not self.accounts:
    #         logger.warning(f"No account available for {self.config}")
    #         return False
    #     return True
    #
    # async def _heartbeat(self):
    #     """心跳"""
    #     while True:
    #         if self.sequence:
    #             with suppress(Exception):
    #                 await self.send({"op": 1})
    #         await asyncio.sleep(9)
    #
    # async def daemon(self, manager: Launart, session: aiohttp.ClientSession):
    #     while not manager.status.exiting:
    #         async with session.ws_connect(
    #             self.config.ws_base / "events",
    #         ) as self.connection:
    #             logger.debug(f"{self.config.ws_base} Websocket client connected")
    #             self.close_signal.clear()
    #             result = await self._authenticate()
    #             if not result:
    #                 await asyncio.sleep(3)
    #                 continue
    #             self.close_signal.clear()
    #             close_task = asyncio.create_task(self.close_signal.wait())
    #             receiver_task = asyncio.create_task(self.message_handle())
    #             sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
    #             heartbeat_task = asyncio.create_task(self._heartbeat())
    #             done, pending = await any_completed(
    #                 sigexit_task,
    #                 close_task,
    #                 receiver_task,
    #                 heartbeat_task,
    #             )
    #             if sigexit_task in done:
    #                 logger.info(f"{self} Websocket client exiting...")
    #                 await self.connection.close()
    #                 self.close_signal.set()
    #                 self.connection = None
    #                 for v in list(self.app.accounts.values()):
    #                     if v.identity in self.accounts:
    #                         del self.accounts[v.identity]
    #                 return
    #             if close_task in done:
    #                 receiver_task.cancel()
    #                 logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")
    #                 accounts = {str(i) for i in self.accounts.keys()}
    #                 for n in list(self.app.accounts.keys()):
    #                     logger.debug(f"Unregistering satori account {n}...")
    #                     account = self.app.accounts[n]
    #                     account.connected.clear()
    #                     if n in accounts:
    #                         del self.app.accounts[n]
    #                 self.accounts.clear()
    #                 await asyncio.sleep(5)
    #                 logger.info(f"{self} Reconnecting...")
    #                 continue
    #
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
            await site.start()

        async with self.stage("cleanup"):
            await self.wsgi.shutdown()
            await self.wsgi.cleanup()
