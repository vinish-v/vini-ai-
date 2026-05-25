# Vini AI - AGENTS.md

We are building Vini AI as a serious Windows desktop app with a real local Vini AI runtime.

- Never use fake, hardcoded, or mock runtime code in the codebase.
- Every setup check, runtime status, provider state, and Docker action must reflect real system state.
- Preserve upstream Agent Zero licensing and attribution.
- Keep product code separate from the upstream runtime clone unless there is a deliberate integration reason.
