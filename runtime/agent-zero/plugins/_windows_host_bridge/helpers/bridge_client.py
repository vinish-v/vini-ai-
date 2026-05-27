from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from helpers import files

OFFICE_EXTENSIONS = {"odt", "ods", "odp", "docx", "xlsx", "pptx", "txt"}
DEFAULT_IMPORT_DIR = Path(files.get_abs_path("usr", "workdir", "host-imports"))
MAX_LOCAL_BYTES = 64 * 1024 * 1024


def config(agent: Any | None = None) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    try:
        from helpers import plugins

        raw = plugins.get_plugin_config("_windows_host_bridge", agent=agent) or {}
    except Exception:
        raw = {}
    bridge_url = str(raw.get("bridge_url") or os.getenv("VINI_HOST_BRIDGE_URL") or "").strip()
    token = os.getenv("VINI_HOST_BRIDGE_TOKEN", "").strip()
    return {
        "enabled": bool(raw.get("enabled", True)),
        "bridge_url": bridge_url.rstrip("/"),
        "token": token,
        "timeout": int(raw.get("request_timeout_seconds", 120)),
        "max_response_chars": int(raw.get("max_response_chars", 12000)),
    }


def request(
    cfg: dict[str, Any],
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not cfg.get("bridge_url"):
        raise RuntimeError("VINI_HOST_BRIDGE_URL is not configured. Start Vini AI from the desktop app to attach the Windows host bridge.")
    if not cfg.get("token"):
        raise RuntimeError("VINI_HOST_BRIDGE_TOKEN is not configured. Restart the runtime from the Vini AI desktop app.")

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['bridge_url']}{path}",
        data=data,
        method=method,
        headers={
            "content-type": "application/json",
            "x-vini-host-bridge-token": str(cfg["token"]),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=int(cfg.get("timeout") or 120)) as response:
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


def status(agent: Any | None = None) -> dict[str, Any]:
    cfg = config(agent)
    if not cfg["enabled"]:
        return {"ok": False, "enabled": False, "error": "Windows host bridge is disabled in plugin settings."}
    health = request(cfg, "GET", "/health")
    office = request(cfg, "POST", "/office/status", {})
    return {
        **health,
        "enabled": True,
        "host_bridge_attached": bool(health.get("ok")),
        "scoped_folder_access": bool(health.get("scopes")),
        "microsoft_office_installed": bool(office.get("microsoft_office_installed")),
        "microsoft_office": office.get("apps") or {},
    }


def list_host(path: str, agent: Any | None = None) -> dict[str, Any]:
    return request(config(agent), "POST", "/file/list", {"path": _required(path, "path")})


def stat_host(path: str, agent: Any | None = None) -> dict[str, Any]:
    return request(config(agent), "POST", "/file/stat", {"path": _required(path, "path")})


def exists_host(path: str, agent: Any | None = None) -> dict[str, Any]:
    return request(config(agent), "POST", "/file/exists", {"path": _required(path, "path")})


def open_host(path: str, agent: Any | None = None) -> dict[str, Any]:
    return request(config(agent), "POST", "/file/open", {"path": _required(path, "path")})


def open_office(path: str, app: str = "", agent: Any | None = None) -> dict[str, Any]:
    return request(config(agent), "POST", "/office/open", {"path": _required(path, "path"), "app": _office_app(path, app)})


