from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from helpers import files


TASK_ROOT_PARTS = ("usr", "browser_tasks")
WORKSPACE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")
MAX_TAIL_CHARS = 4000


class ScriptedBrowserTaskError(RuntimeError):
    pass


def create_scripted_browser_task(
    *,
    task: str,
    start_url: str = "",
    plan: str | list[str] | None = None,
    script: str = "",
) -> dict[str, Any]:
    task_text = str(task or "").strip()
    if not task_text:
        raise ScriptedBrowserTaskError("task is required")

    root = _task_root()
    root.mkdir(parents=True, exist_ok=True)
    workspace_id = _new_workspace_id(task_text)
    workspace_dir = _safe_workspace_dir(workspace_id, must_exist=False)
    workspace_dir.mkdir(parents=False, exist_ok=False)

    plan_text = _format_plan(task_text, start_url, plan)
    final_script = _normalize_script(script) or _starter_script(task_text, start_url)
    status = "ready" if script.strip() else "script_required"

    _write_text(workspace_dir / "plan.md", plan_text)
    _write_text(workspace_dir / "final_script.py", final_script)
    _write_json(
        workspace_dir / "task.json",
        {
            "workspace_id": workspace_id,
            "task": task_text,
            "start_url": start_url,
            "status": status,
            "created_at": _utc_timestamp(),
        },
    )

    return {
        "ok": True,
        "status": status,
        "workspace_id": workspace_id,
        "workspace": str(workspace_dir),
        "plan_path": str(workspace_dir / "plan.md"),
        "final_script_path": str(workspace_dir / "final_script.py"),
        "message": (
            "Workspace created. Write a task-specific final_script.py before running."
            if status == "script_required"
            else "Workspace created with executable final_script.py."
        ),
    }


def run_scripted_browser_task(
    *,
    workspace_id: str,
    timeout: int = 90,
) -> dict[str, Any]:
    workspace_dir = _safe_workspace_dir(workspace_id, must_exist=True)
    final_script = workspace_dir / "final_script.py"
    if not final_script.exists():
        raise ScriptedBrowserTaskError(f"final_script.py is missing for {workspace_id}")

    run_dir = _next_run_dir(workspace_dir)
    run_dir.mkdir(parents=False, exist_ok=False)
    run_script = run_dir / "final_script.py"
    shutil.copy2(final_script, run_script)

    env = os.environ.copy()
    env["VINI_BROWSER_TASK_DIR"] = str(workspace_dir)
    env["VINI_BROWSER_RUN_DIR"] = str(run_dir)
    env["PYTHONUNBUFFERED"] = "1"

    started = time.time()
    timed_out = False
    try:
        completed = subprocess.run(
            [sys.executable, str(run_script)],
            cwd=str(run_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout or 90)),
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = _decode_output(exc.stdout)
        stderr = _decode_output(exc.stderr)
        stderr = (stderr + "\n" if stderr else "") + f"Timed out after {timeout} seconds"

    duration_ms = int((time.time() - started) * 1000)
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    _write_text(stdout_path, stdout)
    _write_text(stderr_path, stderr)

    screenshots = _collect_artifacts(run_dir, ("*.png", "*.jpg", "*.jpeg", "*.webp"))
    logs = _collect_artifacts(run_dir, ("*.log", "*log*.txt"))
    script_report_path = run_dir / "report.json"
    script_report = _read_json(script_report_path) if script_report_path.exists() else None

    status = "timeout" if timed_out else ("completed" if exit_code == 0 else "failed")
    report = {
        "ok": exit_code == 0 and not timed_out,
        "status": status,
        "workspace_id": workspace_id,
        "workspace": str(workspace_dir),
        "run_dir": str(run_dir),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_tail": stdout[-MAX_TAIL_CHARS:],
        "stderr_tail": stderr[-MAX_TAIL_CHARS:],
        "screenshots": screenshots,
        "logs": logs,
        "script_report": script_report,
    }
    _write_json(run_dir / "vini_run_report.json", report)
    _write_json(workspace_dir / "last_run.json", report)
    return report


