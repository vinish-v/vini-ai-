### scripted_browser_task
repeatable browser automation lane that creates a task workspace with `plan.md`,
`final_script.py`, per-run logs, screenshots, stdout/stderr, and a run report

arg: `task` required natural-language task description when creating a workspace
arg: `start_url` optional URL the script should begin from
arg: `plan` optional string or list of plan steps to write into `plan.md`
arg: `script` optional complete Python Playwright script to write as `final_script.py`
arg: `mode` optional `create`, `run`, or `create_and_run` (default)
arg: `workspace_id` required only for `mode: run`
arg: `timeout` optional run timeout in seconds

Use this when a browser workflow should be reproducible, audited, rerun, or
handed off as a durable artifact. It is best for scripted tasks, regression
proof, download flows, multi-step forms that need a saved script, and final
evidence.

Use `browser` instead when the user needs live watched interaction, takeover,
cursor/action streaming, or the current visible tab. Use `extract_page` first
for read-only page content. Do not claim success unless the script actually ran
and the returned report proves the intended outcome.

If you call this without `script`, it will create the workspace and starter
script only. That result is `script_required`; write a real task-specific
`final_script.py` before treating the work as complete.

example create and run:
~~~json
{
  "tool_name": "scripted_browser_task",
  "tool_args": {
    "mode": "create_and_run",
    "task": "Open example.com and capture proof",
    "start_url": "https://example.com",
    "script": "from pathlib import Path\nimport json, os\nrun_dir = Path(os.environ['VINI_BROWSER_RUN_DIR'])\n(run_dir / 'report.json').write_text(json.dumps({'status':'completed'}), encoding='utf-8')\n"
  }
}
~~~
