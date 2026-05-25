from __future__ import annotations

from helpers.api import ApiHandler, Request, Response
from plugins._connectors.helpers import registry


class Action(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        data = input or {}
        connector_id = str(data.get("connector_id") or "").strip()
        action = str(data.get("action") or "").strip()
        if not connector_id:
            return Response(status=400, response="connector_id is required")
        if not action:
            return Response(status=400, response="action is required")
        return await registry.run_action_async(
            action,
            connector_id,
            data.get("payload") if isinstance(data.get("payload"), dict) else {},
            confirmed=bool(data.get("confirmed")),
        )
