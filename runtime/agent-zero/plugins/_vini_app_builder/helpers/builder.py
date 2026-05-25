from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Response, request
from helpers import files, plugins


PLUGIN_NAME = "_vini_app_builder"
MANIFEST_NAME = "vini-project.json"
LOG_NAME = "vini-builder.log"
DEFAULT_FRAMEWORK = "vite-react-ts"
PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SKIP_EXPORT_DIRS = {"node_modules", ".git", "dist", ".vite"}
SKIP_EXPORT_FILES = {LOG_NAME}
PREVIEW_PROCESSES: dict[str, subprocess.Popen[str]] = {}


@dataclass
class CommandResult:
    ok: bool
    command: list[str]
    cwd: str
    code: int
    stdout: str
    stderr: str
    duration_seconds: float


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config() -> dict[str, Any]:
    raw = plugins.get_plugin_config(PLUGIN_NAME) or {}
    return {
        "enabled": bool(raw.get("enabled", True)),
        "projects_root": str(raw.get("projects_root") or "/a0/usr/projects"),
        "exports_root": str(raw.get("exports_root") or "/a0/usr/exports"),
        "preview_port_start": int(raw.get("preview_port_start") or 43100),
        "preview_port_end": int(raw.get("preview_port_end") or 43199),
        "command_timeout_seconds": int(raw.get("command_timeout_seconds") or 240),
        "max_response_chars": int(raw.get("max_response_chars") or 20000),
    }


def _resolve_a0_path(path_value: str) -> Path:
    path_text = str(path_value or "").strip()
    if path_text.startswith("/a0/"):
        path_text = path_text.removeprefix("/a0/")
    elif path_text.startswith("/a0"):
        path_text = path_text.removeprefix("/a0").lstrip("/")
    if os.path.isabs(path_text):
        return Path(path_text).resolve()
    return Path(files.get_abs_path(path_text)).resolve()


