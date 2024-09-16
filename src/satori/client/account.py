from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Generic, TypeVar

from yarl import URL

from satori.model import LoginType

from .protocol import ApiProtocol

TP = TypeVar("TP", bound="ApiProtocol")
TP1 = TypeVar("TP1", bound="ApiProtocol")


@dataclass
class ApiInfo:
    host: str = "localhost"
    port: int = 5140
    path: str = ""
    token: str | None = None

    def __post_init__(self):
        if self.path and not self.path.startswith("/"):
            self.path = f"/{self.path}"

    @property
    def api_base(self):
        return URL(f"http://{self.host}:{self.port}{self.path}") / "v1"


class Account(Generic[TP]):
    def __init__(
        self,
        platform: str,
        self_id: str,
        self_info: LoginType,
        config: ApiInfo,
        protocol_cls: type[TP] = ApiProtocol,
    ):
        self.platform = platform
        self.self_id = self_id
        self.self_info = self_info
        self.config = config
        self.protocol = protocol_cls(self)  # type: ignore
        self.connected = asyncio.Event()

    def custom(
        self, config: ApiInfo | None = None, protocol_cls: type[TP1] = ApiProtocol, **kwargs
    ) -> "Account[TP1]":
        return Account(
            self.platform,
            self.self_id,
            self.self_info,
            config or (ApiInfo(**kwargs) if kwargs else self.config),
            protocol_cls,  # type: ignore
        )

    @property
    def identity(self):
        return f"{self.platform}/{self.self_id}"

    def ensure_url(self, url: str) -> URL:
        """确定链接形式。

        若链接符合以下条件之一，则返回链接的代理形式 ({host}/{path}/{version}/proxy/{url})：
            - 链接以 "upload://" 开头
            - 链接开头出现在 self_info.proxy_urls 中的某一项
        """
        if url.startswith("upload"):
            return self.config.api_base / "proxy" / url.lstrip("/")
        for proxy_url in self.self_info.proxy_urls:
            if url.startswith(proxy_url):
                return self.config.api_base / "proxy" / url.lstrip("/")
        return URL(url)

    def __repr__(self):
        return f"<Account {self.self_id} ({self.platform})>"

    def __getattr__(self, item):
        return getattr(self.protocol, item)
