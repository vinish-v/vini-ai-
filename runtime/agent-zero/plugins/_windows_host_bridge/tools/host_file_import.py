from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._windows_host_bridge.helpers import bridge_client


class HostFileImport(Tool):
    async def execute(
        self,
        host_path: str = "",
        local_path: str = "",
        register_office: bool = True,
        open_in_desktop: bool = False,
        **kwargs,
    ) -> Response:
        try:
            result = bridge_client.import_host_file(
                host_path,
                local_path,
                register_office=register_office,
                open_in_desktop=open_in_desktop,
                context_id=self.agent.context.id if self.agent and self.agent.context else "",
                agent=self.agent,
            )
        except Exception as exc:
            return Response(message=f"host_file_import failed: {exc}", break_loop=False)
        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
