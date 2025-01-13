from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import cast

import aiohttp
from launart.manager import Launart
from launart.utilles import any_completed
from loguru import logger

from satori.model import Event, Identify, LoginStatus, MetaPayload, Opcode, Ready

from ..account import Account
from ..config import WebsocketsInfo as WebsocketsInfo
from .base import BaseNetwork


class WsNetwork(BaseNetwork[WebsocketsInfo]):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    @property
    def id(self):
        return f"satori/network/ws/{self.config.identity}#{id(self)}"

    connection: aiohttp.ClientWebSocketResponse | None = None

    def post_event(self, body: dict):
        async def event_parse_task(raw: dict):
            try:
                event = Event.parse(raw)
            except Exception as e:
                if (
                    "self_id" in raw
                    or ("login" in raw and "self_id" in raw["login"])
                    or ("login" in raw and "user" in raw["login"] and "self_id" in raw["login"]["user"])
                ):
                    logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")
                else:
                    logger.trace(f"Failed to parse event: {raw}\nCaused by {e!r}")
            else:
                logger.trace(f"Received event: {event}")
                self.sequence = event.sn
                await self.app.post(event, self)

        return asyncio.create_task(event_parse_task(body))

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        async for msg in self.connection:
            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                return
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = json.loads(cast(str, msg.data))
                logger.trace(f"Received payload: {data}")
                if data["op"] == Opcode.EVENT:
                    self.post_event(data["body"])
                elif data["op"] == Opcode.META:
                    payload = MetaPayload.parse(data["body"])
                    self.proxy_urls = payload.proxy_urls
                    for account in self.accounts.values():
                        account.proxy_urls = payload.proxy_urls.copy()
                elif data["op"] > 5:
                    logger.warning(f"Received unknown event: {data}")
                continue
        else:
            await self.connection_closed()

    async def send(self, payload: dict):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        await self.connection.send_json(payload)

    @property
    def alive(self):
        return self.connection is not None and not self.connection.closed

    async def wait_for_available(self):
        await self.status.wait_for_available()

    async def _authenticate(self):
        """鉴权连接"""
        if not self.connection:
            raise RuntimeError("connection is not established")
        payload = Identify(self.config.token)
        if self.sequence > -1:
            payload.sn = self.sequence
        try:
            await self.send({"op": Opcode.IDENTIFY.value, "body": payload.dump()})
        except Exception as e:
            logger.error(f"Error while sending IDENTIFY event: {e!r}")
            return False

        resp = await self.connection.receive()
        if resp.type != aiohttp.WSMsgType.TEXT:
            logger.error(f"Received unexpected payload: {resp}")
            return False
        data = resp.json()
        if data["op"] != Opcode.READY:
            logger.error(f"Received unexpected payload: {data}")
            return False
        ready = Ready.parse(data["body"])
        self.proxy_urls = ready.proxy_urls
        for login in ready.logins:
            if not login.user:
                continue
            login_sn = f"{login.user.id}@{id(self)}"
            if login_sn in self.app.accounts:
                account = self.app.accounts[login_sn]
                self.accounts[login_sn] = account
                if login.status == LoginStatus.ONLINE:
                    account.connected.set()
                else:
                    account.connected.clear()
                account.config = self.config
            else:
                account = Account(login, self.config, ready.proxy_urls, self.app.default_api_cls)
                logger.info(f"account registered: {account}")
                (account.connected.set() if login.status == LoginStatus.ONLINE else account.connected.clear())
                self.app.accounts[login_sn] = account
                self.accounts[login_sn] = account
            await self.app.account_update(account, LoginStatus.ONLINE)
        if not self.accounts:
            logger.warning(f"No account available for {self.config}")
            # return False
        return True

    async def _heartbeat(self):
        """心跳"""
        while True:
            with suppress(Exception):
                await self.send({"op": 1})
            await asyncio.sleep(9)

    async def daemon(self, manager: Launart, session: aiohttp.ClientSession):
        while not manager.status.exiting:
            try:
                async with session.ws_connect(self.config.ws_base / "events", timeout=30) as self.connection:
                    logger.debug(f"{self.id} Websocket client connected")
                    self.close_signal.clear()
                    result = await self._authenticate()
                    if not result:
                        await asyncio.sleep(3)
                        continue
                    self.close_signal.clear()
                    close_task = asyncio.create_task(self.close_signal.wait())
                    receiver_task = asyncio.create_task(self.message_receive())
                    sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
                    heartbeat_task = asyncio.create_task(self._heartbeat())
                    done, pending = await any_completed(
                        sigexit_task,
                        close_task,
                        receiver_task,
                        heartbeat_task,
                    )
                    if sigexit_task in done:
                        logger.info(f"{self.id} Websocket client exiting...")
                        await self.connection.close()
                        self.close_signal.set()
                        self.connection = None
                        for v in list(self.app.accounts.values()):
                            if (identity := f"{v.self_id}@{id(self)}") in self.accounts:
                                v.connected.clear()
                                await self.app.account_update(v, LoginStatus.OFFLINE)
                                del self.app.accounts[identity]
                                del self.accounts[identity]
                        return
                    if close_task in done:
                        receiver_task.cancel()
                        logger.warning(f"{self} Connection closed by server, will reconnect in 5 seconds...")
                        for k in self.accounts.keys():
                            logger.debug(f"Unregistering satori account {k}...")
                            account = self.app.accounts[k]
                            account.connected.clear()
                            await self.app.account_update(account, LoginStatus.RECONNECT)
                        self.accounts.clear()
                        await asyncio.sleep(5)
                        logger.info(f"{self} Reconnecting...")
                        continue
            except Exception as e:
                logger.error(f"{self} Error while connecting: {e}")
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.daemon(manager, session)

        async with self.stage("cleanup"):
            await session.close()
