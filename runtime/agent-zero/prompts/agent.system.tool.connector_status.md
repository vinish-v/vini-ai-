### connector_status
inspect Vini AI connector readiness, credential requirements, and honest setup gaps
arg: `connector_id` optional connector id such as `gmail`, `github`, `slack`, `my-browser`; omit for all connectors
returns manifest, auth mode, status, label, message, and actions

Use this before relying on a connector. Never claim a connector is connected unless this tool reports `verified`.

example:
~~~json
{
  "thoughts": ["I need to know whether Gmail is actually usable before reading mail."],
  "headline": "Checking connector status",
  "tool_name": "connector_status",
  "tool_args": {
    "connector_id": "gmail"
  }
}
~~~
