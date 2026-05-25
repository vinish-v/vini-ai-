# Vini App Builder

Vini App Builder is the local Manus-style website builder inside Vini Computer. It is not an IDE shell and it does not use VSCodium. The builder runs in the existing Vini AI runtime container and writes projects under `/a0/usr/projects`.

## Runtime Capability

- Plugin: `runtime/agent-zero/plugins/_vini_app_builder`
- Tool name: `vini_app_builder`
- Project root: `/a0/usr/projects/<projectId>`
- Manifest: `/a0/usr/projects/<projectId>/vini-project.json`
- Export root: `/a0/usr/exports`
- Preview route: `/vini-preview/<projectId>/`
- ZIP route: `/vini-builder/export/<projectId>`

The v1 generated app target is Vite + React + TypeScript. Builder actions create real files, run real package/build commands, capture stdout/stderr and exit codes in `vini-builder.log`, update the manifest, start a per-project dev server, and proxy the preview through the authenticated runtime WebUI.

## Vini Computer Surface

The Build surface is registered in the existing right canvas beside Browser and Desktop. It provides:

- Prompt handoff to Vini AI with instructions to use `vini_app_builder`.
- Direct project creation for a starter Vite project.
- Project list and status from real manifests.
- Build, preview, and export actions backed by runtime API calls.
- Live preview iframe pointed at `/vini-preview/<projectId>/`.
- File list and proof log from the project workspace.

Fresh `vini_app_builder` tool results auto-open the Build surface. Existing browser/search auto-open behavior is unchanged.

## Failure Behavior

The builder must surface real blockers:

- Missing package manager or install failure appears as a failed command with stderr and exit code.
- Broken generated code fails build/typecheck and leaves the project status failed.
- Preview startup or verification failure is recorded in the manifest and log.
- Export failure returns a runtime error instead of a fake ZIP.

Cloud deploy, GitHub sync, domains, payment setup, and hosted databases are intentionally out of scope for v1.
