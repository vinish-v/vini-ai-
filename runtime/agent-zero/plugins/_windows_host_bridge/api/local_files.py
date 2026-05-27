from __future__ import annotations

from helpers.api import ApiHandler, Request
from plugins._windows_host_bridge.helpers import bridge_client


class LocalFiles(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        action = str(input.get("action") or "status").strip().lower().replace("-", "_")
        try:
            if action == "status":
                return bridge_client.status()
            if action == "list":
                return bridge_client.list_host(str(input.get("path") or ""))
            if action == "stat":
                return bridge_client.stat_host(str(input.get("path") or ""))
            if action == "exists":
                return bridge_client.exists_host(str(input.get("path") or ""))
            if action == "import":
                return bridge_client.import_host_file(
                    str(input.get("host_path") or input.get("path") or ""),
                    str(input.get("local_path") or ""),
                    register_office=input.get("register_office") is not False,
                    open_in_desktop=input.get("open_in_desktop") is True,
                    context_id=str(input.get("ctxid") or input.get("context_id") or ""),
                )
            if action == "export":
                return bridge_client.export_host_file(
                    str(input.get("local_path") or ""),
                    str(input.get("host_path") or input.get("path") or ""),
                )
            if action == "open":
                return bridge_client.open_host(str(input.get("path") or ""))
            if action == "office_status":
                return bridge_client.request(bridge_client.config(), "POST", "/office/status", {})
            if action == "office_open":
                return bridge_client.open_office(str(input.get("path") or ""), str(input.get("app") or ""))
            return {"ok": False, "error": f"Unsupported local files action: {action}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "action": action}
