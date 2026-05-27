from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._windows_host_bridge.helpers import bridge_client


class HostFileList(Tool):
    async def execute(self, path: str = "", **kwargs) -> Response:
        try:
            result = bridge_client.list_host(path, self.agent)
        except Exception as exc:
            return Response(message=f"host_file_list failed: {exc}", break_loop=False)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
