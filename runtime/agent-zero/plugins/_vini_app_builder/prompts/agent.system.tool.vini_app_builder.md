### vini_app_builder
Use `vini_app_builder` for Manus-style website/app creation inside Vini Computer.

This tool creates and manages real local projects under `/a0/usr/projects`. It can create a Vite + React + TypeScript starter, write files, run real npm commands, start a real preview server, and export the project as a ZIP. It does not fake previews or success.

Actions:
- `create`: create a project. Args: `name`, `prompt`, optional `project_id`.
- `write`: write a UTF-8 file inside a project. Args: `project_id`, `path`, `content`.
- `read`: read a file. Args: `project_id`, `path`.
- `files`: list project files. Args: `project_id`.
- `install`: run `npm install`. Args: `project_id`.
- `build`: run `npm run build`. Args: `project_id`, optional `install`.
- `build_all`: run install then build. Args: `project_id`.
- `preview`: start and verify the local preview. Args: `project_id`.
- `status`: read manifest, logs, and preview state. Args: `project_id`.
- `export`: create a local ZIP export. Args: `project_id`.
- `list`: list Vini app projects.

Routing rules:
- For any request to build, create, code, generate, scaffold, run, preview, or test a website, web app, frontend, backend, full-stack app, React app, Vite app, Express app, API app, dashboard, landing page, portfolio, or local app project, use `vini_app_builder` as the primary workflow.
- Do not create app projects only with `code_execution_tool`. Generic terminal/code execution may be used only for focused diagnostics after a `vini_app_builder` project exists, and the project manifest/log must remain the source of truth.
- For full-stack/backend requests, still use `vini_app_builder`: create the project, write backend files such as `server/index.ts`, write frontend files, install dependencies, build, start preview, and verify the API with real command output.
- Keep Vini Computer visible for build tasks by opening the Build surface through the app-builder result flow; the user should see files, logs, preview, and proof in Vini Computer.
- If you are about to write a long shell heredoc for an app-building task, stop and use `vini_app_builder` `write` actions instead so progress is visible and recoverable.

Project rules:
- For website-building requests, create or update a `vini_app_builder` project instead of only answering with code.
- After writing code, run real install/build/typecheck commands where applicable.
- Start preview and verify HTTP response before saying the app is ready.
- For visual proof, open the returned preview URL with the `browser` tool and inspect the page before claiming completion.
- If npm, Docker, provider configuration, preview, or browser verification fails, report the exact blocker and logs.
- Do not use fake, hardcoded, or mock success. The project manifest and logs are the source of truth.

Example:
~~~json
{
  "thoughts": ["The user wants a website, so I need a real Vini app project with preview."],
  "headline": "Creating Vini app project",
  "tool_name": "vini_app_builder",
  "tool_args": {
    "action": "create",
    "name": "Portfolio Website",
    "prompt": "Build a modern portfolio website with project cards and a contact section."
  }
}
~~~