def import_host_file(
    host_path: str,
    local_path: str = "",
    *,
    register_office: bool = True,
    open_in_desktop: bool = False,
    context_id: str = "",
    agent: Any | None = None,
) -> dict[str, Any]:
    payload = request(config(agent), "POST", "/file/read-binary", {"path": _required(host_path, "host_path")})
    data = base64.b64decode(str(payload.get("contentBase64") or ""))
    if len(data) > MAX_LOCAL_BYTES:
        raise RuntimeError(f"Imported file exceeds Vini local limit ({len(data)} bytes).")

    target = _import_target(local_path, str(payload.get("name") or Path(host_path).name))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    result: dict[str, Any] = {
        "ok": True,
        "action": "import",
        "host_path": payload.get("path") or host_path,
        "local_path": files.normalize_a0_path(str(target)),
        "size": len(data),
    }
    if register_office and target.suffix.lower().lstrip(".") in OFFICE_EXTENSIONS:
        from plugins._office.helpers import document_store
        from plugins._desktop.helpers import desktop_session

        doc = document_store.register_document(target, context_id=context_id)
        result["document"] = _public_doc(doc)
        if open_in_desktop:
            desktop = desktop_session.get_manager().open(doc)
            result["desktop"] = desktop
            result["open_in_desktop"] = bool(desktop.get("available"))
    return result


def export_host_file(
    local_path: str,
    host_path: str,
    *,
    agent: Any | None = None,
) -> dict[str, Any]:
    source = _local_path(local_path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    data = source.read_bytes()
    if len(data) > MAX_LOCAL_BYTES:
        raise RuntimeError(f"File is too large to export through the host bridge ({len(data)} bytes).")
    payload = request(
        config(agent),
        "POST",
        "/file/write-binary",
        {
            "path": _required(host_path, "host_path"),
            "contentBase64": base64.b64encode(data).decode("ascii"),
            "createDirs": True,
        },
    )
    return {
        "ok": bool(payload.get("ok")),
        "action": "export",
        "local_path": files.normalize_a0_path(str(source)),
        "host_path": payload.get("path") or host_path,
        "size": payload.get("size") or len(data),
        "modifiedAt": payload.get("modifiedAt"),
    }


def _required(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _import_target(local_path: str, basename: str) -> Path:
    if local_path:
        return _local_path(local_path)
    safe = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in basename).strip(" ._") or "host-file"
    target = DEFAULT_IMPORT_DIR / safe
    if not target.exists():
        return target.resolve(strict=False)
    stem = target.stem
    suffix = target.suffix
    for index in range(2, 1000):
        candidate = DEFAULT_IMPORT_DIR / f"{stem} {index}{suffix}"
        if not candidate.exists():
            return candidate.resolve(strict=False)
    raise FileExistsError(f"Could not choose a unique import path for {basename}")


def _local_path(value: str) -> Path:
    raw = _required(value, "local_path")
    if raw.startswith("/a0/"):
        raw = files.get_abs_path(raw.removeprefix("/a0/"))
    candidate = Path(raw if os.path.isabs(raw) else files.get_abs_path(raw)).resolve(strict=False)
    base = Path(files.get_base_dir()).resolve(strict=False)
    try:
        common = os.path.commonpath([str(candidate), str(base)])
    except ValueError as exc:
        raise PermissionError("Local path must stay inside the Vini runtime workspace.") from exc
    if common != str(base):
        raise PermissionError("Local path must stay inside the Vini runtime workspace.")
    return candidate


def _office_app(path: str, app: str = "") -> str:
    normalized = str(app or "").strip().lower()
    if normalized:
        aliases = {"doc": "word", "docx": "word", "xls": "excel", "xlsx": "excel", "ppt": "powerpoint", "pptx": "powerpoint"}
        return aliases.get(normalized, normalized)
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in {"doc", "docx"}:
        return "word"
    if ext in {"xls", "xlsx"}:
        return "excel"
    if ext in {"ppt", "pptx"}:
        return "powerpoint"
    return "word"


def _public_doc(doc: dict[str, Any]) -> dict[str, Any]:
    from plugins._office.helpers import document_store

    return {
        "file_id": doc["file_id"],
        "path": document_store.display_path(doc["path"]),
        "basename": doc["basename"],
        "extension": doc["extension"],
        "size": doc["size"],
        "version": document_store.item_version(doc),
        "last_modified": doc["last_modified"],
    }
