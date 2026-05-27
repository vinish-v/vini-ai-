from __future__ import annotations

import json
from typing import Any

from helpers.tool import Response, Tool
from plugins._browser.helpers.extraction import extract_page


class ExtractPage(Tool):
    async def execute(
        self,
        url: str = "",
        max_chars: int = 16000,
        timeout: int = 12,
        headers: dict[str, str] | None = None,
        **_: Any,
    ) -> Response:
        try:
            result = extract_page(
                url,
                max_chars=max_chars,
                timeout=timeout,
                headers=headers if isinstance(headers, dict) else None,
            )
        except Exception as exc:
            result = {
                "ok": False,
                "status": "failed",
                "url": str(url or ""),
                "error": str(exc),
                "extraction_mode": "static_html",
            }
        return Response(
            message=json.dumps(result, indent=2, ensure_ascii=False),
            break_loop=False,
        )
