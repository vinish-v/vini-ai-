import json
import os
import urllib.error
import urllib.request
from typing import Any

from helpers.tool import Tool, Response
from helpers import plugins


class WindowsHostBridge(Tool):
    async def execute(self, **kwargs) -> Response:
        action = str(self.args.get("action") or kwargs.get("action") or "status").strip().lower()
        cfg = _get_config(self.agent)

        if not cfg["enabled"]:
            return Response(message="Windows host bridge is disabled in plugin settings.", break_loop=False)

        try:
            if action == "status":
                result = _request(cfg, "GET", "/health")
            elif action == "list":
                result = _request(cfg, "POST", "/file/list", {"path": _required(self.args, "path")})
            elif action == "read":
                result = _request(cfg, "POST", "/file/read", {"path": _required(self.args, "path")})
            elif action == "write":
                result = _request(
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
                result = _request(
                    cfg,
                    "POST",
                    "/file/mkdir",
                    {"path": _required(self.args, "path"), "recursive": self.args.get("recursive", True)},
                )
            elif action == "delete":
                result = _request(
                    cfg,
                    "POST",
                    "/file/delete",
                    {"path": _required(self.args, "path"), "recursive": self.args.get("recursive", False)},
                )
            elif action == "run":
                result = _request(
                    cfg,
                    "POST",
                    "/command/run",
                    {
                        "command": _required(self.args, "command"),
                        "cwd": self.args.get("cwd"),
                        "timeoutMs": int(self.args.get("timeout_ms", 30000)),
                    },
                )
            else:
                return Response(
                    message=f"Unknown windows_host_bridge action '{action}'. Supported: status, list, read, write, mkdir, delete, run.",
                    break_loop=False,
                )
        except Exception as exc:
            return Response(message=f"Windows host bridge error: {exc}", break_loop=False)

        return Response(message=_format_result(action, result, cfg["max_response_chars"]), break_loop=False)


def _get_config(agent) -> dict[str, Any]:
    raw = plugins.get_plugin_config("_windows_host_bridge", agent=agent) or {}
    bridge_url = str(raw.get("bridge_url") or os.getenv("VINI_HOST_BRIDGE_URL") or "").strip()
    token = os.getenv("VINI_HOST_BRIDGE_TOKEN", "").strip()
    return {
        "enabled": bool(raw.get("enabled", True)),
        "bridge_url": bridge_url.rstrip("/"),
        "token": token,
        "timeout": int(raw.get("request_timeout_seconds", 120)),
        "max_response_chars": int(raw.get("max_response_chars", 12000)),
    }


def _required(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _request(cfg: dict[str, Any], method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not cfg["bridge_url"]:
        raise RuntimeError("VINI_HOST_BRIDGE_URL is not configured. Start Vini AI from the desktop app to attach the Windows host bridge.")
    if not cfg["token"]:
        raise RuntimeError("VINI_HOST_BRIDGE_TOKEN is not configured. Restart the runtime from the Vini AI desktop app.")

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{cfg['bridge_url']}{path}",
        data=data,
        method=method,
        headers={
            "content-type": "application/json",
            "x-vini-host-bridge-token": cfg["token"],
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=cfg["timeout"]) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach Windows host bridge at {cfg['bridge_url']}: {exc.reason}") from exc

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected bridge response: {raw[:500]}")
    return parsed


def _format_result(action: str, result: dict[str, Any], max_chars: int) -> str:
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"
    status = "ok" if result.get("ok") else "error"
    return f"windows_host_bridge {action} {status}\n{text}"
