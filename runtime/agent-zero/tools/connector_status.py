from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._connectors.helpers import registry


class ConnectorStatus(Tool):
    async def execute(self, connector_id: str = "", **kwargs):
        result = registry.status(connector_id or None)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
