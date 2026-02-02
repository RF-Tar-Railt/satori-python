import asyncio
from dataclasses import dataclass
from datetime import datetime
from weakref import finalize


@dataclass
class Audit:
    id: str
    guild_id: str
    channel_id: str
    seq: str
    create_time: datetime
    audit_time: datetime
    message_id: str | None = None


class AuditResultStore:
    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        finalize(self, self._futures.clear)

    def add_result(self, result: dict):
        audit = Audit(
            result["audit_id"],
            result["guild_id"],
            result["channel_id"],
            result["seq_in_channel"],
            datetime.fromisoformat(result["create_time"]),
            datetime.fromisoformat(result["audit_time"]),
            result.get("message_id"),
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
