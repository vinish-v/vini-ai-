from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._connectors.helpers import registry


class ConnectorSearch(Tool):
    async def execute(self, query: str = "", connector_type: str = "", auth: str = "", **kwargs):
        result = registry.search(query=query, connector_type=connector_type, auth=auth)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
