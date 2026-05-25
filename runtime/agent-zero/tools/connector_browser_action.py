from __future__ import annotations

import json

from helpers.tool import Response, Tool
from plugins._browser.tools.browser import Browser
from plugins._connectors.helpers import registry
from tools.connector_payload import normalize_payload


class ConnectorBrowserAction(Tool):
    async def execute(
        self,
        connector_id: str = "",
        url: str = "",
        browser_action: str = "open",
        payload: dict | str | None = None,
        execute_browser: bool = True,
        **kwargs,
    ):
        data = normalize_payload(payload, kwargs)
        if url:
            data["url"] = url
        if browser_action:
            data["browser_action"] = browser_action

        result = registry.run_action("browser_action", connector_id, data, confirmed=True)
        if result.get("ok") and execute_browser:
            action = str(result.get("browser_action") or "open").strip().lower()
            if action != "open":
                result["browser_result"] = {
                    "ok": False,
                    "message": "connector_browser_action currently executes only browser open. Use the browser tool for follow-up clicks, typing, and extraction.",
                }
            else:
                browser = Browser(
                    agent=self.agent,
                    name="browser",
                    method=None,
                    args={"action": "open", "url": result.get("url", "")},
                    message=self.message,
                    loop_data=self.loop_data,
                )
                response = await browser.execute(action="open", url=str(result.get("url") or ""))
                try:
                    result["browser_result"] = json.loads(response.message)
                except Exception:
                    result["browser_result"] = {"message": response.message}

        return Response(message=json.dumps(result, indent=2, ensure_ascii=False), break_loop=False)
