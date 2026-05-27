from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from shutil import which
from typing import Any

from helpers import settings
from helpers.mcp_handler import MCPConfig
from plugins._connectors.helpers import registry


PRESETS: dict[str, dict[str, Any]] = {
    "google-workspace": {
        "server_name": "google_workspace",
        "required_commands": ["uvx"],
        "required_env": ["GOOGLE_OAUTH_CLIENT_ID"],
        "optional_env": ["GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI"],
        "install_message": "Install uv/uvx in the Vini AI runtime so workspace-mcp can be launched.",
        "config": {
            "type": "stdio",
            "command": "uvx",
            "args": ["workspace-mcp", "--tools", "gmail", "drive", "calendar", "--tool-tier", "core"],
            "env": {
                "OAUTHLIB_INSECURE_TRANSPORT": "1",
                "WORKSPACE_MCP_CREDENTIALS_DIR": "/a0/usr/google_workspace_mcp/credentials",
            },
            "init_timeout": 45,
            "tool_timeout": 180,
        },
    },
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

PRESET_ALIASES = {
    "gmail": "google-workspace",
    "google-drive": "google-workspace",
    "google-calendar": "google-workspace",
}


def preset_status(connector_id: str) -> dict[str, Any]:
    manifest = registry.get_connector(connector_id)
    preset_id = _preset_id_for(connector_id)
    if not manifest or (manifest.auth != "mcp" and not preset_id):
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"Connector '{connector_id}' is not a preset-backed MCP connector.",
        }
    preset = PRESETS.get(preset_id or manifest.id)
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
    missing_env = _missing_env(preset)
    return {
        "ok": not missing and not missing_env,
        "status": "ready" if not missing and not missing_env else ("missing_dependency" if missing else "missing_configuration"),
        "connector_id": manifest.id,
        "connector_name": manifest.name,
        "server_name": preset["server_name"],
        "missing_commands": missing,
        "missing_env": missing_env,
        "install_message": preset["install_message"] if missing else _env_message(missing_env),
        "config_preview": _redacted_config(_build_config(preset)),
        "connector": _connector_snapshot(
            manifest,
            "not_configured" if missing or missing_env else "configured",
            "Needs MCP dependency" if missing else ("Needs OAuth credentials" if missing_env else "MCP preset available"),
            (
                f"{manifest.name} preset can be saved after installing: {', '.join(missing)}."
                if missing
                else (
                    f"{manifest.name} preset needs {', '.join(missing_env)} in Vini AI secrets or variables."
                    if missing_env
                    else f"{manifest.name} preset dependencies are available."
                )
            ),
        ),
    }


def enable(connector_id: str, *, force: bool = True) -> dict[str, Any]:
    manifest = registry.get_connector(connector_id)
    preset_id = _preset_id_for(connector_id)
    if not manifest or (manifest.auth != "mcp" and not preset_id):
        return {
            "ok": False,
            "status": "unsupported_action",
            "message": f"Connector '{connector_id}' is not an MCP connector.",
            "no_changes_made": True,
        }

    preset = PRESETS.get(preset_id or manifest.id)
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
    missing_env = _missing_env(preset)
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
    if missing_env:
        return {
            "ok": False,
            "status": "missing_configuration",
            "label": "Needs OAuth credentials",
            "message": f"{manifest.name} cannot be enabled yet. Add {', '.join(missing_env)} to Vini AI secrets or variables. {_env_message(missing_env)}",
            "missing_env": missing_env,
            "connector": _connector_snapshot(
                manifest,
                "not_configured",
                "Needs OAuth credentials",
                f"{manifest.name} needs {', '.join(missing_env)} before the Google Workspace MCP server can start.",
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

    servers[server_name] = _build_config(preset)
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


def _missing_env(preset: dict[str, Any]) -> list[str]:
    env = _combined_settings_env()
    return [key for key in preset.get("required_env", []) if not env.get(key)]


def _env_message(missing_env: list[str]) -> str:
    if not missing_env:
        return ""
    return (
        "Create a Google Cloud OAuth client and save the required value in Vini AI settings. "
        "GOOGLE_OAUTH_CLIENT_SECRET is optional for public desktop/PKCE clients but recommended for web clients."
    )


def _build_config(preset: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(preset["config"])
    env = config.get("env") if isinstance(config.get("env"), dict) else {}
    for key in ("PATH", "HOME", "USER", "PYTHONPATH", "UV_CACHE_DIR"):
        if os.environ.get(key) and key not in env:
            env[key] = os.environ[key]
    combined = _combined_settings_env()
    for key in [*preset.get("required_env", []), *preset.get("optional_env", [])]:
        if combined.get(key):
            env[key] = combined[key]
    config["env"] = env
    return config


def _combined_settings_env() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        current = settings.get_settings()
        result.update(_parse_env_text(str(current.get("variables") or "")))
        result.update(_parse_env_text(str(current.get("secrets") or "")))
    except Exception:
        pass
    return result


def _parse_env_text(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            result[key] = value
    return result


def _preset_id_for(connector_id: str) -> str:
    normalized = str(connector_id or "").strip().lower()
    return PRESET_ALIASES.get(normalized, normalized if normalized in PRESETS else "")


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
