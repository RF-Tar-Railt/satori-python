from __future__ import annotations

import asyncio
from datetime import datetime
from typing import cast

import aiohttp
from launart.manager import Launart
from launart.utilles import any_completed
from loguru import logger

from satori.const import EventType
from satori.model import Event, Identify, LoginStatus, MetaPayload, Opcode, Ready
from satori.reconnect import RECONNECT_STABLE_SECONDS, ReconnectPolicy, is_normal_close, is_server_shutdown
from satori.utils import decode, encode

from ..config import WebsocketsInfo as WebsocketsInfo
from .base import BaseNetwork


class WsNetwork(BaseNetwork[WebsocketsInfo]):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    @property
    def id(self):
        return f"satori/net/ws/{self.config.identity}#{id(self):x}"

    connection: aiohttp.ClientWebSocketResponse | None = None

    async def event_parse_task(self, raw: dict):
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
            self.sequence = event.sn
            await self.app.post(event, self)

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        while True:
            msg = await self.connection.receive()
            if msg.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.ERROR,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
            }:
                await self.connection_closed()
                return
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = decode(msg.data)
                if data["op"] == Opcode.EVENT:
                    asyncio.create_task(self.event_parse_task(data["body"]))
                elif data["op"] == Opcode.META:
                    payload = MetaPayload.parse(data["body"])
                    self.proxy_urls = payload.proxy_urls
                    for account in self.accounts.values():
                        account.proxy_urls = payload.proxy_urls.copy()
                elif data["op"] > 5:
                    logger.warning(f"Received unknown event: {data}")
                else:
                    logger.trace(f"Received payload: {data}")
                continue

    async def send(self, payload: dict):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        await self.connection.send_str(encode(payload))

    @property
    def alive(self):
        return self.connection is not None and not self.connection.closed

    async def wait_for_available(self):
        await self.status.wait_for_available()

    async def _authenticate(self):
        """鉴权连接"""
        if not self.connection:
            raise RuntimeError("connection is not established")
        payload = Identify(token=self.config.token)
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
        data = decode(cast(str, resp.data))
        if data["op"] != Opcode.READY:
            logger.error(f"Received unexpected payload: {data}")
            return False
        ready = Ready.parse(data["body"])
        self.proxy_urls = ready.proxy_urls
        for login in ready.logins:
            if login.identifier in self.accounts:
                await self.app.post(Event(EventType.LOGIN_UPDATED, datetime.now(), login), self)
            else:
                await self.app.post(Event(EventType.LOGIN_ADDED, datetime.now(), login), self)
        if not self.accounts:
            logger.warning(f"No account available for {self.config}")
            # return False
        return True

    async def _heartbeat(self):
        """心跳"""
        while True:
            try:
                await self.send({"op": 1})
            except Exception as e:
                logger.error(f"Error while sending heartbeat: {e!r}")
            await asyncio.sleep(9)

    async def _mark_accounts(self, status: LoginStatus, *, removed: bool = False):
        event_type = EventType.LOGIN_REMOVED if removed else EventType.LOGIN_UPDATED
        for account in list(self.accounts.values()):
            if status in (LoginStatus.ONLINE, LoginStatus.CONNECT):
                account.connected.set()
            else:
                account.connected.clear()
            account.self_info.status = status
            await self.app.post(Event(event_type, datetime.now(), account.self_info), self)
        if removed:
            self.accounts.clear()

    async def daemon(self, manager: Launart, session: aiohttp.ClientSession):
        policy = ReconnectPolicy()
        while not manager.status.exiting:
            try:
                await self._mark_accounts(LoginStatus.RECONNECT)
                async with session.ws_connect(self.config.ws_base / "events", timeout=300) as self.connection:
                    logger.debug(f"{self.id} Websocket client connected")
                    await self._mark_accounts(LoginStatus.CONNECT)
                    self.close_signal.clear()
                    result = await self._authenticate()
                    if not result:
                        code = self.connection.close_code
                        if is_normal_close(code):
                            logger.info(f"{self.id} Connection closed by server (code={code}), login removed")
                            await self._mark_accounts(LoginStatus.OFFLINE, removed=True)
                            if not is_server_shutdown(code):
                                return
                        await self._mark_accounts(LoginStatus.RECONNECT)
                        if not await policy.sleep():
                            logger.error(f"{self.id} Reconnect attempts exhausted, marking accounts offline")
                            await self._mark_accounts(LoginStatus.OFFLINE)
                            return
                        logger.info(f"{self.id} Reconnecting...")
                        continue
                    connected_at = asyncio.get_running_loop().time()
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
                        await self._mark_accounts(LoginStatus.OFFLINE, removed=True)
                        return
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    code = self.connection.close_code if self.connection else None
                    if is_normal_close(code):
                        logger.info(f"{self.id} Connection closed by server (code={code}), login removed")
                        await self._mark_accounts(LoginStatus.OFFLINE, removed=True)
                        if not is_server_shutdown(code):
                            return
                    if connected_at and asyncio.get_running_loop().time() - connected_at >= RECONNECT_STABLE_SECONDS:
                        policy.reset()
                    await self._mark_accounts(LoginStatus.RECONNECT)
                    if not await policy.sleep():
                        logger.error(f"{self.id} Reconnect attempts exhausted, marking accounts offline")
                        await self._mark_accounts(LoginStatus.OFFLINE)
                        return
                    logger.info(f"{self.id} Reconnecting...")
                    continue
            except Exception as e:
                logger.error(f"{self.id} Error while connecting: {e}")
                await self._mark_accounts(LoginStatus.RECONNECT)
                if not await policy.sleep():
                    logger.error(f"{self.id} Reconnect attempts exhausted, marking accounts offline")
                    await self._mark_accounts(LoginStatus.OFFLINE)
                    return
                logger.info(f"{self.id} Reconnecting...")

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.daemon(manager, session)

        async with self.stage("cleanup"):
            await session.close()
