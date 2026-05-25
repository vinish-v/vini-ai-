# Vini AI Windows Host Bridge

Vini AI Desktop starts a local Windows host bridge at `127.0.0.1:50180`.
The Docker runtime receives only:

- `VINI_HOST_BRIDGE_URL=http://host.docker.internal:50180`
- `VINI_HOST_BRIDGE_TOKEN=<generated local token>`

The token is generated in the desktop user-data directory and is not committed.

## Scope

The default scoped folders are derived from the signed-in Windows user:

- Documents
- Desktop
- Downloads
- Vini AI runtime `workdir`
- Vini AI runtime `projects`

Edit `host-bridge.json` in the Vini AI desktop user-data directory to change
the scope list or approval requirements.

## Approval Gates

The bridge allows read-only folder listing and text-file reads inside scoped
folders. These actions are path-gated.

The following actions require a visible Windows approval dialog:

- PowerShell command execution
- File write or append
- Folder creation
- Delete

Command execution starts in a scoped working directory, but the Windows shell is
not a filesystem sandbox. Vini AI surfaces this limitation instead of claiming
stronger isolation than Windows provides.

## Agent Tool

The runtime tool is `windows_host_bridge`.

Supported actions:

- `status`
- `list`
- `read`
- `write`
- `mkdir`
- `delete`
- `run`

If the desktop bridge is unavailable, the tool returns an explicit setup error.
