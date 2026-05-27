import json
from typing import Any

from helpers.tool import Tool, Response
from plugins._windows_host_bridge.helpers import bridge_client


class WindowsHostBridge(Tool):
    async def execute(self, **kwargs) -> Response:
        action = str(self.args.get("action") or kwargs.get("action") or "status").strip().lower()
        cfg = bridge_client.config(self.agent)

        if not cfg["enabled"]:
            return Response(message="Windows host bridge is disabled in plugin settings.", break_loop=False)

        try:
            if action == "status":
                result = bridge_client.status(self.agent)
            elif action == "list":
                result = bridge_client.list_host(_required(self.args, "path"), self.agent)
            elif action == "stat":
                result = bridge_client.stat_host(_required(self.args, "path"), self.agent)
            elif action == "exists":
                result = bridge_client.exists_host(_required(self.args, "path"), self.agent)
            elif action == "read":
                result = bridge_client.request(cfg, "POST", "/file/read", {"path": _required(self.args, "path")})
            elif action == "write":
                result = bridge_client.request(
                    cfg,
                    "POST",
                    "/file/write",
                    {
                        "path": _required(self.args, "path"),
                        "content": str(self.args.get("content", "")),
                        "mode": self.args.get("mode", "overwrite"),
                        "createDirs": self.args.get("create_dirs", True),
                    },
                )
            elif action == "mkdir":
                result = bridge_client.request(
                    cfg,
                    "POST",
                    "/file/mkdir",
                    {"path": _required(self.args, "path"), "recursive": self.args.get("recursive", True)},
                )
            elif action == "delete":
                result = bridge_client.request(
                    cfg,
                    "POST",
                    "/file/delete",
                    {"path": _required(self.args, "path"), "recursive": self.args.get("recursive", False)},
                )
            elif action == "run":
                result = bridge_client.request(
                    cfg,
                    "POST",
                    "/command/run",
                    {
                        "command": _required(self.args, "command"),
                        "cwd": self.args.get("cwd"),
                        "timeoutMs": int(self.args.get("timeout_ms", 30000)),
                    },
                )
            elif action == "import":
                result = bridge_client.import_host_file(
                    _required(self.args, "host_path"),
                    str(self.args.get("local_path") or ""),
                    register_office=bool(self.args.get("register_office", True)),
                    open_in_desktop=bool(self.args.get("open_in_desktop", False)),
                    context_id=self.agent.context.id if self.agent and self.agent.context else "",
                    agent=self.agent,
                )
            elif action == "export":
                result = bridge_client.export_host_file(
                    _required(self.args, "local_path"),
                    _required(self.args, "host_path"),
                    agent=self.agent,
                )
            elif action == "open":
                result = bridge_client.open_host(_required(self.args, "path"), self.agent)
            elif action == "office_status":
                result = bridge_client.request(cfg, "POST", "/office/status", {})
            elif action == "office_open":
                result = bridge_client.open_office(
                    _required(self.args, "path"),
                    str(self.args.get("app") or ""),
                    self.agent,
                )
            else:
                return Response(
                    message=(
                        f"Unknown windows_host_bridge action '{action}'. Supported: status, list, stat, exists, read, "
                        "write, mkdir, delete, run, import, export, open, office_status, office_open."
                    ),
                    break_loop=False,
                )
        except Exception as exc:
            return Response(message=f"Windows host bridge error: {exc}", break_loop=False)

        return Response(message=_format_result(action, result, cfg["max_response_chars"]), break_loop=False)


def _required(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _format_result(action: str, result: dict[str, Any], max_chars: int) -> str:
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"
    status = "ok" if result.get("ok") else "error"
    return f"windows_host_bridge {action} {status}\n{text}"
