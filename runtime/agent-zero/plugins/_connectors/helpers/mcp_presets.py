from __future__ import annotations

import json
import time
from copy import deepcopy
from shutil import which
from typing import Any

from helpers import settings
from helpers.mcp_handler import MCPConfig
from plugins._connectors.helpers import registry


PRESETS: dict[str, dict[str, Any]] = {
    "context7": {
        "server_name": "context7",
        "required_commands": ["npx"],
        "install_message": "Install Node.js/npm in the Vini AI runtime so the npx command is available.",
        "config": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],
            "init_timeout": 30,
            "tool_timeout": 120,
        },
    },
    "serena": {
        "server_name": "serena",
        "required_commands": ["serena"],
        "install_message": "Install Serena in the Vini AI runtime with: uv tool install -p 3.13 serena-agent@latest --prerelease=allow",
        "config": {
            "type": "stdio",
            "command": "serena",
            "args": ["start-mcp-server", "--project-from-cwd", "--context=codex", "--open-web-dashboard", "False"],
            "init_timeout": 30,
            "tool_timeout": 120,
        },
    },
}


def preset_status(connector_id: str) -> dict[str, Any]:
    manifest = registry.get_connector(connector_id)
    if not manifest or manifest.auth != "mcp":
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"Connector '{connector_id}' is not a preset-backed MCP connector.",
        }
    preset = PRESETS.get(manifest.id)
    if not preset:
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"{manifest.name} has no built-in MCP preset yet. Configure it manually in MCP settings.",
            "connector": _connector_snapshot(
                manifest,
                "unsupported_action",
                "Manual MCP setup needed",
                f"{manifest.name} has no built-in MCP preset yet. Configure it manually in MCP settings.",
            ),
        }
    missing = _missing_commands(preset)
    return {
        "ok": not missing,
        "status": "ready" if not missing else "missing_dependency",
        "connector_id": manifest.id,
        "connector_name": manifest.name,
        "server_name": preset["server_name"],
        "missing_commands": missing,
        "install_message": preset["install_message"] if missing else "",
        "config_preview": _redacted_config(preset["config"]),
        "connector": _connector_snapshot(
            manifest,
            "not_configured" if missing else "configured",
            "Needs MCP dependency" if missing else "MCP preset available",
            (
                f"{manifest.name} preset can be saved after installing: {', '.join(missing)}."
                if missing
                else f"{manifest.name} preset dependencies are available."
            ),
        ),
    }


def enable(connector_id: str, *, force: bool = True) -> dict[str, Any]:
    manifest = registry.get_connector(connector_id)
    if not manifest or manifest.auth != "mcp":
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"Connector '{connector_id}' is not an MCP connector.",
            "no_changes_made": True,
        }

    preset = PRESETS.get(manifest.id)
    if not preset:
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"{manifest.name} does not have a built-in MCP preset. Configure it manually in MCP settings.",
            "connector": _connector_snapshot(
                manifest,
                "unsupported_action",
                "Manual MCP setup needed",
                f"{manifest.name} does not have a built-in MCP preset. Configure it manually in MCP settings.",
            ),
            "no_changes_made": True,
        }

    missing = _missing_commands(preset)
    if missing:
        return {
            "ok": False,
            "status": "missing_dependency",
            "label": "Needs MCP dependency",
            "message": f"{manifest.name} cannot be enabled yet. Missing command(s): {', '.join(missing)}. {preset['install_message']}",
            "missing_commands": missing,
            "install_message": preset["install_message"],
            "connector": _connector_snapshot(
                manifest,
                "not_configured",
                "Needs MCP dependency",
                f"{manifest.name} cannot be enabled yet. Missing command(s): {', '.join(missing)}.",
            ),
            "no_changes_made": True,
        }

    raw_config = _load_raw_mcp_config()
    servers = _mcp_servers_object(raw_config)
    server_name = str(preset["server_name"])
    if server_name in servers and not force:
        return {
            "ok": False,
            "status": "already_configured",
            "label": "Already configured",
            "message": f"{manifest.name} already has an MCP server entry named {server_name}.",
            "connector": registry.status(manifest.id).get("connector"),
            "no_changes_made": True,
        }

    servers[server_name] = deepcopy(preset["config"])
    updated = {"mcpServers": servers}
    _apply_mcp_config(updated)
    connector = registry.status(manifest.id).get("connector")
    return {
        "ok": bool(connector and connector.get("status") in {"configured", "verified"}),
        "status": connector.get("status") if connector else "configured",
        "label": connector.get("label") if connector else "Credentials saved, not verified",
        "message": connector.get("message") if connector else f"{manifest.name} MCP preset was saved.",
        "server_name": server_name,
        "connector": connector,
        "mcp_status": _runtime_status(),
    }


def refresh(connector_id: str | None = None) -> dict[str, Any]:
    raw_config = _load_raw_mcp_config()
    _apply_mcp_config(raw_config)
    if connector_id:
        connector = registry.status(connector_id).get("connector")
        return {
            "ok": True,
            "status": connector.get("status") if connector else "unknown",
            "label": connector.get("label") if connector else "Unknown connector",
            "message": connector.get("message") if connector else f"Connector '{connector_id}' was not found.",
            "connector": connector,
            "mcp_status": _runtime_status(),
        }
    return {"ok": True, "mcp_status": _runtime_status(), **registry.status()}


def _missing_commands(preset: dict[str, Any]) -> list[str]:
    return [command for command in preset.get("required_commands", []) if not which(command)]


def _load_raw_mcp_config() -> dict[str, Any]:
    try:
        raw = settings.get_settings().get("mcp_servers") or "{}"
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {"mcpServers": {}}
    except Exception:
        return {"mcpServers": {}}


def _mcp_servers_object(config: dict[str, Any]) -> dict[str, Any]:
    servers = config.get("mcpServers")
    if isinstance(servers, dict):
        return deepcopy(servers)
    if isinstance(servers, list):
        result: dict[str, Any] = {}
        for item in servers:
            if isinstance(item, dict) and item.get("name"):
                name = str(item["name"])
                result[name] = {key: value for key, value in item.items() if key != "name"}
        return result
    return {}


def _apply_mcp_config(config: dict[str, Any]) -> None:
    config_text = json.dumps(config, indent=2)
    settings.set_settings_delta({"mcp_servers": "[]"})
    settings.set_settings_delta({"mcp_servers": config_text})
    time.sleep(1)
    if not MCPConfig.get_instance().is_initialized():
        MCPConfig.update(config_text)


def _runtime_status() -> list[dict[str, Any]]:
    try:
        return MCPConfig.get_instance().get_servers_status()
    except Exception:
        return []


def _redacted_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(config)
    env = redacted.get("env")
    if isinstance(env, dict):
        for key in list(env.keys()):
            if any(token in key.lower() for token in ("key", "token", "secret", "password")):
                env[key] = "***"
    return redacted


def _connector_snapshot(manifest: Any, status: str, label: str, message: str) -> dict[str, Any]:
    data = manifest.output()
    data.update(
        {
            "status": status,
            "label": label,
            "message": message,
            "verified": status == "verified",
            "ready_for_agent": status == "verified",
            "details": {},
        }
    )
    return data
