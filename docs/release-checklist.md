# Vini AI Release Checklist

Use this checklist before cutting a Windows release.

## Source Check

- Working tree is clean.
- Upstream attribution and license files are present.
- No secrets, user data, logs, or generated runtime artifacts are tracked.
- README, setup docs, and changelog are updated.

## Desktop Build

```powershell
npm --prefix apps/desktop install
npm run desktop:build
npm run desktop:package
```

Verify:

- App launches from the packaged build.
- Native menu bar is hidden.
- Window title and branding say Vini AI.
- Runtime controls reflect real Docker state.

## Runtime Build

```powershell
docker build -f runtime\Dockerfile.vini-ai -t vini-ai/agent-runtime:local runtime
```

Verify:

- Image builds successfully.
- Container starts.
- `http://127.0.0.1:50080` loads.
- Health probe succeeds.

## Functional Smoke Test

- Start Vini AI Desktop.
- Start runtime from desktop shell.
- Open the runtime UI.
- Create a new chat.
- Configure a real model/provider.
- Run a simple task.
- Run a browser/search task and verify visible pages open.
- Open Vini AI Computer.
- Open connector settings.
- Test missing-provider and missing-connector states.

## Persistence Test

- Change settings.
- Create a project or chat.
- Restart the app.
- Restart the container.
- Confirm settings, chats, projects, and workdir state survive.

## Security Test

- Confirm host bridge token is not committed.
- Confirm scoped folder restrictions apply.
- Confirm command execution requires approval.
- Confirm connector errors do not print secrets.

## Installer Test

- Install from the generated Windows setup file.
- Launch from Start Menu.
- Start runtime.
- Close and reopen.
- Uninstall.
- Confirm user data remains unless explicitly removed.

## Release Notes

Include:

- Version.
- New features.
- Known limitations.
- Setup requirements.
- Upgrade notes.
- Attribution note for Agent Zero lineage.
