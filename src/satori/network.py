from __future__ import annotations

import json
import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, cast

import aiohttp
from loguru import logger
from launart import Service
from launart.manager import Launart
from launart.utilles import any_completed

from .account import Account
from .config import ClientInfo
from .model import Event, Opcode, LoginStatus
from .exception import (
    NetworkError,
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    UnauthorizedException,
    MethodNotAllowedException,
    ApiNotImplementedException,
)

if TYPE_CHECKING:
    from .main import App


class Connection(Service):
    required: set[str] = set()
    stages: set[str] = {"preparing", "blocking", "cleanup"}

    @property
    def id(self):
        return f"satori/network/client#{self.config.host}:{self.config.port}"

    accounts: dict[str, Account]
    close_signal: asyncio.Event
    sequence: int
    connection: aiohttp.ClientWebSocketResponse | None = None
    session: aiohttp.ClientSession

    def __init__(self, app: App, config: ClientInfo):
        super().__init__()
        self.app = app
        self.config = config
        self.accounts = {}
        self.close_signal = asyncio.Event()
        self.sequence = -1

    async def message_receive(self):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        async for msg in self.connection:
            if msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED}:
                self.close_signal.set()
                break
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data: dict = json.loads(cast(str, msg.data))
                if data["op"] == 0:
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
                    await self.app.post(event)
                except Exception as e:
                    logger.warning(f"Failed to parse event: {raw}\nCaused by {e!r}")

            asyncio.create_task(event_parse_task(data))

    async def connection_closed(self):
        self.close_signal.set()

    async def send(self, payload: dict):
        if self.connection is None:
            raise RuntimeError("connection is not established")

        await self.connection.send_json(payload)

    async def call_http(self, account: Account, action: str, params: dict | None = None) -> dict:
        endpoint = self.config.api_base / action
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.token}",
            "X-Platform": account.platform,
            "X-Self-ID:": account.self_id,
        }
        try:
            async with self.session.post(
                endpoint,
                json=params or {},
                headers=headers,
            ) as resp:
                if 200 <= resp.status < 300:
                    return json.loads(content) if (content := await resp.text()) else {}
                elif resp.status == 400:
                    raise BadRequestException(await resp.text())
                elif resp.status == 401:
                    raise UnauthorizedException(await resp.text())
                elif resp.status == 403:
                    raise ForbiddenException(await resp.text())
                elif resp.status == 404:
                    raise NotFoundException(await resp.text())
                elif resp.status == 405:
                    raise MethodNotAllowedException(await resp.text())
                elif resp.status == 500:
                    raise ApiNotImplementedException(await resp.text())
                else:
                    resp.raise_for_status()
        except Exception as e:
            raise NetworkError(f"Error while calling {endpoint}") from e

    @property
    def alive(self):
        return self.connection is not None and not self.connection.closed

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

        resp = await self.connection.receive_json()
        if resp["op"] != Opcode.READY:
            logger.error(f"Received unexpected payload: {resp}")
            return False
        for login in resp["body"]["logins"]:
            if "self_id" not in login:
                continue
            platform = login.get("platform", "satori")
            self_id = login["self_id"]
            identity = f"{platform}/{self_id}"
            if identity in self.app.accounts:
                account = self.app.accounts[identity]
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
            async with session.ws_connect(
                self.config.ws_base / "events",
            ) as self.connection:
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
                            del self.accounts[v.identity]
                    return
                if close_task in done:
                    receiver_task.cancel()
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
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await self.daemon(manager, self.session)

        async with self.stage("cleanup"):
            await self.session.close()
            self.connection = None
