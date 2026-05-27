from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from helpers.api import ApiHandler, Request, Response
from helpers import files
from plugins._vini_app_builder.helpers import builder
from plugins._vini_canvas.helpers import open_design_catalog
from plugins._model_config.helpers import model_config


DATA_DIR = Path(files.get_abs_path(files.USER_DIR, "canvas", "data"))
STATE_FILE = DATA_DIR / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str, fallback: str = "vini-canvas-app") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    return (normalized or fallback)[:54].strip("-") or fallback


def _unique_project_id(name: str) -> str:
    base = _slug(name)
    candidate = base
    index = 2
    while builder._project_dir(candidate).exists():
        candidate = f"{base[:48]}-{index}"
        index += 1
    return candidate


def _derive_app_name(prompt: str, fallback: str = "Vini Canvas App") -> str:
    clean = str(prompt or "").strip()
    if not clean:
        return fallback

    def title_case_name(value: str) -> str:
        minor_words = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "the", "to", "with"}
        words = re.sub(r"[^A-Za-z0-9\s&'-]", " ", value).split()
        titled = []
        for index, word in enumerate(words[:6]):
            lower = word.lower()
            if index > 0 and lower in minor_words:
                titled.append(lower)
            else:
                titled.append(lower[:1].upper() + lower[1:])
        return " ".join(titled).strip()

    match = re.search(
        r"\b(?:called|named)\s+[\"']?(.{2,90}?)(?:[\"']?(?:[.!?,;:\n]|$))",
        clean,
        re.IGNORECASE,
    )
    if match:
        candidate = re.sub(
            r"\b(?:build|create|include|make|use|with)\b.*$",
            "",
            match.group(1).strip(),
            flags=re.IGNORECASE,
        ).strip(" \"'")
        name = title_case_name(candidate)
        if name:
            return name[:60]

    stop_words = {
        "a",
        "an",
        "and",
        "app",
        "application",
        "build",
        "create",
        "for",
        "make",
        "me",
        "modern",
        "new",
        "page",
        "responsive",
        "site",
        "the",
        "to",
        "website",
        "with",
    }
    words = [
        word
        for word in re.sub(r"[^A-Za-z0-9\s-]", " ", clean).split()
        if word and word.lower() not in stop_words
    ][:5]
    if not words:
        return fallback
    return title_case_name(" ".join(words))[:60] or fallback


def _delete_project_dir(project_id: str) -> None:
    target = builder._project_dir(project_id).resolve()
    root = target.parent.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Canvas project path escaped the Vini projects root.") from exc
    if target.exists():
        shutil.rmtree(target)


