### connector_update
prepare or execute a connector update operation
arg: `connector_id` connector id
arg: `payload` object describing what to update
arg: `confirmed` boolean; required as `true` only after the user confirms the preview
returns confirmation-required preview for risky actions, or a real setup/unsupported result

Never set `confirmed: true` unless the user has confirmed the exact preview.

For API-key connectors without a named adapter, include an official HTTPS `url`, optional `method`, and `json` or `form` payload. The router will execute a real HTTP request with the stored connector credential after confirmation.

For MCP connectors, include `payload.tool_name` and `payload.args`; only use `confirmed: true` after user confirmation.
