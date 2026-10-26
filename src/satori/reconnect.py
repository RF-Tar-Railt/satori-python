from __future__ import annotations

import asyncio

RECONNECT_DELAYS: tuple[float, ...] = (5.0, 10.0, 20.0, 40.0, 60.0)
"""断线重连的退避时间（秒）。"""

RECONNECT_ATTEMPTS_PER_DELAY = 5
"""每个退避档位的重试次数。"""

MAX_RECONNECT_ATTEMPTS = len(RECONNECT_DELAYS) * RECONNECT_ATTEMPTS_PER_DELAY
"""连续重连失败的最大次数。"""

RECONNECT_STABLE_SECONDS = 60.0
"""连接稳定超过该时长后，重置重连计数。"""

RECONNECT_TOTAL_SECONDS = sum(delay * RECONNECT_ATTEMPTS_PER_DELAY for delay in RECONNECT_DELAYS)
"""完整走完一轮重连退避所需的总时长（秒）。"""

SERVER_SHUTDOWN_CLOSE_CODES = frozenset({1000, 1001, 1012})
"""服务端主动下线或重启时使用的 WebSocket 关闭码。

- ``1000`` Normal Closure：正常的主动关闭。
- ``1001`` Going Away：服务端或代理准备下线。
- ``1012`` Service Restart：uvicorn 等服务端优雅关闭时发送的关闭码。
"""

AUTH_FAILURE_CLOSE_CODES = frozenset({3000})
"""Satori 服务端鉴权失败时使用的自定义关闭码。"""

NORMAL_CLOSE_CODES = SERVER_SHUTDOWN_CLOSE_CODES | AUTH_FAILURE_CLOSE_CODES
"""主动关闭的 WebSocket 关闭码。"""


def is_normal_close(code: int | None) -> bool:
    """判断 WebSocket 是否为主动关闭（服务端关闭或本端主动退出）。"""
    return code in NORMAL_CLOSE_CODES


def is_server_shutdown(code: int | None) -> bool:
    """判断 WebSocket 是否由服务端主动下线或重启导致。"""
    return code in SERVER_SHUTDOWN_CLOSE_CODES


class ReconnectPolicy:
    """有上限的断线重连策略。

    连续失败时按 ``RECONNECT_DELAYS`` 的顺序退避，每个档位重试
    ``RECONNECT_ATTEMPTS_PER_DELAY`` 次；连接稳定后调用 :meth:`reset`。
    """

    def __init__(
        self,
        delays: tuple[float, ...] = RECONNECT_DELAYS,
        attempts_per_delay: int = RECONNECT_ATTEMPTS_PER_DELAY,
    ):
        if not delays:
            raise ValueError("delays must not be empty")
        if attempts_per_delay <= 0:
            raise ValueError("attempts_per_delay must be positive")
        self.delays = delays
        self.attempts_per_delay = attempts_per_delay
        self.attempts = 0

    @property
    def max_attempts(self) -> int:
        return len(self.delays) * self.attempts_per_delay

    @property
    def exhausted(self) -> bool:
        return self.attempts >= self.max_attempts

    def reset(self) -> None:
        self.attempts = 0

    def next_delay(self) -> float | None:
        """返回下一次重连前的等待时间；次数用尽时返回 ``None``。"""
        if self.exhausted:
            return None
        index = min(self.attempts // self.attempts_per_delay, len(self.delays) - 1)
        self.attempts += 1
        return self.delays[index]

    async def sleep(self) -> bool:
        """等待下一次重连；次数用尽时返回 ``False``。"""
        delay = self.next_delay()
        if delay is None:
            return False
        await asyncio.sleep(delay)
        return True


__all__ = [
    "AUTH_FAILURE_CLOSE_CODES",
    "MAX_RECONNECT_ATTEMPTS",
    "NORMAL_CLOSE_CODES",
    "RECONNECT_ATTEMPTS_PER_DELAY",
    "RECONNECT_DELAYS",
    "RECONNECT_STABLE_SECONDS",
    "RECONNECT_TOTAL_SECONDS",
    "SERVER_SHUTDOWN_CLOSE_CODES",
    "ReconnectPolicy",
    "is_normal_close",
    "is_server_shutdown",
]
