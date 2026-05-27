from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from helpers import files, plugins, settings
from plugins._connectors.helpers import action_adapters


AUTH_BY_UI_TYPE = {
    "api-key": "api_key",
    "built-in": "built_in",
    "mcp": "mcp",
    "oauth": "oauth",
    "plugin": "plugin",
}

READ_ACTIONS = {"status", "search", "read", "browser_action", "scrape", "crawl", "map", "batch_scrape", "interact"}
RISKY_ACTIONS = {"create", "update", "send", "delete"}
ALL_ACTIONS = [
    "status",
    "search",
    "read",
    "create",
    "update",
    "send",
    "delete",
    "browser_action",
    "scrape",
    "crawl",
    "map",
    "batch_scrape",
    "interact",
]

GOOGLE_WORKSPACE_CONNECTORS = {"gmail", "google-drive", "google-calendar"}
GOOGLE_WORKSPACE_MCP_NAMES = {"google-workspace", "google_workspace", "workspace-mcp", "workspace_mcp"}


@dataclass(frozen=True)
class ConnectorManifest:
    id: str
    name: str
    type: str
    auth: str
    description: str = ""
    auth_url: str = ""
    plugin_name: str = ""
    surface_id: str = ""
    env_keys: tuple[str, ...] = ()
    key_mode: str = "any"
    requirements: tuple[str, ...] = ()
    prompts: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    def output(self) -> dict[str, Any]:
        data = asdict(self)
        data["env_keys"] = list(self.env_keys)
        data["requirements"] = list(self.requirements)
        data["prompts"] = list(self.prompts)
        data["actions"] = list(self.actions)
        return data


def list_connectors() -> list[ConnectorManifest]:
    return _load_manifests()


def get_connector(connector_id: str) -> ConnectorManifest | None:
    normalized = _normalize_id(connector_id)
    for manifest in _load_manifests():
        if manifest.id == normalized:
            return manifest
    return None


def status(connector_id: str | None = None) -> dict[str, Any]:
    manifests = _load_manifests()
    if connector_id:
        manifest = get_connector(connector_id)
        if not manifest:
            return {
                "ok": False,
                "error": f"Unknown connector '{connector_id}'.",
                "available_connectors": [item.id for item in manifests],
            }
        return {"ok": True, "connector": _status_for(manifest)}

    return {
        "ok": True,
        "connectors": [_status_for(manifest) for manifest in manifests],
        "count": len(manifests),
    }


