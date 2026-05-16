import asyncio
from dataclasses import dataclass
from datetime import datetime
from weakref import finalize


@dataclass
class Audit:
    id: str
    channel_id: str
    create_time: datetime
    audit_time: datetime
    message_id: str | None = None
    guild_id: str | None = None
    seq: str | None = None


class AuditResultStore:
    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        finalize(self, self._futures.clear)

    def add_result(self, result: dict):
        if "group_id" in result:
            result["channel_id"] = result.pop("group_id")
        elif "group_openid" in result:
            result["channel_id"] = result.pop("group_openid")
        audit = Audit(
            result["audit_id"],
            result["channel_id"],
            datetime.fromisoformat(result["create_time"]),
            datetime.fromisoformat(result["audit_time"]),
            result.get("message_id"),
            result.get("guild_id"),
            result.get("seq_in_channel"),
        )
        if future := self._futures.get(audit.id):
            future.set_result(audit)

    async def fetch(self, audit: str, timeout: float = 30) -> Audit | None:
        future = asyncio.get_event_loop().create_future()
        self._futures[audit] = future
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            del self._futures[audit]


audit_result = AuditResultStore()
