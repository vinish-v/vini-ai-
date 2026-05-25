from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._connectors.helpers import registry
from tools.connector_payload import normalize_payload


class ConnectorRead(Tool):
    async def execute(self, connector_id: str = "", payload: dict | str | None = None, **kwargs):
        result = await registry.run_action_async("read", connector_id, normalize_payload(payload, kwargs), confirmed=bool(kwargs.get("confirmed")))
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