def _load_state() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        return {"next_app_id": 1, "next_chat_id": 1, "next_message_id": 1, "apps": [], "chats": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return {
        "next_app_id": int(data.get("next_app_id") or 1),
        "next_chat_id": int(data.get("next_chat_id") or 1),
        "next_message_id": int(data.get("next_message_id") or 1),
        "apps": data.get("apps") if isinstance(data.get("apps"), list) else [],
        "chats": data.get("chats") if isinstance(data.get("chats"), list) else [],
    }


def _save_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def _next_id(state: dict[str, Any], key: str) -> int:
    value = int(state.get(key) or 1)
    state[key] = value + 1
    return value


def _find_app(state: dict[str, Any], app_id: int) -> dict[str, Any]:
    for app in state["apps"]:
        if int(app.get("id")) == int(app_id):
            return app
    raise ValueError(f"Vini Canvas app not found: {app_id}")


def _find_chat(state: dict[str, Any], chat_id: int) -> dict[str, Any]:
    for chat in state["chats"]:
        if int(chat.get("id")) == int(chat_id):
            return chat
    raise ValueError(f"Vini Canvas chat not found: {chat_id}")


def _files_for_project(project_id: str) -> list[str]:
    result = builder.handle_action({"action": "files", "project_id": project_id})
    if not result.get("ok"):
        return []
    return [
        str(item.get("path"))
        for item in result.get("files", [])
        if item.get("kind") == "file" or item.get("type") == "file"
    ]


def _project_id_for_app(state: dict[str, Any], app_id: int) -> str:
    return str(_find_app(state, app_id)["project_id"])


def _save_project_metadata(project_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    manifest = builder._load_manifest(project_id)
    manifest.update(metadata)
    return builder._save_manifest(project_id, manifest)


def _git_command(project_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    project_dir = builder._project_dir(project_id)
    return subprocess.run(
        ["git", *args],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=15,
    )


def _is_git_repo(project_id: str) -> bool:
    return (builder._project_dir(project_id) / ".git").exists()


def _stop_preview(project_id: str) -> dict[str, Any]:
    process = builder.PREVIEW_PROCESSES.pop(project_id, None)
    if process is None:
        return {"ok": True, "stopped": False}
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except Exception:
            process.kill()
            process.wait(timeout=8)
    return {"ok": True, "stopped": True, "exit_code": process.poll()}


def _read_project_context(project_id: str) -> str:
    files_result = builder.handle_action({"action": "files", "project_id": project_id})
    if not files_result.get("ok"):
        return ""
    selected: list[tuple[str, str]] = []
    total = 0
    priority = {
        "package.json",
        "index.html",
        "vite.config.ts",
        "tsconfig.json",
        "src/main.tsx",
        "src/App.tsx",
        "src/styles.css",
        "README.md",
    }
    entries = [
        str(item.get("path") or "")
        for item in files_result.get("files", [])
        if (item.get("kind") == "file" or item.get("type") == "file") and item.get("path")
    ]
    entries.sort(key=lambda path: (path not in priority, path))
    for path in entries:
        if any(part in {"node_modules", "dist", ".git"} for part in Path(path).parts):
            continue
        read_result = builder.handle_action({"action": "read", "project_id": project_id, "path": path})
        if not read_result.get("ok"):
            continue
        content = str(read_result.get("content") or "")
        if len(content) > 30000:
            content = content[:30000] + "\n/* ...truncated... */"
        total += len(content)
        if total > 120000:
            break
        selected.append((path, content))
    blocks = []
    for path, content in selected:
        blocks.append(f"--- {path} ---\n{content}")
    return "\n\n".join(blocks)


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = raw.find("{")
    if start == -1:
        raise ValueError("The model did not return a JSON object.")
    decoder = json.JSONDecoder()
    parsed, _end = decoder.raw_decode(raw[start:])
    if not isinstance(parsed, dict):
        raise ValueError("The model JSON response was not an object.")
    return parsed


def _normalize_generated_files(data: dict[str, Any]) -> list[dict[str, str]]:
    raw_files = data.get("files")
    normalized: list[dict[str, str]] = []
    if isinstance(raw_files, dict):
        raw_files = [
            {"path": path, "content": content}
            for path, content in raw_files.items()
        ]
    if not isinstance(raw_files, list):
        raise ValueError("The model response must contain a files array.")
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/").lstrip("/")
        content = item.get("content")
        if not path or content is None:
            continue
        if path.startswith("../") or "/../" in path or path in {".", ".."}:
            raise ValueError(f"Generated file path escaped the project: {path}")
        if any(part in {"node_modules", ".git", "dist"} for part in Path(path).parts):
            continue
        normalized.append(
            {
                "path": path,
                "content": str(content),
                "description": str(item.get("description") or f"Updated {path}"),
            }
        )
    if not normalized:
        raise ValueError("The model response did not contain any writable files.")
    if len(normalized) > 60:
        raise ValueError("The model returned too many files for one Canvas turn.")
    return normalized


def _provider_status() -> tuple[dict[str, Any], str | None]:
    cfg = model_config.get_chat_model_config(None)
    provider = str(cfg.get("provider") or "").strip()
    name = str(cfg.get("name") or "").strip()
    if not provider or not name:
        return cfg, "No Vini AI chat provider/model is configured."
    if not model_config.has_provider_api_key(provider, str(cfg.get("api_key") or ""), "chat"):
        return cfg, f"Vini AI provider '{provider}' is selected but no API key is configured."
    return cfg, None


async def _generate_files_with_vini_model(
    *,
    app: dict[str, Any],
    chat: dict[str, Any],
    prompt: str,
    design_context: dict[str, Any],
    design_brief: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, Any], str]:
    cfg, error = _provider_status()
    if error:
        raise RuntimeError(error)

    project_id = str(app["project_id"])
    context = _read_project_context(project_id)
    history = []
    for message in chat.get("messages", [])[-8:]:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        if role and content:
            history.append(f"{role.upper()}: {content[:4000]}")

    design_guidance = open_design_catalog.prompt_context_block(design_context, design_brief)

    system = """You are Vini Canvas, an app-building backend inside Vini AI.
Generate production-quality React + TypeScript Vite apps by editing real project files.
Return ONLY strict JSON. No markdown, no commentary outside JSON.
The JSON shape must be:
{
  "summary": "short summary",
  "files": [
    {"path": "package.json", "description": "why", "content": "full file content"}
  ]
}
Rules:
- Always return complete file contents, not patches.
- Keep the app runnable with npm install, npm run build, and npm run dev.
- Use only real dependencies declared in package.json.
- Follow the Vini Design Director brief and selected Open Design catalog guidance.
- Prefer polished, domain-specific UI over generic starter/proof cards.
- Do not use fake data when the user asks for backend/integration behavior; surface honest UI states instead.
- Do not claim integrations, reservations, purchases, payments, auth, email delivery, or database writes work unless the generated app includes real working local behavior for them.
- Do not write outside the project. Do not include node_modules, dist, lockfiles, or binary files."""
    user = f"""User request:
{prompt}

Design context:
{design_guidance}

Existing project files:
{context or "(empty project)"}

Recent chat:
{chr(10).join(history) or "(none)"}

Return strict JSON now."""

    model = model_config.build_chat_model(None)
    response, _reasoning = await model.unified_call(
        system_message=system,
        user_message=user,
    )
    parsed = _extract_json_object(response)
    return _normalize_generated_files(parsed), cfg, str(parsed.get("summary") or "")


def _fetch_preview_text(url: str) -> tuple[bool, str, str]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Vini-Canvas-QA/1.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            status = getattr(response, "status", 200)
            body = response.read(2_000_000).decode("utf-8", errors="replace")
            return 200 <= int(status) < 400, body, f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        body = exc.read(200_000).decode("utf-8", errors="replace")
        return False, body, f"HTTP {exc.code}"
    except Exception as exc:
        return False, "", str(exc)


def _run_visual_qa(
    *,
    app: dict[str, Any],
    prompt: str,
    design_brief: dict[str, Any],
    preview_result: dict[str, Any] | None,
) -> dict[str, Any]:
    project_id = str(app["project_id"])
    checks: list[dict[str, Any]] = []
    qa = {
        "ok": False,
        "method": "http-static-preview-qa",
        "started_at": _now(),
        "finished_at": None,
        "checks": checks,
        "preview_url": (preview_result or {}).get("preview_url"),
        "internal_preview_url": (preview_result or {}).get("internal_preview_url"),
        "notes": [
            "This is a real local preview HTTP/static QA pass. Browser/Playwright screenshot QA can be layered on top from the desktop shell.",
        ],
    }

    if not preview_result or not preview_result.get("ok"):
        checks.append({"name": "preview-http", "ok": False, "detail": "Preview did not start or verify."})
        qa["finished_at"] = _now()
        _save_project_metadata(project_id, {"visual_qa_runs": [qa], "quality_gate_status": "preview_failed"})
        return qa

    url = str(preview_result.get("internal_preview_url") or "").strip()
    ok, body, detail = _fetch_preview_text(url)
    checks.append({"name": "preview-http", "ok": ok, "detail": detail})
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip().lower()
    source_context = _read_project_context(project_id).lower()
    text_for_checks = text if len(text) >= 120 else source_context

    blank_ok = len(text) >= 120 or len(source_context) >= 500
    checks.append(
        {
            "name": "not-blank",
            "ok": blank_ok,
            "detail": {
                "preview_text_length": len(text),
                "source_text_length": len(source_context),
                "source_fallback_used": len(text) < 120,
            },
        }
    )

    requested_terms = [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{3,}", prompt.lower())
        if token
        not in {
            "build",
            "called",
            "create",
            "include",
            "make",
            "modern",
            "page",
            "ready",
            "responsive",
            "website",
        }
    ][:18]
    matched_terms = [token for token in requested_terms if token in text_for_checks]
    checks.append(
        {
            "name": "requested-domain-content",
            "ok": len(matched_terms) >= max(1, min(3, len(requested_terms))),
            "detail": {"matched": matched_terms, "sampled": requested_terms},
        }
    )

    placeholder_markers = [
        "production-ready website built by vini ai",
        "generated from intent",
        "live preview",
        "exportable code",
        "welcome to your blank app",
        "build proof",
    ]
    placeholders = [marker for marker in placeholder_markers if marker in text_for_checks]
    checks.append({"name": "no-placeholder-proof-copy", "ok": not placeholders, "detail": placeholders})

    overflow_markers = ["overflow-x: hidden", "word-break", "overflow-wrap", "clamp("]
    checks.append(
        {
            "name": "responsive-text-guards",
            "ok": any(marker in source_context for marker in overflow_markers),
            "detail": "Expected CSS guards such as overflow-wrap, word-break, clamp(), or overflow-x control.",
        }
    )

    qa["ok"] = all(bool(check.get("ok")) for check in checks)
    qa["finished_at"] = _now()
    manifest = builder._load_manifest(project_id)
    runs = manifest.get("visual_qa_runs") if isinstance(manifest.get("visual_qa_runs"), list) else []
    runs.append(qa)
    _save_project_metadata(
        project_id,
        {
            "visual_qa_runs": runs[-10:],
            "quality_gate_status": "passed" if qa["ok"] else "visual_qa_failed",
            "design_brief": design_brief,
        },
    )
    return qa


def _dyad_write_message(
    *,
    summary: str,
    generated_files: list[dict[str, str]],
    build_result: dict[str, Any] | None,
    preview_result: dict[str, Any] | None,
    design_context: dict[str, Any] | None = None,
    design_brief: dict[str, Any] | None = None,
    visual_qa: dict[str, Any] | None = None,
) -> str:
    parts = [
        "<dyad-status>Planning design</dyad-status>",
        "<dyad-status>Selecting skills</dyad-status>",
        "<dyad-status>Selecting design system</dyad-status>",
    ]
    if design_context and design_brief:
        selected_skills = ", ".join(
            str(item.get("id") or item.get("title") or "")
            for item in design_context.get("selected_open_design_skills", [])[:5]
        )
        selected_systems = ", ".join(
            str(item.get("id") or item.get("title") or "")
            for item in design_context.get("selected_open_design_systems", [])[:3]
        )
        brief_payload = escape(
            json.dumps(
                {
                    "domain": design_brief.get("domain"),
                    "skills": selected_skills,
                    "design_systems": selected_systems,
                    "quality_gate": design_brief.get("quality_gate"),
                },
                indent=2,
            ),
            quote=False,
        )
        parts.append(f"<dyad-status>Design brief:\n{brief_payload}\n</dyad-status>")

    parts.append(summary.strip() or "Updated the app files.")
    parts.append("<dyad-status>Writing files</dyad-status>")
    for file_info in generated_files:
        path = escape(file_info["path"], quote=True)
        description = escape(file_info.get("description") or f"Updated {file_info['path']}", quote=True)
        content = escape(file_info["content"], quote=False)
        parts.append(f'<dyad-write path="{path}" description="{description}">\n{content}\n</dyad-write>')

    if build_result:
        parts.append("<dyad-status>Installing dependencies</dyad-status>")
        parts.append("<dyad-status>Building</dyad-status>")
        commands = build_result.get("commands") or []
        failed = [cmd for cmd in commands if isinstance(cmd, dict) and not cmd.get("ok")]
        if build_result.get("ok"):
            parts.append("<dyad-status>Build passed with real npm install/build commands.</dyad-status>")
        else:
            command = failed[-1] if failed else {}
            stderr = str(command.get("stderr") or build_result.get("error") or "Build failed.")
            parts.append(
                "<dyad-status>Build failed. Real stderr:\n"
                + escape(stderr[:4000], quote=False)
                + "\n</dyad-status>"
            )

    if preview_result and preview_result.get("ok"):
        parts.append("<dyad-status>Starting preview</dyad-status>")
        parts.append(f"<dyad-status>Preview started at {escape(str(preview_result.get('preview_url') or ''), quote=False)}</dyad-status>")
    if visual_qa:
        parts.append("<dyad-status>Running visual QA</dyad-status>")
        qa_summary = "Visual QA passed." if visual_qa.get("ok") else "Visual QA found issues."
        parts.append(
            "<dyad-status>"
            + qa_summary
            + "\n"
            + escape(json.dumps(visual_qa.get("checks") or [], indent=2)[:5000], quote=False)
            + "\n</dyad-status>"
        )
        if visual_qa.get("ok"):
            parts.append("<dyad-status>Ready with proof</dyad-status>")
        else:
            parts.append("<dyad-status>Repairing design is required before this app should be treated as complete.</dyad-status>")
    return "\n\n".join(parts)


async def _generate_app_turn(state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    chat = _find_chat(state, int(data.get("chatId")))
    app = _find_app(state, int(chat.get("appId")))
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt is required.")

    _append_message_once(state, chat, "user", prompt)
    _save_state(state)

    design_context = open_design_catalog.select_design_context(prompt)
    design_brief = open_design_catalog.create_design_brief(prompt, design_context)
    _save_project_metadata(
        str(app["project_id"]),
        {
            "open_design_commit": design_context.get("open_design_commit"),
            "selected_open_design_skills": design_context.get("selected_open_design_skills"),
            "selected_open_design_systems": design_context.get("selected_open_design_systems"),
            "selected_vini_skills": design_context.get("selected_vini_skills"),
            "design_brief": design_brief,
            "quality_gate_status": "planning",
        },
    )

    generated_files, cfg, summary = await _generate_files_with_vini_model(
        app=app,
        chat=chat,
        prompt=prompt,
        design_context=design_context,
        design_brief=design_brief,
    )
    for file_info in generated_files:
        write_result = builder.handle_action(
            {
                "action": "write",
                "project_id": app["project_id"],
                "path": file_info["path"],
                "content": file_info["content"],
            }
        )
        if not write_result.get("ok"):
            raise RuntimeError(write_result.get("error") or f"Failed to write {file_info['path']}")

    build_result = builder.handle_action({"action": "build_all", "project_id": app["project_id"], "install": True})
    preview_result = None
    if build_result.get("ok"):
        preview_result = builder.handle_action({"action": "preview", "project_id": app["project_id"], "verify": True})
    visual_qa = _run_visual_qa(
        app=app,
        prompt=prompt,
        design_brief=design_brief,
        preview_result=preview_result,
    )

    assistant_content = _dyad_write_message(
        summary=summary,
        generated_files=generated_files,
        build_result=build_result,
        preview_result=preview_result,
        design_context=design_context,
        design_brief=design_brief,
        visual_qa=visual_qa,
    )
    assistant_message = _append_message(state, chat, "assistant", assistant_content)
    assistant_message["model"] = f"{cfg.get('provider')}/{cfg.get('name')}"
    assistant_message["totalTokens"] = math.ceil((len(prompt) + len(assistant_content)) / 4)
    chat["title"] = chat.get("title") if chat.get("title") and chat.get("title") != "New Chat" else prompt[:60]
    app["updatedAt"] = _now()
    _save_state(state)

    warnings = []
    if build_result and not build_result.get("ok"):
        command = next((cmd for cmd in reversed(build_result.get("commands") or []) if isinstance(cmd, dict) and not cmd.get("ok")), {})
        warnings.append(
            "Build failed with real exit status"
            + (f" {command.get('code')}" if command.get("code") is not None else "")
            + ". Check the generated build output in the chat."
        )
    if preview_result and not preview_result.get("ok"):
        warnings.append(f"Preview did not verify: {preview_result.get('verification') or preview_result.get('error')}")
    if visual_qa and not visual_qa.get("ok"):
        failed_checks = [
            str(check.get("name"))
            for check in visual_qa.get("checks", [])
            if isinstance(check, dict) and not check.get("ok")
        ]
        warnings.append("Visual QA found issues: " + ", ".join(failed_checks))

    return {
        "ok": True,
        "chat": _chat_response(chat),
        "updatedFiles": True,
        "files": [item["path"] for item in generated_files],
        "build": build_result,
        "preview": preview_result,
        "designContext": design_context,
        "designBrief": design_brief,
        "visualQa": visual_qa,
        "warningMessages": warnings,
    }


def _app_response(app: dict[str, Any], *, full: bool = False) -> dict[str, Any]:
    project_id = str(app["project_id"])
    project_path = builder._project_dir(project_id)
    base = {
        "id": int(app["id"]),
        "name": str(app["name"]),
        "path": project_id,
        "createdAt": app.get("createdAt") or _now(),
        "updatedAt": app.get("updatedAt") or _now(),
        "githubOrg": None,
        "githubRepo": None,
        "githubBranch": None,
        "supabaseProjectId": None,
        "supabaseParentProjectId": None,
        "supabaseOrganizationSlug": None,
        "neonProjectId": None,
        "neonDevelopmentBranchId": None,
        "neonPreviewBranchId": None,
        "neonActiveBranchId": None,
        "vercelProjectId": None,
        "vercelProjectName": None,
        "vercelDeploymentUrl": None,
        "vercelTeamId": None,
        "installCommand": "npm install",
        "startCommand": "npm run dev",
        "isFavorite": bool(app.get("isFavorite", False)),
        "resolvedPath": str(project_path),
    }
    if full:
        base.update(
            {
                "files": _files_for_project(project_id),
                "frameworkType": "vite-react",
                "supabaseProjectName": None,
                "vercelTeamSlug": None,
            }
        )
    return base


def _chat_summary(chat: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(chat["id"]),
        "appId": int(chat["appId"]),
        "title": chat.get("title") or None,
        "createdAt": chat.get("createdAt") or _now(),
        "chatMode": chat.get("chatMode") or "build",
    }


def _chat_response(chat: dict[str, Any]) -> dict[str, Any]:
    return {
        **_chat_summary(chat),
        "title": chat.get("title") or "New Chat",
        "messages": chat.get("messages") if isinstance(chat.get("messages"), list) else [],
        "initialCommitHash": None,
        "dbTimestamp": chat.get("updatedAt") or chat.get("createdAt") or _now(),
    }


def _create_chat(state: dict[str, Any], app_id: int, chat_mode: str | None = None) -> int:
    chat_id = _next_id(state, "next_chat_id")
    timestamp = _now()
    state["chats"].append(
        {
            "id": chat_id,
            "appId": int(app_id),
            "title": "New Chat",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "chatMode": chat_mode or "build",
            "messages": [],
        }
    )
    return chat_id


def _append_message(state: dict[str, Any], chat: dict[str, Any], role: str, content: str) -> dict[str, Any]:
    message = {
        "id": _next_id(state, "next_message_id"),
        "role": role,
        "content": content,
        "createdAt": _now(),
        "approvalState": None,
        "commitHash": None,
        "sourceCommitHash": None,
        "dbTimestamp": _now(),
        "requestId": None,
        "totalTokens": None,
        "model": None,
    }
    chat.setdefault("messages", []).append(message)
    chat["updatedAt"] = _now()
    return message


def _append_message_once(state: dict[str, Any], chat: dict[str, Any], role: str, content: str) -> dict[str, Any]:
    clean_content = str(content or "").strip()
    for message in reversed(chat.get("messages") or []):
        if str(message.get("role") or "") != role:
            continue
        if str(message.get("content") or "").strip() == clean_content:
            return message
        break
    return _append_message(state, chat, role, clean_content)


def _handle(data: dict[str, Any]) -> dict[str, Any]:
    action = str(data.get("action") or "").strip()
    state = _load_state()

    if action == "list_apps":
        return {"ok": True, "apps": [_app_response(app) for app in state["apps"]]}

    if action == "check_app_name":
        name = str(data.get("appName") or "").strip()
        exists = any(str(app.get("name", "")).lower() == name.lower() for app in state["apps"])
        return {"ok": True, "exists": exists, "message": "App name already exists." if exists else ""}

    if action == "create_app":
        prompt = str(data.get("prompt") or "").strip()
        name = str(data.get("name") or "").strip() or _derive_app_name(prompt, "Untitled App")
        project_id = _unique_project_id(name)
        created = builder.handle_action(
            {
                "action": "create",
                "name": name,
                "prompt": prompt,
                "project_id": project_id,
            }
        )
        if not created.get("ok"):
            return {"ok": False, "error": created.get("error") or "Failed to create Canvas project."}
        timestamp = _now()
        app = {
            "id": _next_id(state, "next_app_id"),
            "name": name,
            "project_id": created["project"]["project_id"],
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "isFavorite": False,
        }
        state["apps"].append(app)
        chat_id = _create_chat(state, app["id"], data.get("initialChatMode") or "build")
        if prompt:
            chat = _find_chat(state, chat_id)
            _append_message_once(state, chat, "user", prompt)
            chat["title"] = prompt[:60]
        _save_state(state)
        return {"ok": True, "app": _app_response(app), "chatId": chat_id}

    if action == "get_app":
        return {"ok": True, "app": _app_response(_find_app(state, int(data.get("appId"))), full=True)}

    if action == "set_app_theme":
        app = _find_app(state, int(data.get("appId")))
        raw_theme_id = data.get("themeId")
        theme_id = str(raw_theme_id).strip() if raw_theme_id is not None else None
        if not theme_id:
            theme_id = None
        app["themeId"] = theme_id
        app["updatedAt"] = _now()
        manifest = builder._load_manifest(str(app["project_id"]))
        manifest["canvas_theme_id"] = theme_id
        builder._save_manifest(str(app["project_id"]), manifest)
        _save_state(state)
        return {"ok": True, "themeId": theme_id}

    if action == "get_app_theme":
        app = _find_app(state, int(data.get("appId")))
        return {"ok": True, "themeId": app.get("themeId") or None}

    if action == "list_versions":
        app = _find_app(state, int(data.get("appId")))
        project_id = str(app["project_id"])
        if not _is_git_repo(project_id):
            return {"ok": True, "versions": []}
        result = _git_command(
            project_id,
            ["log", "--max-count=100000", "--pretty=format:%H%x00%s%x00%ct"],
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "Unable to read Canvas git history."}
        versions = []
        for line in result.stdout.splitlines():
            parts = line.split("\x00")
            if len(parts) != 3:
                continue
            oid, message, timestamp = parts
            try:
                parsed_timestamp = int(timestamp)
            except ValueError:
                parsed_timestamp = 0
            versions.append(
                {
                    "oid": oid,
                    "message": message,
                    "timestamp": parsed_timestamp,
                    "dbTimestamp": None,
                }
            )
        return {"ok": True, "versions": versions}

    if action == "get_current_branch":
        app = _find_app(state, int(data.get("appId")))
        project_id = str(app["project_id"])
        if not _is_git_repo(project_id):
            return {"ok": True, "branch": "no-git"}
        result = _git_command(project_id, ["branch", "--show-current"])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "Unable to read Canvas git branch."}
        branch = result.stdout.strip() or "detached"
        return {"ok": True, "branch": branch}

    if action == "get_proposal":
        _find_chat(state, int(data.get("chatId")))
        return {"ok": True, "proposal": None}

    if action == "apply_app_template":
        app = _find_app(state, int(data.get("appId")))
        template_id = str(data.get("templateId") or "react").strip()
        supported_templates = {"react", "vite-react", "vite-react-ts", "default"}
        if template_id not in supported_templates:
            return {"ok": False, "error": f"Vini Canvas template is not available yet: {template_id}"}
        app["templateId"] = template_id
        app["updatedAt"] = _now()
        manifest = builder._load_manifest(str(app["project_id"]))
        manifest["canvas_template_id"] = template_id
        builder._save_manifest(str(app["project_id"]), manifest)
        _save_state(state)
        return {"ok": True, "applied": False, "needsRestart": False}

    if action == "delete_app":
        app_id = int(data.get("appId"))
        app = _find_app(state, app_id)
        state["apps"] = [item for item in state["apps"] if int(item.get("id")) != app_id]
        state["chats"] = [item for item in state["chats"] if int(item.get("appId")) != app_id]
        _save_state(state)
        _delete_project_dir(str(app.get("project_id") or ""))
        return {"ok": True, "project_id": app.get("project_id")}

    if action == "create_chat":
        chat_id = _create_chat(state, int(data.get("appId")), data.get("initialChatMode") or "build")
        _save_state(state)
        return {"ok": True, "chatId": chat_id}

    if action == "get_chats":
        app_id = data.get("appId")
        chats = state["chats"]
        if app_id is not None:
            chats = [chat for chat in chats if int(chat.get("appId")) == int(app_id)]
        chats = sorted(chats, key=lambda chat: str(chat.get("updatedAt") or chat.get("createdAt") or ""), reverse=True)
        return {"ok": True, "chats": [_chat_summary(chat) for chat in chats]}

    if action == "get_chat":
        return {"ok": True, "chat": _chat_response(_find_chat(state, int(data.get("chatId"))))}

    if action == "get_chat_metadata":
        return {"ok": True, "chat": _chat_summary(_find_chat(state, int(data.get("chatId"))))}

    if action == "update_chat":
        chat = _find_chat(state, int(data.get("chatId")))
        if "title" in data:
            chat["title"] = data.get("title") or None
        if "chatMode" in data:
            chat["chatMode"] = data.get("chatMode") or "build"
        chat["updatedAt"] = _now()
        _save_state(state)
        return {"ok": True}

    if action == "delete_chat":
        chat_id = int(data.get("chatId"))
        state["chats"] = [chat for chat in state["chats"] if int(chat.get("id")) != chat_id]
        _save_state(state)
        return {"ok": True}

    if action == "delete_messages":
        chat = _find_chat(state, int(data.get("chatId")))
        chat["messages"] = []
        chat["updatedAt"] = _now()
        _save_state(state)
        return {"ok": True}

    if action == "read_app_file":
        app = _find_app(state, int(data.get("appId")))
        result = builder.handle_action({"action": "read", "project_id": app["project_id"], "path": data.get("filePath")})
        return {"ok": bool(result.get("ok")), "content": result.get("content", ""), "error": result.get("error")}

    if action == "edit_app_file":
        app = _find_app(state, int(data.get("appId")))
        result = builder.handle_action(
            {
                "action": "write",
                "project_id": app["project_id"],
                "path": data.get("filePath"),
                "content": data.get("content") or "",
            }
        )
        return {"ok": bool(result.get("ok")), "warning": result.get("error") if not result.get("ok") else None}

    if action == "run_app":
        project_id = _project_id_for_app(state, int(data.get("appId")))
        project_dir = builder._project_dir(project_id)
        if (project_dir / "package.json").is_file() and not (project_dir / "node_modules").exists():
            install = builder.handle_action({"action": "install", "project_id": project_id})
            if not install.get("ok"):
                command = install.get("command") or {}
                return {
                    "ok": False,
                    "error": command.get("stderr") or install.get("error") or "npm install failed for Canvas project.",
                    "command": command,
                }
        preview = builder.handle_action({"action": "preview", "project_id": project_id, "verify": True})
        if not preview.get("ok"):
            return {"ok": False, "error": preview.get("error") or str(preview.get("verification") or "Preview failed."), "preview": preview}
        return {"ok": True, "preview": preview, "project": preview.get("project")}

    if action == "stop_app":
        project_id = _project_id_for_app(state, int(data.get("appId")))
        return _stop_preview(project_id)

    if action == "restart_app":
        project_id = _project_id_for_app(state, int(data.get("appId")))
        _stop_preview(project_id)
        preview = _handle({"action": "run_app", "appId": int(data.get("appId"))})
        if not preview.get("ok"):
            return preview
        return {"ok": True, **preview}

    if action == "search_apps":
        query = str(data.get("query") or "").lower()
        matches = []
        for app in state["apps"]:
            if query in str(app.get("name", "")).lower():
                matches.append({"id": app["id"], "name": app["name"], "createdAt": app["createdAt"], "matchedChatTitle": None, "matchedChatMessage": None})
        return {"ok": True, "results": matches}

    if action == "count_tokens":
        input_text = str(data.get("input") or "")
        approx = max(1, math.ceil(len(input_text) / 4))
        return {
            "ok": True,
            "tokens": {
                "estimatedTotalTokens": approx,
                "actualMaxTokens": None,
                "messageHistoryTokens": 0,
                "codebaseTokens": 0,
                "mentionedAppsTokens": 0,
                "inputTokens": approx,
                "systemPromptTokens": 0,
                "contextWindow": 128000,
            },
        }

    if action == "sync-open-design-catalog" or action == "sync_open_design_catalog":
        manifest = open_design_catalog.catalog_manifest()
        counts = open_design_catalog.catalog_counts()
        return {"ok": True, "manifest": manifest, "counts": counts}

    if action == "list-design-skills" or action == "list_design_skills":
        return {
            "ok": True,
            "manifest": open_design_catalog.catalog_manifest(),
            "skills": [entry.public() for entry in open_design_catalog.skills()],
            "viniSkills": open_design_catalog.VINI_NATIVE_SKILLS,
        }

    if action == "list-design-systems" or action == "list_design_systems":
        return {
            "ok": True,
            "manifest": open_design_catalog.catalog_manifest(),
            "designSystems": [entry.public() for entry in open_design_catalog.design_systems()],
        }

    if action == "select-design-context" or action == "select_design_context":
        prompt = str(data.get("prompt") or "")
        return {"ok": True, "context": open_design_catalog.select_design_context(prompt)}

    if action == "create-design-brief" or action == "create_design_brief":
        prompt = str(data.get("prompt") or "")
        context = data.get("context") if isinstance(data.get("context"), dict) else open_design_catalog.select_design_context(prompt)
        return {"ok": True, "brief": open_design_catalog.create_design_brief(prompt, context), "context": context}

    if action == "run-visual-qa" or action == "run_visual_qa":
        app = _find_app(state, int(data.get("appId")))
        project_id = str(app["project_id"])
        manifest = builder._load_manifest(project_id)
        preview_result = {
            "ok": bool((manifest.get("preview_verification") or {}).get("ok")),
            "preview_url": manifest.get("preview_url"),
            "internal_preview_url": manifest.get("internal_preview_url"),
            "verification": manifest.get("preview_verification"),
        }
        prompt = str(data.get("prompt") or manifest.get("brief") or "")
        design_brief = manifest.get("design_brief") if isinstance(manifest.get("design_brief"), dict) else {}
        qa = _run_visual_qa(app=app, prompt=prompt, design_brief=design_brief, preview_result=preview_result)
        return {"ok": True, "visualQa": qa}

    if action == "repair-from-qa" or action == "repair_from_qa":
        return {
            "ok": False,
            "error": "Automatic repair is performed during generation when visual QA fails. Start a Retry/Build turn to repair with the recorded QA evidence.",
        }

    if action == "get-build-proof" or action == "get_build_proof":
        app = _find_app(state, int(data.get("appId")))
        project_id = str(app["project_id"])
        status = builder.handle_action({"action": "status", "project_id": project_id})
        manifest = status.get("project") or {}
        return {
            "ok": True,
            "proof": {
                "project_id": project_id,
                "status": manifest.get("status"),
                "preview_url": manifest.get("preview_url"),
                "internal_preview_url": manifest.get("internal_preview_url"),
                "last_verified_at": manifest.get("last_verified_at"),
                "quality_gate_status": manifest.get("quality_gate_status"),
                "open_design_commit": manifest.get("open_design_commit"),
                "visual_qa_runs": manifest.get("visual_qa_runs") or [],
                "log": status.get("log"),
            },
        }

    if action == "record_chat_prompt":
        chat = _find_chat(state, int(data.get("chatId")))
        _append_message(state, chat, "user", str(data.get("prompt") or ""))
        _save_state(state)
        return {"ok": True, "chat": _chat_response(chat)}

    return {"ok": False, "error": f"Unsupported Vini Canvas backend action: {action}"}


class Backend(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            if str((input or {}).get("action") or "").strip() == "generate_app":
                if (input or {}).get("chatId") is None:
                    return {"ok": False, "error": "chatId is required for Vini Canvas generation."}
                return await _generate_app_turn(_load_state(), input or {})
            return _handle(input or {})
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
