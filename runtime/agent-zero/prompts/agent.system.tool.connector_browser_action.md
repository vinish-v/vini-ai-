### connector_browser_action
open a connector's real browser fallback route in Vini AI Computer
arg: `connector_id` connector id
arg: `url` optional URL override; defaults to the connector sign-in or app URL
arg: `browser_action` optional; currently `open`
arg: `execute_browser` optional boolean, default true
returns connector fallback status and browser runtime result

For OAuth connectors without durable API support, explain that this is browser-session automation, not an API-connected durable connector.
