from __future__ import annotations

import json
from typing import Any

from helpers.tool import Response, Tool
from plugins._browser.helpers.scripted_task import (
    ScriptedBrowserTaskError,
    create_and_run_scripted_browser_task,
    create_scripted_browser_task,
    run_scripted_browser_task,
)


class ScriptedBrowserTask(Tool):
    async def execute(
        self,
        task: str = "",
        start_url: str = "",
        plan: str | list[str] | None = None,
        script: str = "",
        mode: str = "create_and_run",
        workspace_id: str = "",
        timeout: int = 90,
        **_: Any,
    ) -> Response:
        try:
            normalized_mode = str(mode or "create_and_run").strip().lower()
            if normalized_mode == "create":
                result = create_scripted_browser_task(
                    task=task,
                    start_url=start_url,
                    plan=plan,
                    script=script,
                )
            elif normalized_mode == "run":
                result = run_scripted_browser_task(
                    workspace_id=workspace_id,
                    timeout=timeout,
                )
            elif normalized_mode in {"create_and_run", "create-run", "run_new"}:
                result = create_and_run_scripted_browser_task(
                    task=task,
                    start_url=start_url,
                    plan=plan,
                    script=script,
                    timeout=timeout,
                )
            else:
                raise ScriptedBrowserTaskError(
                    "mode must be create, run, or create_and_run"
                )
        except Exception as exc:
            result = {
                "ok": False,
                "status": "failed",
                "mode": mode,
                "workspace_id": workspace_id,
                "error": str(exc),
            }

        return Response(
            message=json.dumps(result, indent=2, ensure_ascii=False),
            break_loop=False,
        )
