# Contributing To Vini AI

Vini AI is a real local-runtime product. Contributions should improve runtime correctness, user trust, and product quality without hiding setup gaps.

## Development Setup

```powershell
npm --prefix apps/desktop install
npm run desktop:dev
```

Build the local runtime image:

```powershell
docker build -f runtime\Dockerfile.vini-ai -t vini-ai/agent-runtime:local runtime
```

Run the runtime directly:

```powershell
docker run -d --name vini-ai-agent-zero --restart unless-stopped -p 50080:80 -v "$env:APPDATA\Vini AI\agent-zero\usr:/a0/usr" vini-ai/agent-runtime:local
```

## Engineering Rules

- Do not add fake, hardcoded, or mock runtime behavior.
- Do not claim a provider, connector, browser, model, or host bridge is configured unless the system can verify it.
- Preserve upstream Agent Zero licensing and attribution.
- Keep product code separate from upstream runtime code unless there is a deliberate integration reason.
- Keep user data, credentials, logs, and generated runtime artifacts out of tracked source.
- Prefer explicit setup errors over silent fallback behavior.

## Before Opening A Pull Request

Run what applies to your change:

```powershell
npm run desktop:build
python -m py_compile runtime/agent-zero/plugins/_vini_app_builder/helpers/builder.py
```

If your change touches Docker runtime behavior:

```powershell
docker build -f runtime\Dockerfile.vini-ai -t vini-ai/agent-runtime:local runtime
```

If your change touches UI:

- Verify `http://127.0.0.1:50080`.
- Check main chat, composer, Vini AI Computer, and relevant modal states.
- Confirm no text overlap at common desktop sizes.

## Pull Request Checklist

- The change is real and connected to runtime behavior where relevant.
- Missing setup states are honest.
- No credentials or user data are committed.
- Documentation is updated when behavior changes.
- Upstream attribution remains intact.
