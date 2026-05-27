from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._windows_host_bridge.helpers import bridge_client


class HostOfficeOpen(Tool):
    async def execute(self, path: str = "", app: str = "", **kwargs) -> Response:
        try:
            result = bridge_client.open_office(path, app, self.agent)
        except Exception as exc:
            return Response(message=f"host_office_open failed: {exc}", break_loop=False)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