def search(query: str = "", connector_type: str = "", auth: str = "") -> dict[str, Any]:
    needle = str(query or "").strip().lower()
    wanted_type = str(connector_type or "").strip().lower()
    wanted_auth = str(auth or "").strip().lower()
    results = []
    for manifest in _load_manifests():
        if wanted_type and manifest.type != wanted_type:
            continue
        if wanted_auth and manifest.auth != wanted_auth:
            continue
        haystack = " ".join(
            [
                manifest.id,
                manifest.name,
                manifest.type,
                manifest.auth,
                manifest.description,
                " ".join(manifest.env_keys),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        results.append(_status_for(manifest))
    return {"ok": True, "connectors": results, "count": len(results)}


def run_action(
    action: str,
    connector_id: str,
    payload: dict[str, Any] | None = None,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    payload = payload if isinstance(payload, dict) else {}
    manifest = get_connector(connector_id)
    if not manifest:
        return {"ok": False, "status": "not_configured", "message": f"Unknown connector '{connector_id}'."}

    current = _status_for(manifest)
    if normalized_action not in ALL_ACTIONS:
        return _unsupported(manifest, normalized_action, f"Unknown connector action '{normalized_action}'.")

    if normalized_action == "status":
        return {"ok": True, "action": normalized_action, "connector": current}

    if normalized_action == "browser_action":
        return _browser_action(manifest, payload)

    if manifest.auth == "oauth":
        if normalized_action in RISKY_ACTIONS and not confirmed:
            return _confirmation_required(manifest, normalized_action, payload, current)
        return _browser_action_required(manifest, normalized_action, payload)

    if current["status"] in {"not_configured", "expired"}:
        return {
            "ok": False,
            "status": current["status"],
            "label": current["label"],
            "connector": current,
            "action": normalized_action,
            "message": current["message"],
        }

    if normalized_action in RISKY_ACTIONS and not confirmed:
        return _confirmation_required(manifest, normalized_action, payload, current)

    adapter_result = _run_adapter(manifest, normalized_action, payload)
    if adapter_result is not None:
        return adapter_result

    if manifest.auth == "mcp":
        return {
            "ok": False,
            "status": "unsupported_action",
            "label": "MCP tool routing needed",
            "connector": current,
            "action": normalized_action,
            "message": (
                f"{manifest.name} is configured as an MCP connector. Use the discovered MCP tools directly; "
                "this universal connector router only validates the MCP setup."
            ),
        }

    if manifest.auth == "built_in" and normalized_action in READ_ACTIONS:
        return _browser_action(manifest, payload)

    return _unsupported(
        manifest,
        normalized_action,
        (
            f"{manifest.name} has no real {normalized_action} adapter implemented yet. "
            "Configure an official API/MCP/plugin adapter or use connector_browser_action when a browser fallback is acceptable."
        ),
        connector=current,
    )


async def run_action_async(
    action: str,
    connector_id: str,
    payload: dict[str, Any] | None = None,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    payload = payload if isinstance(payload, dict) else {}
    manifest = get_connector(connector_id)
    if manifest and manifest.id in GOOGLE_WORKSPACE_CONNECTORS:
        current = _status_for(manifest)
        if current["status"] in {"configured", "verified"}:
            if normalized_action in RISKY_ACTIONS and not confirmed:
                return _confirmation_required(manifest, normalized_action, payload, current)
            return await _run_mcp_action(manifest, normalized_action, payload, current)
        return run_action(normalized_action, connector_id, payload, confirmed=confirmed)
    if not manifest or manifest.auth != "mcp":
        return run_action(normalized_action, connector_id, payload, confirmed=confirmed)

    current = _status_for(manifest)
    if current["status"] in {"not_configured", "expired"}:
        return {
            "ok": False,
            "status": current["status"],
            "label": current["label"],
            "connector": current,
            "action": normalized_action,
            "message": current["message"],
        }
    if normalized_action in RISKY_ACTIONS and not confirmed:
        return _confirmation_required(manifest, normalized_action, payload, current)
    return await _run_mcp_action(manifest, normalized_action, payload, current)


def _status_for(manifest: ConnectorManifest) -> dict[str, Any]:
    if manifest.auth == "built_in":
        return _built_in_status(manifest)
    if manifest.auth == "api_key":
        return _api_key_status(manifest)
    if manifest.auth == "plugin":
        return _plugin_status(manifest)
    if manifest.auth == "mcp":
        return _mcp_status(manifest)
    if manifest.auth == "oauth":
        return _oauth_status(manifest)
    return _base_status(
        manifest,
        "unsupported_action",
        "Unsupported connector",
        f"{manifest.name} has an unknown auth mode: {manifest.auth}.",
    )


def _built_in_status(manifest: ConnectorManifest) -> dict[str, Any]:
    try:
        from plugins._browser.helpers.playwright import get_playwright_binary

        binary = get_playwright_binary()
        if not binary:
            raise RuntimeError("Playwright browser binary was not found.")
        return _base_status(
            manifest,
            "verified",
            "Ready for agent",
            f"{manifest.name} can use the built-in browser runtime.",
            verified=True,
            details={"browser_binary": str(binary)},
        )
    except Exception as exc:
        return _base_status(
            manifest,
            "not_configured",
            "Browser runtime unavailable",
            f"{manifest.name} cannot use the browser runtime yet: {exc}",
        )


def _api_key_status(manifest: ConnectorManifest) -> dict[str, Any]:
    found, missing = _configured_env_keys(manifest)
    adapter_actions = action_adapters.supported_actions(manifest.id)
    extra_details: dict[str, Any] = {}
    if manifest.id == "firecrawl":
        env = _combined_env()
        base_url = str(env.get("FIRECRAWL_API_URL") or env.get("FIRECRAWL_BASE_URL") or "https://api.firecrawl.dev/v2")
        extra_details = {
            "api_base": base_url.rstrip("/"),
            "hosted_api_configured": "api.firecrawl.dev" in base_url,
            "self_host_url_configured": bool(base_url and "api.firecrawl.dev" not in base_url),
            "api_version": "v2",
            "provider_states": [
                "not_configured",
                "configured_unverified",
                "auth_failed_or_forbidden",
                "quota_exhausted",
                "rate_limited",
                "endpoint_not_found",
                "provider_unavailable",
            ],
        }
    if missing:
        return _base_status(
            manifest,
            "not_configured",
            "Needs API key",
            f"{manifest.name} needs {', '.join(missing)} in Vini AI secrets, variables, or process environment.",
            details={"found_keys": found, "missing_keys": missing, "adapter_actions": adapter_actions, **extra_details},
        )
    return _base_status(
        manifest,
        "configured",
        "Credentials saved, not verified",
        (
            f"{manifest.name} credentials exist. Agent actions can use a service-specific adapter when available, "
            "or an explicit official API URL through the generic HTTP adapter."
        ),
        details={"found_keys": found, "adapter_actions": adapter_actions, "generic_http": True, **extra_details},
    )


def _oauth_status(manifest: ConnectorManifest) -> dict[str, Any]:
    if manifest.id in GOOGLE_WORKSPACE_CONNECTORS:
        workspace_status = _google_workspace_mcp_status(manifest)
        if workspace_status:
            return workspace_status
    return _base_status(
        manifest,
        "unsupported_action",
        "Browser session only",
        (
            f"{manifest.name} does not have durable OAuth token storage and refresh implemented yet. "
            "Vini can open the real site in the browser as a fallback, but API actions are not connected."
        ),
        details={"auth_url": manifest.auth_url, "browser_fallback_available": bool(manifest.auth_url)},
    )


def _google_workspace_mcp_status(manifest: ConnectorManifest) -> dict[str, Any] | None:
    mcp = _load_mcp_servers()
    servers = mcp.get("mcpServers") if isinstance(mcp, dict) else {}
    if not isinstance(servers, dict) or not any(_google_workspace_name_matches(str(name)) for name in servers.keys()):
        return None

    runtime = _mcp_runtime_snapshot()
    runtime_matches = [
        server
        for server in runtime.get("servers", [])
        if _google_workspace_name_matches(str(server.get("name") or ""))
    ]
    matched_names = sorted(
        set(
            [str(name) for name in servers.keys() if _google_workspace_name_matches(str(name))]
            + [str(item.get("name")) for item in runtime_matches if item.get("name")]
        )
    )
    tools = _mcp_tools_for_names(matched_names, runtime.get("tools", []))
    service_tools = _filter_google_workspace_tools(manifest.id, tools)
    credential_users = _google_workspace_credential_users(servers)
    errors = [item for item in runtime_matches if item.get("error")]
    if service_tools:
        if not credential_users:
            return _base_status(
                manifest,
                "configured",
                "OAuth sign-in needed",
                (
                    f"{manifest.name} MCP tools are available, but no Google account OAuth token is stored yet. "
                    "Run a Google Workspace tool with user_google_email and complete the Google consent flow."
                ),
                details={
                    "mcp_preset": "google-workspace",
                    "matching_servers": matched_names,
                    "mcp_tools": service_tools,
                    "google_credentials": {"stored_users": [], "count": 0},
                    **runtime,
                },
            )
        return _base_status(
            manifest,
            "verified",
            "Ready for agent",
            f"{manifest.name} is ready through the Google Workspace MCP server with {len(service_tools)} matching tool(s) and stored Google OAuth credentials.",
            verified=True,
            details={
                "mcp_preset": "google-workspace",
                "matching_servers": matched_names,
                "mcp_tools": service_tools,
                "google_credentials": {"stored_users": credential_users, "count": len(credential_users)},
                **runtime,
            },
        )
    if errors:
        return _base_status(
            manifest,
            "expired",
            "MCP server error",
            f"Google Workspace MCP is configured but failed tool discovery: {errors[0].get('error')}",
            details={"mcp_preset": "google-workspace", "matching_servers": matched_names, "mcp_errors": errors, **runtime},
        )
    return _base_status(
        manifest,
        "configured",
        "Credentials saved, not verified",
        f"Google Workspace MCP is declared for {manifest.name}, but no matching tools have been discovered yet.",
        details={"mcp_preset": "google-workspace", "matching_servers": matched_names, **runtime},
    )


def _plugin_status(manifest: ConnectorManifest) -> dict[str, Any]:
    plugin_name = manifest.plugin_name
    if not plugin_name or not plugins.find_plugin_dir(plugin_name):
        return _base_status(
            manifest,
            "not_configured",
            "Plugin setup needed",
            f"{manifest.name} needs plugin {plugin_name or '(missing plugin name)'} to be installed.",
        )
    if plugins.get_toggle_state(plugin_name) != "enabled":
        return _base_status(
            manifest,
            "not_configured",
            "Plugin setup needed",
            f"{manifest.name} plugin {plugin_name} is installed but disabled.",
        )

    if plugin_name == "_email_integration":
        configured = _email_configured(plugin_name)
    elif plugin_name == "_telegram_integration":
        configured = _telegram_configured(plugin_name)
    elif plugin_name == "_whatsapp_integration":
        configured = _whatsapp_configured(plugin_name)
    elif plugin_name == "_oauth" and manifest.id == "codex":
        return _codex_status(manifest)
    else:
        configured = _has_meaningful_config(plugins.get_plugin_config(plugin_name))

    if configured:
        return _base_status(
            manifest,
            "configured",
            "Credentials saved, not verified",
            f"{manifest.name} plugin has configuration. Use the plugin's own test/status flow before external actions.",
            details={"adapter_actions": action_adapters.supported_actions(manifest.id)},
        )
    return _base_status(
        manifest,
        "not_configured",
        "Plugin setup needed",
        f"{manifest.name} plugin is available, but no usable configuration was found.",
    )


def _codex_status(manifest: ConnectorManifest) -> dict[str, Any]:
    try:
        from plugins._oauth.helpers import codex

        info = codex.status()
        if info.get("connected"):
            return _base_status(
                manifest,
                "verified",
                "Ready for agent",
                "Codex/ChatGPT account auth exists and can be used by the OAuth plugin.",
                verified=True,
                details={k: v for k, v in info.items() if k not in {"access_token", "refresh_token", "id_token"}},
            )
        return _base_status(
            manifest,
            "not_configured",
            "Plugin setup needed",
            info.get("message") or "Codex/ChatGPT auth file was not found or is not usable.",
            details={"auth_file_path": info.get("auth_file_path"), "discovered_auth_files": info.get("discovered_auth_files", [])},
        )
    except Exception as exc:
        return _base_status(
            manifest,
            "not_configured",
            "Plugin setup needed",
            f"Could not inspect Codex/ChatGPT OAuth status: {exc}",
        )


def _mcp_status(manifest: ConnectorManifest) -> dict[str, Any]:
    mcp = _load_mcp_servers()
    servers = mcp.get("mcpServers") if isinstance(mcp, dict) else {}
    if not isinstance(servers, dict) or not servers:
        return _base_status(
            manifest,
            "not_configured",
            "Needs MCP server",
            f"{manifest.name} needs an MCP server entry in Vini AI MCP settings.",
        )

    runtime = _mcp_runtime_snapshot()
    configured_matches = _matching_mcp_names(manifest, servers.keys())
    runtime_matches = [
        server
        for server in runtime.get("servers", [])
        if _mcp_name_matches(manifest, str(server.get("name") or ""))
    ]
    matched_names = sorted(set(configured_matches + [str(item.get("name")) for item in runtime_matches if item.get("name")]))

    if not matched_names:
        return _base_status(
            manifest,
            "not_configured",
            "Needs MCP server",
            f"MCP is configured, but no server name matches {manifest.name}.",
            details={"configured_servers": sorted(servers.keys()), **runtime},
        )

    tools = _mcp_tools_for_names(matched_names, runtime.get("tools", []))
    errors = [item for item in runtime_matches if item.get("error")]
    if tools:
        return _base_status(
            manifest,
            "verified",
            "Ready for agent",
            f"{manifest.name} MCP server is configured and {len(tools)} tool(s) are discovered.",
            verified=True,
            details={"matching_servers": matched_names, "mcp_tools": tools, **runtime},
        )
    if errors:
        return _base_status(
            manifest,
            "expired",
            "MCP server error",
            f"{manifest.name} MCP server is configured but failed tool discovery: {errors[0].get('error')}",
            details={"matching_servers": matched_names, "mcp_errors": errors, **runtime},
        )
    return _base_status(
        manifest,
        "configured",
        "Credentials saved, not verified",
        f"{manifest.name} MCP server is declared, but no tools have been discovered yet.",
        details={"matching_servers": matched_names, **runtime},
    )


def _browser_action(manifest: ConnectorManifest, payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or manifest.auth_url or "").strip()
    if not url:
        url = _default_url(manifest)
    if not url:
        return _unsupported(manifest, "browser_action", f"{manifest.name} has no browser URL configured.")
    return {
        "ok": True,
        "status": "browser_session_only" if manifest.auth == "oauth" else "verified",
        "label": "Browser session only" if manifest.auth == "oauth" else "Ready for agent",
        "connector": _status_for(manifest),
        "action": "browser_action",
        "browser_action": payload.get("browser_action") or "open",
        "url": url,
        "message": (
            f"Use the real browser runtime for {manifest.name}. "
            "For OAuth connectors this is a browser-session fallback, not durable API access."
        ),
    }


def _browser_action_required(
    manifest: ConnectorManifest,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    browser = _browser_action(manifest, payload)
    return {
        "ok": False,
        "status": "browser_action_required",
        "label": "Browser session only",
        "connector": _status_for(manifest),
        "action": action,
        "browser_fallback": {
            "tool_name": "connector_browser_action",
            "tool_args": {
                "connector_id": manifest.id,
                "url": browser.get("url"),
                "browser_action": "open",
            },
        },
        "message": (
            f"{manifest.name} has no durable OAuth API adapter for {action}. "
            "Use the browser fallback, then continue visibly in Vini AI Computer."
        ),
        "no_api_changes_made": True,
    }


def _base_status(
    manifest: ConnectorManifest,
    status_value: str,
    label: str,
    message: str,
    *,
    verified: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **manifest.output(),
        "status": status_value,
        "label": label,
        "message": message,
        "verified": verified,
        "ready_for_agent": status_value == "verified",
        "details": details or {},
    }


def _unsupported(
    manifest: ConnectorManifest,
    action: str,
    message: str,
    *,
    connector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "unsupported_action",
        "label": "Unsupported action",
        "connector": connector or _status_for(manifest),
        "action": action,
        "message": message,
        "no_changes_made": True,
    }


def _confirmation_required(
    manifest: ConnectorManifest,
    action: str,
    payload: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "confirmation_required",
        "label": "Confirmation required",
        "connector": current,
        "action": action,
        "preview": _preview(manifest, action, payload),
        "message": (
            f"{manifest.name} {action} is a risky external action. "
            "No changes were made. Ask the user to confirm the preview, then retry with confirmed=true."
        ),
        "no_changes_made": True,
    }


def _run_adapter(
    manifest: ConnectorManifest,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    plugin_config = None
    if manifest.plugin_name:
        try:
            plugin_config = plugins.get_plugin_config(manifest.plugin_name)
        except Exception:
            plugin_config = None
    try:
        result = action_adapters.run(
            manifest,
            action,
            payload,
            _combined_env(),
            plugin_config=plugin_config if isinstance(plugin_config, dict) else None,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "request_failed",
            "label": "Request failed",
            "connector": _status_for(manifest),
            "action": action,
            "message": str(exc),
            "no_changes_made": action in RISKY_ACTIONS,
        }
    if result is None:
        return None
    result.setdefault("connector", _status_for(manifest))
    if action in RISKY_ACTIONS:
        result.setdefault("no_changes_made", False)
    return result


async def _run_mcp_action(
    manifest: ConnectorManifest,
    action: str,
    payload: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    tool_name = str(
        payload.get("tool_name")
        or payload.get("mcp_tool")
        or payload.get("tool")
        or ""
    ).strip()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    if not args and isinstance(payload.get("tool_args"), dict):
        args = payload["tool_args"]
    if not tool_name:
        tools = current.get("details", {}).get("mcp_tools", [])
        return {
            "ok": False,
            "status": "mcp_tool_required",
            "label": "MCP tool required",
            "connector": current,
            "action": action,
            "message": (
                f"{manifest.name} is ready through MCP. Choose one discovered MCP tool and retry with "
                "payload.tool_name plus payload.args."
            ),
            "available_tools": tools,
            "no_changes_made": True,
        }
    full_tool_name = _resolve_mcp_tool_name(manifest, tool_name)
    if not full_tool_name:
        return {
            "ok": False,
            "status": "mcp_tool_not_found",
            "label": "MCP tool not found",
            "connector": current,
            "action": action,
            "message": f"MCP tool '{tool_name}' was not found for {manifest.name}.",
            "available_tools": current.get("details", {}).get("mcp_tools", []),
            "no_changes_made": True,
        }
    try:
        from helpers.mcp_handler import MCPConfig

        response = await MCPConfig.get_instance().call_tool(full_tool_name, args)
        text_parts = [
            getattr(item, "text", "")
            for item in getattr(response, "content", [])
            if getattr(item, "type", "") == "text"
        ]
        message = "\n\n".join(part for part in text_parts if part)
        is_error = bool(getattr(response, "isError", False))
        return {
            "ok": not is_error,
            "status": "request_failed" if is_error else "executed",
            "label": "Request failed" if is_error else "Executed",
            "connector": current,
            "action": action,
            "mcp_tool_name": full_tool_name,
            "data": message or "[MCP tool returned no textual content]",
            "no_changes_made": action in RISKY_ACTIONS and is_error,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "request_failed",
            "label": "Request failed",
            "connector": current,
            "action": action,
            "mcp_tool_name": full_tool_name,
            "message": str(exc),
            "no_changes_made": action in RISKY_ACTIONS,
        }


def _preview(manifest: ConnectorManifest, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("token", "secret", "password", "key")):
            redacted[key] = "***"
        else:
            redacted[key] = value
    return {
        "connector_id": manifest.id,
        "connector_name": manifest.name,
        "action": action,
        "payload": redacted,
    }


def _configured_env_keys(manifest: ConnectorManifest) -> tuple[list[str], list[str]]:
    env = _combined_env()
    required = list(manifest.env_keys)
    if not required:
        return [], []
    found = [key for key in required if env.get(key)]
    if manifest.key_mode == "all":
        missing = [key for key in required if key not in found]
    else:
        missing = [] if found else required
    return found, missing


def _combined_env() -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if value}
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


def _load_mcp_servers() -> dict[str, Any]:
    try:
        raw = settings.get_settings().get("mcp_servers") or "{}"
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _mcp_runtime_snapshot() -> dict[str, Any]:
    try:
        from helpers.mcp_handler import MCPConfig

        mcp_config = MCPConfig.get_instance()
        if not mcp_config.is_initialized():
            raw = settings.get_settings().get("mcp_servers") or "{}"
            MCPConfig.update(str(raw))
            mcp_config = MCPConfig.get_instance()
        servers = mcp_config.get_servers_status()
        tools = []
        for item in mcp_config.get_tools():
            if isinstance(item, dict):
                for full_name, tool in item.items():
                    if isinstance(tool, dict):
                        tools.append(
                            {
                                "name": full_name,
                                "server": tool.get("server"),
                                "tool": tool.get("name"),
                                "description": tool.get("description"),
                                "input_schema": tool.get("input_schema"),
                            }
                        )
        return {"mcp_initialized": mcp_config.is_initialized(), "servers": servers, "tools": tools}
    except Exception as exc:
        return {"mcp_initialized": False, "servers": [], "tools": [], "mcp_error": str(exc)}


def _matching_mcp_names(manifest: ConnectorManifest, names: Any) -> list[str]:
    return [str(name) for name in names if _mcp_name_matches(manifest, str(name))]


def _mcp_name_matches(manifest: ConnectorManifest, name: str) -> bool:
    normalized = name.strip().lower().replace("_", "-")
    if manifest.id in GOOGLE_WORKSPACE_CONNECTORS:
        return _google_workspace_name_matches(name)
    return manifest.id in normalized or manifest.name.strip().lower().replace(" ", "-") in normalized


def _google_workspace_name_matches(name: str) -> bool:
    normalized = name.strip().lower().replace("_", "-")
    return normalized in GOOGLE_WORKSPACE_MCP_NAMES or "google-workspace" in normalized or "workspace-mcp" in normalized


def _mcp_tools_for_names(names: list[str], tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = {name.strip().lower().replace("_", "-") for name in names}
    result = []
    for tool in tools:
        server = str(tool.get("server") or "").strip().lower().replace("_", "-")
        if server in wanted:
            result.append(tool)
            continue
        full = str(tool.get("name") or "").strip().lower().replace("_", "-")
        if any(full.startswith(f"{name}.") for name in wanted):
            result.append(tool)
    return result


def _filter_google_workspace_tools(connector_id: str, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prefixes = {
        "gmail": ("gmail",),
        "google-drive": ("drive", "gdrive"),
        "google-calendar": ("calendar", "gcalendar"),
    }.get(connector_id, ())
    if not prefixes:
        return tools
    result = []
    for tool in tools:
        short = str(tool.get("tool") or "").strip().lower()
        full = str(tool.get("name") or "").strip().lower()
        description = str(tool.get("description") or "").strip().lower()
        if short == "start_google_auth" or full.endswith(".start_google_auth"):
            result.append(tool)
            continue
        if any(
            short.startswith(prefix)
            or f".{prefix}" in full
            or prefix in description[:160]
            for prefix in prefixes
        ):
            result.append(tool)
    return result


def _google_workspace_credential_users(servers: dict[str, Any]) -> list[str]:
    credential_dirs = []
    for name, config in servers.items():
        if not _google_workspace_name_matches(str(name)) or not isinstance(config, dict):
            continue
        env = config.get("env") if isinstance(config.get("env"), dict) else {}
        if env.get("WORKSPACE_MCP_CREDENTIALS_DIR"):
            credential_dirs.append(str(env["WORKSPACE_MCP_CREDENTIALS_DIR"]))
        if env.get("GOOGLE_MCP_CREDENTIALS_DIR"):
            credential_dirs.append(str(env["GOOGLE_MCP_CREDENTIALS_DIR"]))
    credential_dirs.append("/a0/usr/google_workspace_mcp/credentials")

    users: set[str] = set()
    for raw_dir in credential_dirs:
        try:
            directory = Path(raw_dir).expanduser()
            if not directory.exists() or not directory.is_dir():
                continue
            for item in directory.glob("*.json"):
                user = item.stem
                if user in {"oauth_states"} or "@" not in user:
                    continue
                users.add(user)
        except Exception:
            continue
    return sorted(users)


def _resolve_mcp_tool_name(manifest: ConnectorManifest, tool_name: str) -> str:
    runtime = _mcp_runtime_snapshot()
    tools = _mcp_tools_for_names(
        _matching_mcp_names(manifest, [server.get("name") for server in runtime.get("servers", [])]),
        runtime.get("tools", []),
    )
    requested = tool_name.strip()
    requested_norm = requested.lower()
    for tool in tools:
        full = str(tool.get("name") or "")
        short = str(tool.get("tool") or "")
        if requested == full or requested == short or requested_norm == full.lower() or requested_norm == short.lower():
            return full
    if "." in requested:
        return requested
    return ""


def _email_configured(plugin_name: str) -> bool:
    config = plugins.get_plugin_config(plugin_name)
    handlers = config.get("handlers") if isinstance(config, dict) else []
    if not isinstance(handlers, list):
        return False
    for handler in handlers:
        if not isinstance(handler, dict) or handler.get("enabled") is False:
            continue
        if handler.get("username") and handler.get("password") and (
            handler.get("smtp_server") or handler.get("imap_server")
        ):
            return True
    return False


def _telegram_configured(plugin_name: str) -> bool:
    config = plugins.get_plugin_config(plugin_name)
    bots = config.get("bots") if isinstance(config, dict) else []
    if not isinstance(bots, list):
        return False
    return any(isinstance(bot, dict) and bot.get("enabled") is not False and bot.get("token") for bot in bots)


def _whatsapp_configured(plugin_name: str) -> bool:
    config = plugins.get_plugin_config(plugin_name)
    return isinstance(config, dict) and bool(config.get("enabled"))


def _has_meaningful_config(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_meaningful_config(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_config(item) for item in value)
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return bool(str(value).strip())


def _default_url(manifest: ConnectorManifest) -> str:
    if manifest.id in {"my-browser", "playwright"}:
        return "about:blank"
    return manifest.auth_url


def _load_manifests() -> list[ConnectorManifest]:
    objects = _load_catalog_objects()
    manifests = []
    for item in objects:
        connector_id = _normalize_id(item.get("id"))
        name = str(item.get("name") or connector_id).strip()
        ui_type = str(item.get("type") or "").strip()
        auth = AUTH_BY_UI_TYPE.get(ui_type, ui_type.replace("-", "_"))
        actions = _actions_for(auth)
        manifests.append(
            ConnectorManifest(
                id=connector_id,
                name=name,
                type=ui_type,
                auth=auth,
                description=str(item.get("description") or "").strip(),
                auth_url=str(item.get("authUrl") or "").strip(),
                plugin_name=str(item.get("pluginName") or "").strip(),
                surface_id=str(item.get("surfaceId") or "").strip(),
                env_keys=tuple(str(key).strip() for key in item.get("envKeys", []) if str(key).strip()),
                key_mode=str(item.get("keyMode") or "any").strip(),
                requirements=tuple(str(req).strip() for req in item.get("requirements", []) if str(req).strip()),
                prompts=tuple(str(prompt).strip() for prompt in item.get("prompts", []) if str(prompt).strip()),
                actions=tuple(actions),
            )
        )
    return manifests


def _actions_for(auth: str) -> list[str]:
    return ALL_ACTIONS.copy()


def _load_catalog_objects() -> list[dict[str, Any]]:
    source = Path(files.get_abs_path("webui", "components", "connectors", "connectors-store.js"))
    text = source.read_text(encoding="utf-8")
    array_source = _extract_connectors_array(text)
    objects = []
    for object_source in _iter_object_sources(array_source):
        parsed = _parse_object_source(object_source)
        if parsed.get("id"):
            objects.append(parsed)
    return objects


def _extract_connectors_array(text: str) -> str:
    marker = "const CONNECTORS = ["
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("CONNECTORS catalog was not found in connectors-store.js.")
    start += len(marker)
    depth = 1
    index = start
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return text[start:index]
        index += 1
    raise RuntimeError("CONNECTORS catalog array is not closed.")


def _iter_object_sources(array_source: str) -> list[str]:
    objects = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(array_source):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(array_source[start : index + 1])
    return objects


def _parse_object_source(source: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in ("id", "name", "type", "description", "authUrl", "pluginName", "surfaceId", "keyMode"):
        value = _string_field(source, field)
        if value is not None:
            result[field] = value
    for field in ("envKeys", "requirements", "prompts"):
        result[field] = _array_field(source, field)
    return result


def _string_field(source: str, field: str) -> str | None:
    match = re.search(rf"\b{re.escape(field)}\s*:\s*(\"(?:\\.|[^\"\\])*\")", source)
    if not match:
        return None
    try:
        return str(json.loads(match.group(1)))
    except Exception:
        return match.group(1).strip('"')


def _array_field(source: str, field: str) -> list[str]:
    match = re.search(rf"\b{re.escape(field)}\s*:\s*\[([^\]]*)\]", source, re.DOTALL)
    if not match:
        return []
    values = []
    for raw in re.findall(r"\"(?:\\.|[^\"\\])*\"", match.group(1)):
        try:
            values.append(str(json.loads(raw)))
        except Exception:
            values.append(raw.strip('"'))
    return values


def _normalize_id(value: Any) -> str:
    return str(value or "").strip().lower()
