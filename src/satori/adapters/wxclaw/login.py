from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from typing_extensions import Self

if TYPE_CHECKING:
    from .main import WxClawAdapter

DEFAULT_BOT_TYPE = "3"
MAX_QR_REFRESH_COUNT = 3
DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"

VerifyCodeCallback = Callable[[], Awaitable[str]]


@dataclass(slots=True)
class WxClawLoginResult:
    connected: bool = False
    account_id: str = ""
    token: str = ""
    base_url: str = ""
    user_id: str = ""
    qrcode_url: str = ""
    message: str = ""
    need_verify_code: bool = False


@dataclass(slots=True)
class QrLoginSession:
    _adapter: WxClawAdapter = field(repr=False)
    _base_url: str = DEFAULT_BASE_URL
    _bot_type: str = DEFAULT_BOT_TYPE
    _timeout: float = 480
    _auto_connect: bool = False
    _verify_code_callback: VerifyCodeCallback | None = None

    qrcode: str = ""
    qrcode_url: str = ""

    async def __aenter__(self) -> Self:
        self.qrcode, self.qrcode_url = await self._adapter.start_qr_login(
            base_url=self._base_url,
            bot_type=self._bot_type,
        )
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def wait(self) -> WxClawLoginResult:
        async def on_refresh(qrcode: str, qrcode_url: str):
            self.qrcode = qrcode
            self.qrcode_url = qrcode_url

        result = await self._adapter.wait_qr_login(
            qrcode=self.qrcode,
            base_url=self._base_url,
            bot_type=self._bot_type,
            timeout=self._timeout,
            on_refresh=on_refresh,
            verify_code_callback=self._verify_code_callback,
        )
        result.qrcode_url = self.qrcode_url
        if self._auto_connect and result.connected:
            self._adapter.connect_login_result(result, self._base_url)
        return result
