### windows_host_bridge
Use the Vini AI Windows host bridge for real host-machine access from the desktop app.
This tool is for scoped Windows folders only. It never grants full-disk access.

Actions:
- `status`: check bridge availability and allowed folders
- `list`: list a scoped Windows folder
- `stat`: inspect scoped host file/folder metadata
- `exists`: check if a scoped host path exists
- `read`: read a UTF-8 text file in a scoped folder
- `write`: create/overwrite/append a UTF-8 text file in a scoped folder, approval required
- `mkdir`: create a scoped folder, approval required
- `delete`: delete a scoped path, approval required
- `run`: execute a PowerShell command from a scoped working directory, approval required
- `import`: copy a scoped Windows file into Vini AI's runtime workspace
- `export`: copy a Vini AI runtime file back to a scoped Windows path, approval required
- `open`: open a scoped Windows file with its default Windows app, approval required
- `office_status`: detect installed Microsoft Word, Excel, and PowerPoint
- `office_open`: open a scoped Windows file in native Microsoft Office, approval required

Rules:
- Prefer scoped file operations over command execution when possible.
- For Office-compatible in-app work, import DOCX/XLSX/PPTX first, then use `office_artifact` and Vini Desktop/LibreOffice.
- Use native Microsoft Office only when the user explicitly asks for Word, Excel, or PowerPoint on Windows.
- Native Office opens on the user's Windows desktop, not inside the Vini Xpra live view.
- Use `status` before first use to see allowed Windows folders.
- For `run`, always set `cwd` to one of the allowed project/work folders.
- Command execution is approval-gated and starts in scoped cwd, but the Windows shell is not a filesystem sandbox. Do not claim otherwise.
- If approval is denied, explain the blocker and ask the user to approve a narrower action.

Examples:
~~~json
{
  "thoughts": ["I need to see which Windows folders Vini AI can access."],
  "headline": "Checking Windows host access",
  "tool_name": "windows_host_bridge",
  "tool_args": {
    "action": "status"
  }
}
~~~

~~~json
{
  "thoughts": ["I can list the scoped project folder directly through the host bridge."],
  "headline": "Listing Windows folder",
  "tool_name": "windows_host_bridge",
  "tool_args": {
    "action": "list",
    "path": "C:\\Users\\HP\\Documents"
  }
}
~~~

~~~json
{
  "thoughts": ["The user asked me to run a host command, so I need approval through the bridge."],
  "headline": "Running approved Windows command",
  "tool_name": "windows_host_bridge",
  "tool_args": {
    "action": "run",
    "cwd": "C:\\Users\\HP\\Documents",
    "command": "Get-ChildItem -Force",
    "timeout_ms": 30000
  }
}
~~~
