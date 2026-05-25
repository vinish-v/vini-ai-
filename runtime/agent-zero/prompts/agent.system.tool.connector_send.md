### connector_send
prepare or execute an external send operation such as email, chat, SMS, posts, or notifications
arg: `connector_id` connector id
arg: `payload` object containing recipient/channel/body or equivalent details
arg: `confirmed` boolean; required as `true` only after the user confirms the preview
returns confirmation-required preview for risky sends, or a real setup/unsupported result

Never send silently. Always show the preview and wait for user confirmation before using `confirmed: true`.

Examples of real adapter payloads:
- Slack: `connector_id`, `channel`, `text`
- Telegram: `connector_id`, `chat_id`, `text`
- Resend: `connector_id`, `from`, `to`, `subject`, `text`
- Email: `connector_id`, `to`, `subject`, `body`

For MCP connectors that expose send-like tools, include `payload.tool_name` and `payload.args`; only use `confirmed: true` after user confirmation.