def create_and_run_scripted_browser_task(
    *,
    task: str,
    start_url: str = "",
    plan: str | list[str] | None = None,
    script: str = "",
    timeout: int = 90,
) -> dict[str, Any]:
    created = create_scripted_browser_task(
        task=task,
        start_url=start_url,
        plan=plan,
        script=script,
    )
    if created["status"] == "script_required":
        return created
    run = run_scripted_browser_task(
        workspace_id=created["workspace_id"],
        timeout=timeout,
    )
    return {**created, "status": run["status"], "run": run, "ok": run["ok"]}


def _task_root() -> Path:
    return Path(files.get_abs_path(*TASK_ROOT_PARTS)).resolve()


def _safe_workspace_dir(workspace_id: str, *, must_exist: bool) -> Path:
    clean_id = str(workspace_id or "").strip()
    if not WORKSPACE_ID_PATTERN.fullmatch(clean_id):
        raise ScriptedBrowserTaskError("workspace_id is invalid")
    root = _task_root()
    workspace_dir = (root / clean_id).resolve()
    if not _is_relative_to(workspace_dir, root):
        raise ScriptedBrowserTaskError("workspace_id escapes the browser task root")
    if must_exist and not workspace_dir.is_dir():
        raise ScriptedBrowserTaskError(f"workspace does not exist: {clean_id}")
    return workspace_dir


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _new_workspace_id(task: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    slug = _slugify(task)[:48] or "browser-task"
    candidate = f"{stamp}-{slug}"
    root = _task_root()
    suffix = 1
    while (root / candidate).exists():
        suffix += 1
        candidate = f"{stamp}-{slug}-{suffix}"
    return candidate


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "task"


def _next_run_dir(workspace_dir: Path) -> Path:
    runs_dir = workspace_dir / "final_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    existing = []
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.startswith("run_"):
            try:
                existing.append(int(child.name.removeprefix("run_")))
            except ValueError:
                continue
    return runs_dir / f"run_{(max(existing) if existing else 0) + 1}"


def _format_plan(task: str, start_url: str, plan: str | list[str] | None) -> str:
    if isinstance(plan, list):
        plan_lines = [f"{idx}. {str(item).strip()}" for idx, item in enumerate(plan, 1) if str(item).strip()]
        plan_body = "\n".join(plan_lines)
    elif isinstance(plan, str) and plan.strip():
        plan_body = plan.strip()
    else:
        plan_body = (
            "1. Open the start URL if one is provided.\n"
            "2. Execute the browser workflow with Playwright.\n"
            "3. Save screenshots and logs in the run directory.\n"
            "4. Write report.json with the observed result and proof paths."
        )
    return (
        "# Scripted Browser Task\n\n"
        f"Task: {task}\n\n"
        f"Start URL: {start_url or '(none)'}\n\n"
        "## Plan\n\n"
        f"{plan_body}\n"
    )


def _normalize_script(script: str) -> str:
    text = str(script or "").strip()
    if not text:
        return ""
    if not text.endswith("\n"):
        text += "\n"
    return text


def _starter_script(task: str, start_url: str) -> str:
    task_json = json.dumps(task, ensure_ascii=True)
    start_url_json = json.dumps(start_url, ensure_ascii=True)
    return f'''from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

TASK = {task_json}
START_URL = {start_url_json}


async def main() -> int:
    run_dir = Path(os.environ.get("VINI_BROWSER_RUN_DIR", ".")).resolve()
    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "final_script_log.txt"

    report = {{
        "status": "script_required",
        "task": TASK,
        "start_url": START_URL,
        "screenshots": [],
        "log_path": str(log_path),
        "message": "Replace final_script.py with task-specific Playwright steps before treating this task as complete.",
    }}

    with log_path.open("w", encoding="utf-8") as log:
        log.write("Starter script created. It does not claim task completion.\\n")
        if START_URL:
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(viewport={{"width": 1280, "height": 1800}})
                    await page.goto(START_URL, wait_until="domcontentloaded", timeout=30000)
                    screenshot_path = screenshots_dir / "initial_page.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    await browser.close()
                    report["screenshots"].append(str(screenshot_path))
                    log.write(f"Captured initial page screenshot: {{screenshot_path}}\\n")
            except Exception as exc:
                report["status"] = "provider_gap"
                report["error"] = str(exc)
                log.write(f"Unable to capture starter screenshot: {{exc}}\\n")

    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "script_required" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def _collect_artifacts(root: Path, patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file():
                found.append(str(path))
    return sorted(set(found))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
