from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Generic, TypeVar

import aiohttp

from satori.account import Account
from satori.config import Config
from satori.exception import (
    ApiNotImplementedException,
    BadRequestException,
    ForbiddenException,
    MethodNotAllowedException,
    NotFoundException,
    UnauthorizedException,
)

if TYPE_CHECKING:
    from satori.client import App

TConfig = TypeVar("TConfig", bound=Config)


class BaseNetwork(Generic[TConfig]):
    accounts: dict[str, Account]
    close_signal: asyncio.Event
    sequence: int
    session: aiohttp.ClientSession

    def __init__(self, app: App, config: TConfig):
        super().__init__()
        self.app = app
        self.config = config
        self.accounts = {}
        self.close_signal = asyncio.Event()
        self.sequence = -1

    async def wait_for_available(self):
        ...

    @property
    def alive(self) -> bool:
        ...

    async def connection_closed(self):
        self.close_signal.set()

    async def call_http(self, account: Account, action: str, params: dict | None = None) -> dict:
        endpoint = self.config.api_base / action
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.token or ''}",
            "X-Platform": account.platform,
            "X-Self-ID:": account.self_id,
        }
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
