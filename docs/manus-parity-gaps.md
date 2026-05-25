# Manus Parity Gaps

This document tracks the major product gaps between Vini AI and a polished Manus-style agent workspace.

## 1. Task Lifecycle

Current gap:

- Vini AI can run agent work, but task planning, progress, recovery, and proof of completion need stronger product structure.

Improvements:

- Add a clear task progress card.
- Track plan, active step, evidence, blockers, and completion artifacts.
- Persist task status across restarts.
- Show what the agent did, what it used, and why it stopped.

## 2. Visible Computer Work

Current gap:

- Browser/search work can still appear as chat snippets instead of visible page visits.

Improvements:

- Always open source pages in Vini AI Computer for browser/search tasks.
- Show active URL, page title, and action feed.
- Keep browser, desktop, editor, and build surfaces visually unified.
- Add reliable resize behavior when the computer opens.

## 3. Connectors

Current gap:

- Connector catalog and setup flows are still in progress.

Improvements:

- Add logos, descriptions, requirements, and status.
- Support API-key connectors where OAuth is unsuitable.
- Surface OAuth rejection and CAPTCHA as honest blockers.
- Add remote access section for WhatsApp, Telegram, and Email.

## 4. Voice Mode

Current gap:

- Voice conversation latency and reliability are not yet product-grade.

Improvements:

- Keep STT model warm.
- Use real VAD for barge-in.
- Use a dedicated fast voice LLM configuration.
- Stream TTS as early as possible.
- Add visible latency diagnostics.

## 5. Local Host Control

Current gap:

- Host bridge exists as a direction but needs hardening and UI.

Improvements:

- Add scoped folder editor.
- Add approval history.
- Add command templates and risk labels.
- Add audit logs.
- Add clear bridge unavailable states.

## 6. Release Polish

Current gap:

- Windows packaging path exists, but release flow needs full validation.

Improvements:

- Build installer on clean Windows machine.
- Add update path.
- Verify uninstall keeps user data.
- Add signed builds.
- Add public docs with screenshots and demo GIFs.

## Guiding Rule

Do not chase visual similarity at the cost of runtime truth. Vini AI should look polished, but every status and action must be backed by real system state.
