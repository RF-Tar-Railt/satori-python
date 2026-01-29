import asyncio
from weakref import finalize


class AuditResultStore:
    def __init__(self) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        finalize(self, self._futures.clear)

    def add_result(self, result: dict):
        audit = result["auditId"]
        if future := self._futures.get(audit):
            future.set_result(result)

    async def fetch(self, audit: str, timeout: float = 30) -> dict | None:
        future = asyncio.get_event_loop().create_future()
        self._futures[audit] = future
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            del self._futures[audit]


audit_result = AuditResultStore()
