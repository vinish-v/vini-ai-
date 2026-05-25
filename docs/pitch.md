# Vini AI Pitch

## One-Liner

Vini AI is a Windows desktop AI agent workspace that runs a real local runtime, controls a visible computer surface, and helps users complete browser, file, coding, and automation tasks with honest setup states.

## Problem

Most agent apps look impressive but fail when the user needs real work:

- Browser activity is hidden or reduced to summaries.
- Provider and connector setup is unclear.
- Local file and command access is either missing or unsafe.
- Voice mode is slow or unreliable.
- Desktop apps often wrap a web UI without real runtime control.

## Solution

Vini AI combines a local desktop shell with a Docker-backed runtime:

- The desktop app starts, stops, monitors, and opens the runtime.
- The runtime performs real agent work through browser, desktop, tools, and provider APIs.
- Vini AI Computer shows browser, desktop, editor, and builder surfaces.
- Connectors expose honest auth requirements and setup states.
- The Windows host bridge adds scoped local access with approval gates.

## Why It Matters

The product direction is closer to a practical AI operator than a chat app. The user should see what the agent is doing, understand what is blocked, and keep control over local machine access.

## Target Users

- Developers building and debugging local projects.
- Operators who need browser and document workflows automated.
- Power users who want local runtime ownership.
- Teams experimenting with desktop-first agent workflows.

## Differentiators

- Local Docker runtime instead of a mock backend.
- Visible computer surface for browser and desktop work.
- Honest provider, connector, and host-access states.
- Windows-first desktop packaging path.
- Scoped host bridge instead of unrestricted local access.

## Current Stage

Vini AI is in early product development. The baseline runtime and desktop shell exist, while UI polish, connectors, voice mode, and release hardening are still active work.
