from __future__ import annotations

from helpers.api import ApiHandler, Request, Response
from plugins._connectors.helpers import mcp_presets


class McpPreset(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        data = input or {}
        connector_id = str(data.get("connector_id") or "").strip()
        operation = str(data.get("operation") or "status").strip().lower()

        if operation != "refresh" and not connector_id:
            return Response(status=400, response="connector_id is required")

        if operation == "status":
            return mcp_presets.preset_status(connector_id)
        if operation == "enable":
            return mcp_presets.enable(connector_id, force=bool(data.get("force", True)))
        if operation == "start_auth":
            return await mcp_presets.start_auth(connector_id, str(data.get("user_google_email") or ""))
        if operation == "refresh":
            return mcp_presets.refresh(connector_id or None)

        return Response(status=400, response=f"Unknown MCP preset operation '{operation}'")
