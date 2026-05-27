from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._windows_host_bridge.helpers import bridge_client


class HostFileExport(Tool):
    async def execute(self, local_path: str = "", host_path: str = "", **kwargs) -> Response:
        try:
            result = bridge_client.export_host_file(local_path, host_path, agent=self.agent)
        except Exception as exc:
            return Response(message=f"host_file_export failed: {exc}", break_loop=False)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
