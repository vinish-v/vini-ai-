# Vini AI Technical Report

## Summary

Vini AI is a Windows desktop AI agent application built from a local desktop shell and a Dockerized Vini AI runtime forked from Agent Zero. The product focuses on real runtime behavior, visible computer activity, local persistence, and controlled host-machine access.

## System Components

### Desktop Shell

- Location: `apps/desktop`
- Stack: Electron, Vite, React, TypeScript
- Responsibilities:
  - Launch the desktop product.
  - Hide unnecessary native menu chrome.
  - Check Docker availability.
  - Start and stop the runtime container.
  - Probe runtime health.
  - Expose a constrained preload API.
  - Run the local Windows host bridge.

### Runtime

- Location: `runtime/agent-zero`
- Stack: Python, Flask, Agent Zero lineage
- Responsibilities:
  - Serve the Vini AI web UI.
  - Manage chats, tools, providers, plugins, and projects.
  - Run browser and desktop automation surfaces.
  - Persist user/runtime state under `/a0/usr`.

### Docker Image

- Location: `runtime/Dockerfile.vini-ai`
- Image: `vini-ai/agent-runtime:local`
- Container: `vini-ai-agent-zero`
- Host URL: `http://127.0.0.1:50080`

### Vini AI Computer

The Vini AI Computer is the user-visible work surface for browser, desktop, editor, and build activity. It should show real runtime work rather than static screenshots or fake progress.

### Windows Host Bridge

The host bridge runs on loopback from the desktop main process. It exposes scoped file and command operations to the runtime with token auth and approval gates.

## Data And Persistence

Tracked source should not contain runtime user data. Runtime state is mapped from:

```text
%APPDATA%/Vini AI/agent-zero/usr
```

to:

```text
/a0/usr
```

inside the container.

## Security Model

- Provider credentials remain user-provided.
- Connector setup must be real before showing connected state.
- Host file operations are limited to configured scopes.
- Mutating host actions require approval.
- Missing setup should return explicit errors.

## Main Risks

- OAuth providers can reject embedded or automated browsers.
- Voice latency depends on STT, LLM, and TTS warm paths.
- Docker build time and image size can slow onboarding.
- Browser automation can hit CAPTCHA or anti-bot walls.
- Host command execution must remain auditable and gated.

## Verification Strategy

- Build desktop TypeScript.
- Build Docker runtime image.
- Start container and verify health.
- Use browser verification against `http://127.0.0.1:50080`.
- Test provider missing-key states.
- Test persistence after restart.
- Test Windows installer before release.
