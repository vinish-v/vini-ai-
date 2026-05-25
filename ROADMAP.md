# Vini AI Roadmap

This roadmap tracks the public direction for Vini AI. The priority is real runtime capability before cosmetic completeness.

## Current Milestone: Local Runtime Product Baseline

- Keep the Vini AI runtime buildable from `runtime/Dockerfile.vini-ai`.
- Keep the desktop app connected to real Docker, HTTP, and filesystem state.
- Preserve Agent Zero attribution and license files.
- Keep runtime user data outside tracked source.
- Make setup failures visible instead of pretending success.

## Milestone 1: Workspace Polish

- Finish the Manus-inspired chat/composer layout without breaking existing actions.
- Keep file upload, send, voice, speaker, model, agent, pause, compact, and nudge behavior intact.
- Make Vini AI Computer resize the chat area predictably.
- Keep the right-side computer toggle minimal and placed consistently.
- Remove nonessential top-right status clutter from the main workspace.

## Milestone 2: Vini AI Computer

- Show live browser pages the agent visits, not only snippets in chat.
- Keep browser search visible through the Vini AI Computer surface.
- Improve desktop presentation into a cleaner Vini OS experience.
- Keep browser, desktop, editor, and build surfaces inside one coherent computer frame.
- Add task progress and completion evidence directly beside the active computer surface.

## Milestone 3: Connectors

- Add a connector catalog with logos, descriptions, setup requirements, and connection status.
- Use direct browser sign-in only where the provider allows it.
- Use API key setup for providers that do not support embedded or automated auth.
- Add honest provider-specific blocker states for OAuth rejection, CAPTCHA, missing keys, or missing scopes.
- Add remote access grouping for WhatsApp, Telegram, and Email flows.

## Milestone 4: Voice Conversation

- Stabilize real VAD for barge-in.
- Keep speech-to-text warm so it does not reload models for every turn.
- Add a dedicated voice model selection path separate from the default chat model.
- Target short responses and low token caps for voice mode.
- Make latency visible in logs: VAD end, STT done, LLM first token, TTS first audio.

## Milestone 5: Windows Host Bridge

- Harden scoped folder access.
- Add approval gates for writes, deletes, and command execution.
- Add audit logging for host bridge requests.
- Make allowed folders editable from the desktop settings UI.
- Keep bridge failure states explicit inside the runtime.

## Milestone 6: Release Readiness

- Package the Windows installer.
- Verify install, launch, runtime start, restart, and uninstall behavior.
- Confirm user data persists unless explicitly removed.
- Add release notes and signed artifacts.
- Publish a clean setup guide with screenshots.

## Non-Goals For Now

- No fake connector success.
- No mock browser or desktop surfaces.
- No forced provider default.
- No cloud dependency unless explicitly chosen later.
- No replacing upstream license or attribution files.
