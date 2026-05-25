from __future__ import annotations

from helpers.api import ApiHandler, Request, Response
from plugins._connectors.helpers import registry


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        connector_id = str((input or {}).get("connector_id") or "").strip()
        result = registry.status(connector_id or None)
        if not result.get("ok"):
            return Response(status=404, response=result.get("error") or "Connector not found")
        return result
