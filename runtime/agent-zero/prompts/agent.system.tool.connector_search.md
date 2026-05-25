### connector_search
search available Vini AI connectors and their current capabilities
arg: `query` optional text such as `mail`, `github`, `calendar`, `payment`
arg: `connector_type` optional UI type: `built-in`, `api-key`, `oauth`, `plugin`, `mcp`
arg: `auth` optional auth mode: `built_in`, `api_key`, `oauth`, `plugin`, `mcp`
returns matching connector manifests with real status labels

example:
~~~json
{
  "thoughts": ["I need to find message-capable connectors."],
  "headline": "Searching connectors",
  "tool_name": "connector_search",
  "tool_args": {
    "query": "mail"
  }
}
~~~
