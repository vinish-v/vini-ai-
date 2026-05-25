# Vini AI Verification

## Baseline Checks

```powershell
git -C runtime/agent-zero status --short
npm --prefix apps/desktop run build
```

## Runtime Checks

1. Start Docker Desktop.
2. Launch Vini AI with `npm run desktop:dev`.
3. Confirm Docker CLI and Docker daemon cards are green.
4. Press **Start**.
5. Confirm the container card reports `running`.
6. Confirm the health card reports HTTP 200 from `http://127.0.0.1:50080/api/health`.
7. Press **Open** and complete Vini AI onboarding/provider configuration inside the runtime UI.
8. Press **Load logs** and confirm logs come from the real `vini-ai-agent-zero` container.

## Blocker Scenarios

- Docker missing: Vini AI must report Docker CLI not found.
- Docker stopped: Vini AI must report daemon unavailable.
- Container not created: Vini AI must report that the runtime has not been created yet.
- Container stopped: Vini AI must report stopped status and allow restart.
- Provider not configured: Vini AI must report that no provider key was detected in mounted runtime data.
