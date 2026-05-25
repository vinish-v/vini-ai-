# Vini AI Setup

## Prerequisites

- Windows 10/11
- Docker Desktop running
- Node.js 24+
- Git

## Install Desktop Dependencies

```powershell
npm --prefix apps/desktop install
```

## Run in Development

```powershell
npm run desktop:dev
```

The Vini AI window will show Docker status, container status, the Vini AI health probe, provider-key detection from local runtime data, recent runtime files, and Docker logs.

## Start the Runtime

Use the **Start** button in Vini AI. It builds the local rebranded runtime image when needed, then runs the real Docker container:

```powershell
docker build -f runtime\Dockerfile.vini-ai -t vini-ai/agent-runtime:local runtime
docker run -d --name vini-ai-agent-zero --restart unless-stopped -p 50080:80 -v "%APPDATA%\Vini AI\agent-zero\usr:/a0/usr" vini-ai/agent-runtime:local
```

Open the runtime at:

```text
http://127.0.0.1:50080
```

Configure models/providers inside Vini AI for v1. Vini AI does not force a provider default.
