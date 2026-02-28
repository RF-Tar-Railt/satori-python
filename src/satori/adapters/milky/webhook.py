from __future__ import annotations

import aiohttp
from launart import Launart
from loguru import logger
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from yarl import URL

from .base import MilkyBaseAdapter


class MilkyWebhookAdapter(MilkyBaseAdapter):

    def __init__(
        self,
        endpoint: str | URL,
        *,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        path: str = "/milky",
        self_token: str | None = None,
    ):
        super().__init__(endpoint, token=token, headers=headers)
        self.webhook_token = self_token if self_token is not None else token
        self.webhook_paths = self._normalize_webhook_paths(path)

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            self.session = aiohttp.ClientSession()

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            if self.session:
                await self.session.close()
            self.session = None
            await self._handle_disconnect()

    def get_routes(self) -> list[Route]:
        return [Route(path, self.webhook_endpoint, methods=["POST"]) for path in self.webhook_paths]

    def _normalize_webhook_paths(self, webhook_path: str) -> tuple[str, ...]:
        path = webhook_path or "/"
        normalized = path if path.startswith("/") else f"/{path}"
        paths: set[str] = {normalized}
        stripped = normalized.rstrip("/")
        if stripped and stripped != normalized:
            paths.add(stripped)
        return tuple(sorted(paths))

    async def webhook_endpoint(self, request: StarletteRequest) -> Response:
        if self.webhook_token:
            auth_header = request.headers.get("Authorization")
            provided = None
            if auth_header:
                if auth_header.lower().startswith("bearer "):
                    provided = auth_header[7:]
                else:
                    provided = auth_header
            if provided is None:
                provided = request.query_params.get("access_token")
            if provided != self.webhook_token:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            payload = await request.json()
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to parse milky webhook payload: {e}")
            return JSONResponse({"error": "invalid json"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "invalid payload"}, status_code=400)
        try:
            await self.handle_event(payload)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Error while processing milky webhook event", exc_info=e)
            return JSONResponse({"error": "internal error"}, status_code=500)
        return Response(status_code=204)


__all__ = ["MilkyWebhookAdapter"]
