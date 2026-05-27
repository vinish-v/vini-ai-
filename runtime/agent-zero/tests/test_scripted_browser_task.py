from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

files_stub = types.ModuleType("helpers.files")
files_stub.get_abs_path = lambda *parts: str(PROJECT_ROOT.joinpath(*parts))
sys.modules.setdefault("helpers.files", files_stub)


@dataclass
class _FakeResponse:
    message: str
    break_loop: bool
    additional: dict | None = None


class _FakeTool:
    def __init__(
        self,
        agent=None,
        name: str = "",
        method: str | None = None,
        args: dict | None = None,
        message: str = "",
        loop_data=None,
        **kwargs,
    ) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args or {}
        self.message = message
        self.loop_data = loop_data


tool_stub = types.ModuleType("helpers.tool")
tool_stub.Response = _FakeResponse
tool_stub.Tool = _FakeTool
sys.modules.setdefault("helpers.tool", tool_stub)

from plugins._browser.helpers import scripted_task
from plugins._browser.helpers.scripted_task import (
    ScriptedBrowserTaskError,
    create_and_run_scripted_browser_task,
    create_scripted_browser_task,
    run_scripted_browser_task,
)


def _patch_task_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "agent-zero"

    def fake_get_abs_path(*parts: str) -> str:
        return str(root.joinpath(*parts))

    monkeypatch.setattr(scripted_task.files, "get_abs_path", fake_get_abs_path)
    return root / "usr" / "browser_tasks"


def test_create_without_script_returns_script_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    task_root = _patch_task_root(monkeypatch, tmp_path)

    result = create_scripted_browser_task(
        task="Capture the homepage proof",
        start_url="https://example.com",
    )

    workspace = Path(result["workspace"])
    assert result["ok"] is True
    assert result["status"] == "script_required"
    assert workspace.is_relative_to(task_root)
    assert (workspace / "plan.md").read_text(encoding="utf-8").startswith(
        "# Scripted Browser Task"
    )
    assert "script_required" in (workspace / "final_script.py").read_text(
        encoding="utf-8"
    )
    assert json.loads((workspace / "task.json").read_text(encoding="utf-8"))[
        "status"
    ] == "script_required"


def test_create_and_run_collects_real_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_task_root(monkeypatch, tmp_path)
    script = """
from pathlib import Path
import json
import os

run_dir = Path(os.environ["VINI_BROWSER_RUN_DIR"])
(run_dir / "proof.log").write_text("finished\\n", encoding="utf-8")
(run_dir / "report.json").write_text(json.dumps({"status": "completed", "proof": "ok"}), encoding="utf-8")
print("script completed")
"""

    result = create_and_run_scripted_browser_task(
        task="Write proof artifacts",
        script=script,
        timeout=10,
    )

    run = result["run"]
    run_dir = Path(run["run_dir"])
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert run["exit_code"] == 0
    assert "script completed" in run["stdout_tail"]
    assert str(run_dir / "proof.log") in run["logs"]
    assert run["script_report"] == {"status": "completed", "proof": "ok"}
    assert (run_dir / "vini_run_report.json").is_file()


def test_run_rejects_invalid_workspace_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_task_root(monkeypatch, tmp_path)

    with pytest.raises(ScriptedBrowserTaskError, match="invalid"):
        run_scripted_browser_task(workspace_id="../outside")


def test_tool_returns_json_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_task_root(monkeypatch, tmp_path)
    sys.modules.pop("tools.scripted_browser_task", None)
    module = importlib.import_module("tools.scripted_browser_task")
    tool = module.ScriptedBrowserTask(
        agent=None,
        name="scripted_browser_task",
        method=None,
        args={},
        message="",
        loop_data=None,
    )

    response = asyncio.run(
        tool.execute(
            mode="create",
            task="Create a browser proof workspace",
        )
    )
    payload = json.loads(response.message)

    assert response.break_loop is False
    assert payload["ok"] is True
    assert payload["status"] == "script_required"