def _projects_root() -> Path:
    root = _resolve_a0_path(_config()["projects_root"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _exports_root() -> Path:
    root = _resolve_a0_path(_config()["exports_root"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slug(value: str, fallback: str = "vini-app") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    return (normalized or fallback)[:54].strip("-") or fallback


def _unique_project_id(name: str) -> str:
    root = _projects_root()
    base = _slug(name)
    candidate = base
    index = 2
    while (root / candidate).exists():
        candidate = f"{base[:48]}-{index}"
        index += 1
    return candidate


def _project_dir(project_id: str) -> Path:
    project_id = _normalize_project_id(project_id)
    root = _projects_root().resolve()
    target = (root / project_id).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Project path escaped the Vini AI projects root.") from exc
    return target


def _normalize_project_id(project_id: str) -> str:
    value = str(project_id or "").strip().lower()
    if not PROJECT_ID_RE.match(value):
        raise ValueError("project_id must be a lowercase slug containing letters, numbers, and dashes.")
    return value


def _safe_project_file(project_id: str, relative_path: str) -> Path:
    project_dir = _project_dir(project_id).resolve()
    target = (project_dir / str(relative_path or "").lstrip("/\\")).resolve()
    try:
        target.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError("File path escaped the project directory.") from exc
    return target


def _manifest_path(project_id: str) -> Path:
    return _project_dir(project_id) / MANIFEST_NAME


def _log_path(project_id: str) -> Path:
    return _project_dir(project_id) / LOG_NAME


def _load_manifest(project_id: str) -> dict[str, Any]:
    path = _manifest_path(project_id)
    if not path.is_file():
        raise FileNotFoundError(f"Vini app project not found: {project_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(project_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["updated_at"] = _now()
    _manifest_path(project_id).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _public_project(manifest: dict[str, Any]) -> dict[str, Any]:
    project_id = str(manifest["project_id"])
    status = _process_status(project_id)
    public = dict(manifest)
    public["preview_process"] = status
    public["project_path"] = str(_project_dir(project_id))
    public["project_a0_path"] = f"/a0/usr/projects/{project_id}"
    public["manifest_path"] = str(_manifest_path(project_id))
    public["log_path"] = str(_log_path(project_id))
    return public


def _append_log(project_id: str, text: str) -> None:
    _log_path(project_id).parent.mkdir(parents=True, exist_ok=True)
    with _log_path(project_id).open("a", encoding="utf-8") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")


def _truncate(value: str, max_chars: int | None = None) -> str:
    limit = max_chars or _config()["max_response_chars"]
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated {len(value) - limit} chars]"


def _run(project_id: str, command: list[str], timeout_seconds: int | None = None) -> CommandResult:
    cwd = _project_dir(project_id)
    start = time.time()
    _append_log(project_id, f"\n[{_now()}] $ {' '.join(command)}")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds or _config()["command_timeout_seconds"],
            shell=False,
        )
        result = CommandResult(
            ok=completed.returncode == 0,
            command=command,
            cwd=str(cwd),
            code=completed.returncode,
            stdout=_truncate(completed.stdout),
            stderr=_truncate(completed.stderr),
            duration_seconds=round(time.time() - start, 3),
        )
    except FileNotFoundError as exc:
        result = CommandResult(
            ok=False,
            command=command,
            cwd=str(cwd),
            code=127,
            stdout="",
            stderr=f"Command not found: {command[0]}. Install Node.js/npm in the runtime image to build Vini app projects. {exc}",
            duration_seconds=round(time.time() - start, 3),
        )
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            ok=False,
            command=command,
            cwd=str(cwd),
            code=124,
            stdout=_truncate(str(exc.stdout or "")),
            stderr=_truncate(str(exc.stderr or "") + f"\nCommand timed out after {exc.timeout} seconds."),
            duration_seconds=round(time.time() - start, 3),
        )

    if result.stdout:
        _append_log(project_id, result.stdout)
    if result.stderr:
        _append_log(project_id, result.stderr)
    _append_log(project_id, f"[{_now()}] exit={result.code} duration={result.duration_seconds}s")
    return result


def _command_dict(result: CommandResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "command": result.command,
        "cwd": result.cwd,
        "code": result.code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": result.duration_seconds,
    }


def _find_free_port(project_id: str) -> int:
    manifest = None
    try:
        manifest = _load_manifest(project_id)
    except Exception:
        pass
    existing = int((manifest or {}).get("preview_port") or 0)
    if existing and _port_available(existing):
        return existing

    cfg = _config()
    for port in range(cfg["preview_port_start"], cfg["preview_port_end"] + 1):
        if _port_available(port):
            return port
    raise RuntimeError("No free Vini preview ports are available in the configured range.")


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _process_status(project_id: str) -> dict[str, Any]:
    process = PREVIEW_PROCESSES.get(project_id)
    if process is None:
        return {"running": False}
    code = process.poll()
    return {
        "running": code is None,
        "pid": process.pid,
        "exit_code": code,
    }


def _wait_for_http(url: str, timeout_seconds: int = 20) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                body = response.read(4096).decode("utf-8", errors="replace")
                return {
                    "ok": 200 <= int(response.status) < 400,
                    "status": response.status,
                    "title_detected": "<title>" in body.lower(),
                }
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    return {"ok": False, "error": last_error or "Preview did not respond in time."}


def _starter_files(name: str, prompt: str, project_id: str) -> dict[str, str]:
    title = name.strip() or "Vini App"
    safe_title = title.replace('"', '\\"')
    return {
        "package.json": json.dumps(
            {
                "name": project_id,
                "version": "0.1.0",
                "private": True,
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "typecheck": "tsc -b",
                    "preview": "vite preview",
                },
                "dependencies": {
                    "@vitejs/plugin-react": "^5.1.1",
                    "vite": "^7.2.4",
                    "typescript": "^5.9.3",
                    "react": "^19.2.1",
                    "react-dom": "^19.2.1",
                    "lucide-react": "^0.555.0",
                },
                "devDependencies": {
                    "@types/react": "^19.2.7",
                    "@types/react-dom": "^19.2.3",
                },
            },
            indent=2,
        )
        + "\n",
        "index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{safe_title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
        "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
""",
        "vite.config.ts": f"""import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({{
  base: process.env.VINI_PREVIEW_BASE || "/",
  plugins: [react()],
  server: {{
    host: "127.0.0.1",
    strictPort: true
  }}
}});
""",
        "src/main.tsx": """import React from "react";
import { createRoot } from "react-dom/client";
import { Sparkles, Monitor, PackageCheck } from "lucide-react";
import "./styles.css";

const brief = import.meta.env.VITE_VINI_BRIEF || "A production-ready website built by Vini AI.";

function App() {
  return (
    <main className="app">
      <section className="hero">
        <div className="mark">V</div>
        <p className="eyebrow">Vini AI Website Builder</p>
        <h1>""" + title + """</h1>
        <p className="brief">{brief}</p>
        <div className="actions">
          <a href="#features">Explore</a>
          <a href="#proof" className="secondary">Build proof</a>
        </div>
      </section>
      <section id="features" className="grid">
        <article>
          <Sparkles />
          <h2>Generated from intent</h2>
          <p>Vini created this project in the local runtime workspace and can keep editing the real files.</p>
        </article>
        <article>
          <Monitor />
          <h2>Live preview</h2>
          <p>The app runs through a real Vite dev server and is shown through Vini Computer.</p>
        </article>
        <article id="proof">
          <PackageCheck />
          <h2>Exportable code</h2>
          <p>The source can be zipped locally without cloud lock-in or hidden proprietary formats.</p>
        </article>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
""",
        "src/styles.css": """* {
  box-sizing: border-box;
}

:root {
  color: #f5f5f5;
  background: #050505;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: #050505;
}

.app {
  min-height: 100vh;
  display: grid;
  gap: 24px;
  padding: clamp(24px, 5vw, 72px);
}

.hero {
  min-height: 52vh;
  display: grid;
  align-content: center;
  gap: 18px;
  max-width: 920px;
}

.mark {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #f5f5f5;
  color: #050505;
  font-weight: 900;
  font-size: 28px;
}

.eyebrow {
  margin: 0;
  color: #8b8b92;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 800;
}

h1 {
  margin: 0;
  font-size: clamp(44px, 8vw, 96px);
  line-height: .95;
  letter-spacing: 0;
}

.brief {
  margin: 0;
  color: #c9c9cf;
  font-size: clamp(17px, 2vw, 22px);
  line-height: 1.5;
  max-width: 760px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.actions a {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  border-radius: 7px;
  padding: 0 16px;
  background: #f5f5f5;
  color: #050505;
  text-decoration: none;
  font-weight: 800;
}

.actions .secondary {
  background: #151515;
  color: #f5f5f5;
  border: 1px solid #303030;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

article {
  border: 1px solid #262626;
  border-radius: 8px;
  background: #101010;
  padding: 20px;
}

article svg {
  color: #50d890;
}

h2 {
  margin: 14px 0 8px;
  font-size: 19px;
}

article p {
  margin: 0;
  color: #b9b9c0;
  line-height: 1.45;
}

@media (max-width: 800px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
""",
        "README.md": f"""# {title}

Generated in Vini AI's local app-builder workspace.

## Original brief

{prompt.strip() or "No brief was provided."}

## Commands

```bash
npm install
npm run build
npm run dev -- --host 127.0.0.1 --port <preview-port>
```
""",
    }


def create_project(name: str = "", prompt: str = "", project_id: str = "", overwrite: bool = False) -> dict[str, Any]:
    if not _config()["enabled"]:
        return {"ok": False, "error": "Vini app builder is disabled in plugin settings."}
    resolved_id = _normalize_project_id(project_id) if project_id else _unique_project_id(name or prompt or "vini-app")
    project_dir = _project_dir(resolved_id)
    if project_dir.exists() and not overwrite:
        return {"ok": False, "error": f"Project already exists: {resolved_id}", "project_id": resolved_id}
    project_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in _starter_files(name or resolved_id, prompt, resolved_id).items():
        target = _safe_project_file(resolved_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    manifest = {
        "project_id": resolved_id,
        "name": name.strip() or resolved_id,
        "brief": prompt.strip(),
        "framework": DEFAULT_FRAMEWORK,
        "status": "created",
        "created_at": _now(),
        "updated_at": _now(),
        "dev_command": "npm run dev -- --host 127.0.0.1 --port ${PORT}",
        "preview_port": None,
        "preview_url": None,
        "internal_preview_url": None,
        "last_command": None,
        "last_verified_at": None,
        "export_path": None,
    }
    _save_manifest(resolved_id, manifest)
    _append_log(resolved_id, f"[{_now()}] Created Vini app project {resolved_id}")
    return {"ok": True, "project": _public_project(manifest)}


def list_projects() -> dict[str, Any]:
    root = _projects_root()
    projects = []
    for manifest_path in root.glob(f"*/{MANIFEST_NAME}"):
        try:
            projects.append(_public_project(json.loads(manifest_path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    projects.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return {"ok": True, "projects": projects}


def project_status(project_id: str) -> dict[str, Any]:
    manifest = _load_manifest(project_id)
    log = ""
    log_path = _log_path(project_id)
    if log_path.exists():
        log = _truncate(log_path.read_text(encoding="utf-8", errors="replace"))
    return {"ok": True, "project": _public_project(manifest), "log": log}


def list_files(project_id: str) -> dict[str, Any]:
    root = _project_dir(project_id)
    entries = []
    for path in root.rglob("*"):
        if any(part in SKIP_EXPORT_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in SKIP_EXPORT_FILES:
            continue
        stat = path.stat()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "kind": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return {"ok": True, "project_id": project_id, "files": entries}


def read_file(project_id: str, path: str) -> dict[str, Any]:
    target = _safe_project_file(project_id, path)
    if not target.is_file():
        return {"ok": False, "error": f"File not found: {path}"}
    if target.stat().st_size > 1024 * 1024:
        return {"ok": False, "error": f"File is too large to read through Vini app builder: {path}"}
    return {"ok": True, "project_id": project_id, "path": path, "content": target.read_text(encoding="utf-8")}


def write_file(project_id: str, path: str, content: str) -> dict[str, Any]:
    target = _safe_project_file(project_id, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    manifest = _load_manifest(project_id)
    manifest["status"] = "edited"
    _save_manifest(project_id, manifest)
    _append_log(project_id, f"[{_now()}] Wrote {path}")
    return {"ok": True, "project": _public_project(manifest), "path": path, "size": target.stat().st_size}


def run_script(project_id: str, script: str) -> dict[str, Any]:
    allowed = {
        "install": ["npm", "install"],
        "build": ["npm", "run", "build"],
        "typecheck": ["npm", "run", "typecheck"],
    }
    if script not in allowed:
        return {"ok": False, "error": f"Unsupported script: {script}. Supported: {', '.join(allowed)}"}
    result = _run(project_id, allowed[script])
    manifest = _load_manifest(project_id)
    manifest["status"] = f"{script}_{'passed' if result.ok else 'failed'}"
    manifest["last_command"] = _command_dict(result)
    _save_manifest(project_id, manifest)
    return {"ok": result.ok, "project": _public_project(manifest), "command": _command_dict(result)}


def build_project(project_id: str, install: bool = True) -> dict[str, Any]:
    commands = []
    ok = True
    if install:
        install_result = run_script(project_id, "install")
        commands.append(install_result.get("command"))
        ok = bool(install_result.get("ok"))
    if ok:
        build_result = run_script(project_id, "build")
        commands.append(build_result.get("command"))
        ok = bool(build_result.get("ok"))
    manifest = _load_manifest(project_id)
    manifest["status"] = "build_passed" if ok else "build_failed"
    _save_manifest(project_id, manifest)
    return {"ok": ok, "project": _public_project(manifest), "commands": commands}


def preview_project(project_id: str, start: bool = True, verify: bool = True) -> dict[str, Any]:
    manifest = _load_manifest(project_id)
    port = int(manifest.get("preview_port") or 0)
    status = _process_status(project_id)
    if not status.get("running") and start:
        port = _find_free_port(project_id)
        env = os.environ.copy()
        env["VINI_PREVIEW_BASE"] = f"/vini-preview/{project_id}/"
        env["VITE_VINI_BRIEF"] = str(manifest.get("brief") or "")
        log_handle = _log_path(project_id).open("a", encoding="utf-8")
        log_handle.write(f"\n[{_now()}] $ npm run dev -- --host 127.0.0.1 --port {port}\n")
        log_handle.flush()
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(_project_dir(project_id)),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            shell=False,
        )
        PREVIEW_PROCESSES[project_id] = process
        time.sleep(0.5)

    internal_url = f"http://127.0.0.1:{port}/"
    public_url = f"/vini-preview/{project_id}/"
    verification = _wait_for_http(internal_url, timeout_seconds=20) if verify else {"ok": None}
    manifest.update(
        {
            "status": "preview_running" if verification.get("ok") else "preview_unverified",
            "preview_port": port,
            "preview_url": public_url,
            "internal_preview_url": internal_url,
            "last_verified_at": _now() if verification.get("ok") else manifest.get("last_verified_at"),
            "preview_verification": verification,
        }
    )
    _save_manifest(project_id, manifest)
    return {
        "ok": bool(verification.get("ok")),
        "project": _public_project(manifest),
        "preview_url": public_url,
        "internal_preview_url": internal_url,
        "verification": verification,
    }


def export_project(project_id: str) -> dict[str, Any]:
    manifest = _load_manifest(project_id)
    source = _project_dir(project_id)
    export_dir = _exports_root()
    zip_path = export_dir / f"{project_id}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            if any(part in SKIP_EXPORT_DIRS for part in relative.parts):
                continue
            if path.name in SKIP_EXPORT_FILES or path == zip_path:
                continue
            if path.is_file():
                archive.write(path, arcname=f"{project_id}/{relative.as_posix()}")
    manifest["status"] = "exported"
    manifest["export_path"] = str(zip_path)
    manifest["export_url"] = f"/vini-builder/export/{project_id}"
    _save_manifest(project_id, manifest)
    return {"ok": True, "project": _public_project(manifest), "export_path": str(zip_path), "export_url": manifest["export_url"]}


def proxy_preview(project_id: str, subpath: str = "") -> Response:
    manifest = _load_manifest(project_id)
    port = int(manifest.get("preview_port") or 0)
    if not port:
        return Response("Preview has not been started for this project.", status=404)
    target_path = "/" + (subpath or "")
    query = request.query_string.decode("utf-8", errors="replace")
    target = f"http://127.0.0.1:{port}{target_path}"
    if query:
        target += f"?{query}"
    try:
        upstream = urllib.request.Request(target, method=request.method)
        with urllib.request.urlopen(upstream, timeout=15) as response:
            data = response.read()
            content_type = response.headers.get("content-type")
            if not content_type:
                content_type = mimetypes.guess_type(target_path)[0] or "application/octet-stream"
            headers = {"cache-control": "no-store"}
            return Response(data, status=response.status, content_type=content_type, headers=headers)
    except urllib.error.HTTPError as exc:
        return Response(exc.read(), status=exc.code)
    except Exception as exc:
        return Response(f"Vini preview unavailable: {exc}", status=502)


def download_export(project_id: str) -> Response:
    result = export_project(project_id)
    if not result.get("ok"):
        return Response(str(result.get("error") or "Export failed"), status=500)
    path = Path(str(result["export_path"]))
    return Response(
        path.read_bytes(),
        content_type="application/zip",
        headers={
            "content-disposition": f'attachment; filename="{project_id}.zip"',
            "content-length": str(path.stat().st_size),
            "cache-control": "no-store",
        },
    )


def handle_action(data: dict[str, Any]) -> dict[str, Any]:
    action = str(data.get("action") or "list").strip().lower()
    if action == "create":
        return create_project(
            name=str(data.get("name") or ""),
            prompt=str(data.get("prompt") or data.get("brief") or ""),
            project_id=str(data.get("project_id") or ""),
            overwrite=bool(data.get("overwrite")),
        )
    if action == "list":
        return list_projects()
    if action == "status":
        return project_status(str(data.get("project_id") or ""))
    if action == "files":
        return list_files(str(data.get("project_id") or ""))
    if action == "read":
        return read_file(str(data.get("project_id") or ""), str(data.get("path") or ""))
    if action == "write":
        return write_file(str(data.get("project_id") or ""), str(data.get("path") or ""), str(data.get("content") or ""))
    if action in {"install", "build", "typecheck"}:
        if action == "build":
            return build_project(str(data.get("project_id") or ""), install=bool(data.get("install", False)))
        return run_script(str(data.get("project_id") or ""), action)
    if action == "build_all":
        return build_project(str(data.get("project_id") or ""), install=bool(data.get("install", True)))
    if action in {"preview", "start_preview"}:
        return preview_project(str(data.get("project_id") or ""), start=True, verify=bool(data.get("verify", True)))
    if action == "export":
        return export_project(str(data.get("project_id") or ""))
    return {"ok": False, "error": f"Unsupported Vini app builder action: {action}"}
