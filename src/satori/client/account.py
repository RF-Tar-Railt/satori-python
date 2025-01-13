from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Generic, TypeVar

from yarl import URL

from satori.model import Login

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
        login: Login,
        config: ApiInfo,
        proxy_urls: list[str],
        protocol_cls: type[TP] = ApiProtocol,
    ):
        self.adapter = login.adapter
        self.self_info = login
        self.config = config
        self.proxy_urls = proxy_urls
        self.protocol = protocol_cls(self)  # type: ignore
        self.connected = asyncio.Event()

    @property
    def platform(self):
        return self.self_info.platform or "satori"

    @property
    def self_id(self):
        return self.self_info.user.id

    def custom(
        self, config: ApiInfo | None = None, protocol_cls: type[TP1] = ApiProtocol, **kwargs
    ) -> "Account[TP1]":
        return Account(
            self.self_info,
            config or (ApiInfo(**kwargs) if kwargs else self.config),
            self.proxy_urls,
            protocol_cls,  # type: ignore
        )

    def ensure_url(self, url: str) -> URL:
        """确定链接形式。

        若链接符合以下条件之一，则返回链接的代理形式 ({host}/{path}/{version}/proxy/{url})：
            - 链接以 "internal:" 开头
            - 链接开头出现在 proxy_urls 中的某一项
        """
        if url.startswith("internal:"):
            return self.config.api_base / "proxy" / url.lstrip("/")
        for proxy_url in self.proxy_urls:
            if url.startswith(proxy_url):
                return self.config.api_base / "proxy" / url.lstrip("/")
        return URL(url)

    def __repr__(self):
        return f"<Account {self.self_id} ({self.platform})>"

    def __getattr__(self, item):
        if hasattr(self.protocol, item):
            return getattr(self.protocol, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")
