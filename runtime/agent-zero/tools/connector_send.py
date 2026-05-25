from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._connectors.helpers import registry
from tools.connector_payload import normalize_payload


class ConnectorSend(Tool):
    async def execute(self, connector_id: str = "", payload: dict | str | None = None, confirmed: bool = False, **kwargs):
        result = await registry.run_action_async("send", connector_id, normalize_payload(payload, kwargs), confirmed=confirmed)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
