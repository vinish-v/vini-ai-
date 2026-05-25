# Security Policy

Vini AI controls local runtime, browser automation, connector setup, and optional Windows host access. Security issues should be handled carefully and privately.

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` | Active development |

## Report A Vulnerability

Do not open a public issue for sensitive security reports.

Use GitHub private vulnerability reporting if enabled on the repository, or contact the repository owner directly with:

- A clear description of the issue.
- Steps to reproduce.
- Impact and affected files.
- Whether credentials, host files, browser sessions, or command execution are involved.

## High-Risk Areas

- Windows host bridge command execution.
- Scoped filesystem reads and writes.
- Connector auth flows and API keys.
- Browser session reuse.
- Runtime container mounts.
- Provider credentials.
- Voice/audio data capture.

## Security Expectations

- Host operations must be scoped and approval-gated.
- The runtime must surface missing or unsafe setup states honestly.
- Secrets must never be committed.
- Logs should avoid printing credentials, auth headers, access tokens, or raw session cookies.
- Connector flows must not pretend a connection exists until there is a real credential, token, or session.

## False Positive Secret Scanning

Vendored JavaScript bundles can trigger false positives. Confirm the exact file and token context before closing alerts. Close only as false positive when the value is clearly code text, test data, or documentation placeholder.
