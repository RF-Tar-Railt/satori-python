from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import cast

import aiohttp
from launart import Service
from launart.manager import Launart
from launart.utilles import any_completed
from loguru import logger

from satori.account import Account
from satori.config import ClientInfo
from satori.model import Event, LoginStatus, Opcode

from .base import BaseNetwork


class WsNetwork(BaseNetwork[ClientInfo], Service):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    @property
    def id(self):
        return f"satori/network/ws#{self.config.host}:{self.config.port}"

    connection: aiohttp.ClientWebSocketResponse | None = None

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        async for msg in self.connection:
            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = json.loads(cast(str, msg.data))
                if data["op"] == Opcode.EVENT:
                    yield self, data["body"]
                elif data["op"] > 4:
                    logger.warning(f"Received unknown event: {data}")
        else:
            await self.connection_closed()

    async def message_handle(self):
        async for connection, data in self.message_receive():
            self.sequence = int(data["id"])

            async def event_parse_task(raw: dict):
                try:
                    event = Event.parse(raw)
                except Exception as e:
                    logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")
                else:
                    await self.app.post(event)

            asyncio.create_task(event_parse_task(data))

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
        payload = {
            "op": Opcode.IDENTIFY,
            "body": {
                "token": self.config.token,
            },
        }
        if self.sequence > -1:
            payload["body"]["sequence"] = self.sequence
        try:
            await self.send(payload)
        except Exception as e:
            logger.error(f"Error while sending IDENTIFY event: {e}")
            return False

        resp = await self.connection.receive()
        if resp.type != aiohttp.WSMsgType.TEXT:
            logger.error(f"Received unexpected payload: {resp}")
            return False
        data = resp.json()
        if data["op"] != Opcode.READY:
            logger.error(f"Received unexpected payload: {data}")
            return False
        for login in data["body"]["logins"]:
            if "self_id" not in login:
                continue
            platform = login.get("platform", "satori")
            self_id = login["self_id"]
            identity = f"{platform}/{self_id}"
            if identity in self.app.accounts:
                account = self.app.accounts[identity]
                self.accounts[identity] = account
                if login["status"] == LoginStatus.ONLINE:
                    account.connected.set()
                else:
                    account.connected.clear()
                account.client = self
            else:
                account = Account(platform, self_id, self)
                logger.info(f"account registered: {account}")
                account.connected.set() if login[
                    "status"
                ] == LoginStatus.ONLINE else account.connected.clear()
                self.app.accounts[identity] = account
                self.accounts[identity] = account
                await self.app.account_update(account, LoginStatus.ONLINE)
            await self.app.account_update(account, LoginStatus.CONNECT)
        if not self.accounts:
            logger.warning(f"No account available for {self.config}")
            return False
        return True

    async def _heartbeat(self):
        """心跳"""
        while True:
            if self.sequence:
                with suppress(Exception):
                    await self.send({"op": 1})
            await asyncio.sleep(9)

    async def daemon(self, manager: Launart, session: aiohttp.ClientSession):
        while not manager.status.exiting:
            try:
                async with session.ws_connect(self.config.ws_base / "events", timeout=30) as self.connection:
                    logger.debug(f"{self.config.ws_base} Websocket client connected")
                    self.close_signal.clear()
                    result = await self._authenticate()
                    if not result:
                        await asyncio.sleep(3)
                        continue
                    self.close_signal.clear()
                    close_task = asyncio.create_task(self.close_signal.wait())
                    receiver_task = asyncio.create_task(self.message_handle())
                    sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
                    heartbeat_task = asyncio.create_task(self._heartbeat())
                    done, pending = await any_completed(
                        sigexit_task,
                        close_task,
                        receiver_task,
                        heartbeat_task,
                    )
                    if sigexit_task in done:
                        logger.info(f"{self} Websocket client exiting...")
                        await self.connection.close()
                        self.close_signal.set()
                        self.connection = None
                        for v in list(self.app.accounts.values()):
                            if v.identity in self.accounts:
                                v.connected.clear()
                                del self.accounts[v.identity]
                        return
                    if close_task in done:
                        receiver_task.cancel()
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
            except Exception as e:
                logger.error(f"{self} Error while connecting: {e}")
                await asyncio.sleep(5)
                logger.info(f"{self} Reconnecting...")

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.daemon(manager, self.session)

        async with self.stage("cleanup"):
            await self.session.close()
            self.connection = None
