### connector_read
attempt a read-only connector operation through the universal connector router
arg: `connector_id` connector id
arg: `payload` optional object with provider-specific read details
returns real data only when an adapter exists; otherwise returns the exact setup or unsupported-action gap

For API-key connectors without a named adapter, pass an explicit official API `url`; the router will make a real HTTPS request using the saved connector credential. Do not invent data when the request returns an error.

Firecrawl has a named API adapter. Use `connector_id: "firecrawl"` with
`payload.operation` set to `scrape`, `search`, `crawl`, `map`,
`batch_scrape`, or `interact`. Missing key, quota, rate-limit, blocked endpoint,
and self-host URL states are returned honestly by the connector result.

For MCP connectors such as `serena` and `context7`, call `connector_status` first. If it reports `Ready for agent`, pass `payload.tool_name` (or `payload.mcp_tool`) and `payload.args` to execute a discovered MCP tool through this connector router.

example:
~~~json
{
  "thoughts": ["I should not fake inbox access; I will ask the connector router."],
  "headline": "Reading through connector",
  "tool_name": "connector_read",
  "tool_args": {
    "connector_id": "gmail",
    "payload": {"query": "unread today"}
  }
}
~~~
