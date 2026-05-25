from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._vini_app_builder.helpers.builder import handle_action


class ViniAppBuilder(Tool):
    async def execute(self, **kwargs) -> Response:
        args = dict(self.args or {})
        args.update(kwargs)
        result = handle_action(args)
        text = json.dumps(result, indent=2, ensure_ascii=False)
        return Response(message=f"vini_app_builder {args.get('action', 'list')}\n{text}", break_loop=False)
