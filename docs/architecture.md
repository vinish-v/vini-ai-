# Vini AI Architecture

Vini AI is a Windows desktop shell around the real Vini AI runtime.

## Runtime Boundary

- `runtime/agent-zero` is the rebranded Vini AI runtime forked from `agent0ai/agent-zero`.
- Vini AI does not mock runtime APIs or replace model/provider configuration in v1.
- The desktop app controls the runtime through Docker CLI commands and HTTP health probes.
- Runtime data is mounted into `/a0/usr` from the Electron user data directory, not stored in tracked source.
- The local Docker image is built as `vini-ai/agent-runtime:local` from `runtime/Dockerfile.vini-ai`.

## Desktop App

- `apps/desktop` is an Electron + Vite + React app.
- The main process owns Docker orchestration and filesystem access.
- The renderer only talks through a constrained preload API exposed as `window.vini`.
- Runtime status cards are derived from real Docker, HTTP, and local file checks.
- The main process also starts a token-authenticated Windows host bridge on loopback.
  The runtime can use it only through scoped folders and approval-gated actions.
  Details are in [windows-host-bridge.md](./windows-host-bridge.md).

## Vini AI Computer

- The live computer surface is the real Agent Zero/Vini AI browser runtime, not a mock preview.
- Browser pages are driven through Playwright inside the runtime container.
- The browser viewer streams real Chromium screencast frames over the runtime WebSocket API.
- Agent browser actions emit `browser_viewer_action` events so active viewers can show live cursor/action markers for clicks, typing, navigation, scrolling, and form interactions.
- Browser automation exposes a structured observe loop with URL/title, visible interactive refs, focused element, forms, page errors, recent actions, and optional screenshot/content. Ref-based click/type/form actions validate that targets still exist, are visible, enabled, and current before acting.
- Read-only web extraction uses a fast static extraction lane before heavier browser control. It returns content fingerprints, headings, links, forms, selector hints, and honest blocked/error states; JavaScript-heavy or blocked pages must fall back to Vini Browser or a configured connector.
- Firecrawl remains an external API connector. Vini routes Firecrawl through the configured hosted/self-hosted v2 API for search, scrape, crawl, map, batch scrape, and action-based page extraction; AGPL server internals are not copied.
- Fresh browser and search actions auto-open the live Browser surface when browser autofocus is enabled, so the user sees work as it happens instead of finding screenshots after the task.
- The live Browser surface includes stream status, measured frame cadence, point overlays, and a compact action feed backed by runtime events.
- Full Windows desktop control remains gated behind the scoped host bridge and computer-use backend. If that backend is not armed or connected, Vini AI must report that setup gap instead of pretending OS-level control is available.
- The Build surface is a Manus-style local website-builder surface inside Vini Computer, not an IDE. It uses the runtime `_vini_app_builder` plugin to create projects under `/a0/usr/projects`, run real install/build/typecheck/dev-server commands, proxy live previews through `/vini-preview/<projectId>/`, record proof in `vini-project.json` and `vini-builder.log`, and export local ZIPs. Details are in [vini-app-builder.md](./vini-app-builder.md).

## Default Runtime Contract

- Container name: `vini-ai-agent-zero`
- Docker image: `vini-ai/agent-runtime:local`
- Base image lineage: `agent0ai/agent-zero:latest`
- Host URL: `http://127.0.0.1:50080`
- Container web port: `80`
- Data mount: `%APPDATA%/Vini AI/agent-zero/usr` to `/a0/usr`
- Host bridge URL inside Docker: `http://host.docker.internal:50180`
