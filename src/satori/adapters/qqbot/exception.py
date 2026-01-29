import json
from collections.abc import Mapping

from satori.exception import ActionFailed as BaseActionFailed
from satori.exception import UnauthorizedException as BaseUnauthorizedException

from .audit_store import audit_result


class ActionFailed(BaseActionFailed):
    def __init__(self, status: int, headers: Mapping, response: str | None = None):
        self.body = {}
        self.headers = headers
        if response:
            try:
                self.body = json.loads(response)
            except json.JSONDecodeError:
                pass
        self.status = status
        self.reason = self.body.get("message", "Unknown Error")

    @property
    def code(self) -> int | None:
        return None if self.body is None else self.body.get("code", None)

    @property
    def message(self) -> str | None:
        return None if self.body is None else self.body.get("message", None)

    @property
    def data(self) -> dict | None:
        return None if self.body is None else self.body.get("data", None)

    @property
    def trace_id(self) -> str | None:
        return self.headers.get("X-Tps-trace-ID", None)

    def __repr__(self) -> str:
        args = ("code", "message", "data", "trace_id")
        return (
            f"<{self.__class__.__name__}: {self.status}, "
            + ", ".join(f"{k}={v}" for k in args if (v := getattr(self, k)) is not None)
            + ">"
        )


class UnauthorizedException(ActionFailed, BaseUnauthorizedException):
    pass


class RateLimitException(ActionFailed):
    pass


class ApiNotAvailable(ActionFailed):
    pass


class AuditException(Exception):
    """消息审核"""

    def __init__(self, audit_id: str):
        super().__init__()
        self.audit_id = audit_id

    async def get_audit_result(self, timeout: float | None = None):
        """获取审核结果"""
        return await audit_result.fetch(self.audit_id, timeout or 60)
