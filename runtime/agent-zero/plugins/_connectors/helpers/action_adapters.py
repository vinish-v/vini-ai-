from __future__ import annotations

import base64
import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


SPECIALIZED_ACTIONS: dict[str, set[str]] = {
    "github": {"search", "read", "create", "update"},
    "slack": {"search", "read", "send", "update", "delete"},
    "stripe": {"search", "read", "create"},
    "supabase": {"search", "read"},
    "vercel": {"search", "read"},
    "airtable": {"search", "read", "create", "update", "delete"},
    "linear": {"search", "read", "create", "update", "delete"},
    "todoist": {"search", "read", "create", "update", "delete"},
    "resend": {"read", "send"},
    "firecrawl": {"search", "read"},
    "apify": {"search", "read", "create"},
    "telegram": {"send"},
    "email": {"send"},
    "outlook-mail": {"send"},
}


def supported_actions(connector_id: str) -> list[str]:
    return sorted(SPECIALIZED_ACTIONS.get(connector_id, set()))


def run(
    manifest: Any,
    action: str,
    payload: dict[str, Any],
    env: dict[str, str],
    *,
    plugin_config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    connector_id = str(manifest.id)
    if connector_id == "github":
        return _github(action, payload, env)
    if connector_id == "slack":
        return _slack(action, payload, env)
    if connector_id == "stripe":
        return _stripe(action, payload, env)
    if connector_id == "supabase":
        return _supabase(action, payload, env)
    if connector_id == "vercel":
        return _vercel(action, payload, env)
    if connector_id == "airtable":
        return _airtable(action, payload, env)
    if connector_id == "linear":
        return _linear(action, payload, env)
    if connector_id == "todoist":
        return _todoist(action, payload, env)
    if connector_id == "resend":
        return _resend(action, payload, env)
    if connector_id == "firecrawl":
        return _firecrawl(action, payload, env)
    if connector_id == "apify":
        return _apify(action, payload, env)
    if connector_id == "telegram":
        return _telegram(action, payload, plugin_config or {})
    if connector_id in {"email", "outlook-mail"}:
        return _email(action, payload, plugin_config or {})
    if str(getattr(manifest, "auth", "")) == "api_key":
        return _generic_api(manifest, action, payload, env)
    return None


def _github(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    token = _require_key(env, "GITHUB_TOKEN")
    headers = _bearer_headers(token, accept="application/vnd.github+json")
    headers["X-GitHub-Api-Version"] = "2022-11-28"
    base = "https://api.github.com"
    if action == "search":
        query = _required(payload, "query")
        kind = str(payload.get("kind") or "repositories").strip().lower()
        if kind in {"issue", "issues", "pulls", "prs"}:
            return _result("github", action, _http_json("GET", f"{base}/search/issues?{_qs(q=query, per_page=_limit(payload))}", headers))
        return _result("github", action, _http_json("GET", f"{base}/search/repositories?{_qs(q=query, per_page=_limit(payload))}", headers))
    if action == "read":
        repo = str(payload.get("repo") or payload.get("repository") or "").strip()
        if not repo:
            return _result("github", action, _http_json("GET", f"{base}/user/repos?{_qs(per_page=_limit(payload), sort='updated')}", headers))
        if payload.get("issue_number") or payload.get("issue"):
            issue = payload.get("issue_number") or payload.get("issue")
            return _result("github", action, _http_json("GET", f"{base}/repos/{repo}/issues/{issue}", headers))
        if payload.get("path"):
            path = urllib.parse.quote(str(payload["path"]).strip())
            ref = str(payload.get("ref") or "").strip()
            suffix = f"?{_qs(ref=ref)}" if ref else ""
            return _result("github", action, _http_json("GET", f"{base}/repos/{repo}/contents/{path}{suffix}", headers))
        return _result("github", action, _http_json("GET", f"{base}/repos/{repo}/issues?{_qs(state=payload.get('state') or 'open', per_page=_limit(payload))}", headers))
    if action == "create":
        repo = _required(payload, "repo")
        body = {"title": _required(payload, "title"), "body": str(payload.get("body") or "")}
        labels = payload.get("labels")
        if isinstance(labels, list):
            body["labels"] = labels
        return _result("github", action, _http_json("POST", f"{base}/repos/{repo}/issues", headers, json_body=body))
    if action == "update":
        repo = _required(payload, "repo")
        issue = payload.get("issue_number") or payload.get("issue")
        if not issue:
            raise ValueError("GitHub update requires issue_number.")
        fields = {k: v for k, v in payload.items() if k in {"title", "body", "state", "labels", "assignees"}}
        return _result("github", action, _http_json("PATCH", f"{base}/repos/{repo}/issues/{issue}", headers, json_body=fields))
    return None


def _slack(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "SLACK_BOT_TOKEN"))
    base = "https://slack.com/api"
    if action in {"search", "read"}:
        channel = str(payload.get("channel") or "").strip()
        if channel:
            data = _http_json("GET", f"{base}/conversations.history?{_qs(channel=channel, limit=_limit(payload))}", headers)
        else:
            data = _http_json("GET", f"{base}/conversations.list?{_qs(limit=_limit(payload), types=payload.get('types') or 'public_channel,private_channel')}", headers)
        return _result("slack", action, data)
    if action == "send":
        return _result("slack", action, _http_json("POST", f"{base}/chat.postMessage", headers, json_body={"channel": _required(payload, "channel"), "text": _required(payload, "text")}))
    if action == "update":
        return _result("slack", action, _http_json("POST", f"{base}/chat.update", headers, json_body={"channel": _required(payload, "channel"), "ts": _required(payload, "ts"), "text": _required(payload, "text")}))
    if action == "delete":
        return _result("slack", action, _http_json("POST", f"{base}/chat.delete", headers, json_body={"channel": _required(payload, "channel"), "ts": _required(payload, "ts")}))
    return None


def _stripe(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _basic_headers(_require_key(env, "STRIPE_API_KEY"))
    base = "https://api.stripe.com/v1"
    if action in {"search", "read"}:
        resource = str(payload.get("resource") or "balance").strip().strip("/")
        allowed = {"balance", "customers", "payment_intents", "charges", "invoices", "subscriptions"}
        if resource not in allowed:
            raise ValueError(f"Stripe read resource must be one of: {', '.join(sorted(allowed))}.")
        return _result("stripe", action, _http_json("GET", f"{base}/{resource}?{_qs(limit=_limit(payload, default=10))}", headers))
    if action == "create":
        resource = str(payload.get("resource") or "customers").strip().strip("/")
        if resource != "customers":
            raise ValueError("Stripe create currently supports resource='customers' only.")
        form = {k: v for k, v in payload.items() if k in {"email", "name", "description", "phone"}}
        return _result("stripe", action, _http_json("POST", f"{base}/customers", headers, form=form))
    return None


def _supabase(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "SUPABASE_ACCESS_TOKEN"))
    base = "https://api.supabase.com/v1"
    if action in {"search", "read"}:
        project_ref = str(payload.get("project_ref") or "").strip()
        if project_ref:
            return _result("supabase", action, _http_json("GET", f"{base}/projects/{project_ref}", headers))
        return _result("supabase", action, _http_json("GET", f"{base}/projects", headers))
    return None


def _vercel(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "VERCEL_TOKEN"))
    team = str(payload.get("team_id") or "").strip()
    team_qs = {"teamId": team} if team else {}
    base = "https://api.vercel.com"
    if action in {"search", "read"}:
        resource = str(payload.get("resource") or "projects").strip()
        path = "/v9/projects" if resource == "projects" else "/v6/deployments"
        return _result("vercel", action, _http_json("GET", f"{base}{path}?{_qs(limit=_limit(payload), **team_qs)}", headers))
    return None


def _airtable(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "AIRTABLE_API_KEY"))
    base_id = _required(payload, "base_id")
    table = urllib.parse.quote(_required(payload, "table"))
    base = f"https://api.airtable.com/v0/{base_id}/{table}"
    if action in {"search", "read"}:
        params = {"maxRecords": _limit(payload)}
        if payload.get("view"):
            params["view"] = payload["view"]
        if payload.get("filterByFormula"):
            params["filterByFormula"] = payload["filterByFormula"]
        return _result("airtable", action, _http_json("GET", f"{base}?{_qs(**params)}", headers))
    if action == "create":
        return _result("airtable", action, _http_json("POST", base, headers, json_body={"records": _records(payload)}))
    if action == "update":
        return _result("airtable", action, _http_json("PATCH", base, headers, json_body={"records": _records(payload)}))
    if action == "delete":
        record_id = _required(payload, "record_id")
        return _result("airtable", action, _http_json("DELETE", f"{base}/{record_id}", headers))
    return None


def _linear(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "LINEAR_API_KEY"))
    endpoint = "https://api.linear.app/graphql"
    if action in {"search", "read"}:
        query = """
        query ConnectorIssues($first: Int!) {
          viewer { id name email }
          issues(first: $first, orderBy: updatedAt) { nodes { id identifier title state { name } assignee { name } updatedAt url } }
        }
        """
        return _result("linear", action, _http_json("POST", endpoint, headers, json_body={"query": query, "variables": {"first": _limit(payload)}}))
    if action == "create":
        mutation = "mutation IssueCreate($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier title url } } }"
        fields = {"teamId": _required(payload, "team_id"), "title": _required(payload, "title")}
        for src, dst in (("description", "description"), ("assignee_id", "assigneeId"), ("project_id", "projectId"), ("priority", "priority")):
            if payload.get(src) is not None:
                fields[dst] = payload[src]
        return _result("linear", action, _http_json("POST", endpoint, headers, json_body={"query": mutation, "variables": {"input": fields}}))
    if action == "update":
        mutation = "mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success issue { id identifier title url } } }"
        fields = {k: payload[k] for k in ("title", "description", "priority") if k in payload}
        return _result("linear", action, _http_json("POST", endpoint, headers, json_body={"query": mutation, "variables": {"id": _required(payload, "issue_id"), "input": fields}}))
    if action == "delete":
        mutation = "mutation IssueDelete($id: String!) { issueDelete(id: $id) { success } }"
        return _result("linear", action, _http_json("POST", endpoint, headers, json_body={"query": mutation, "variables": {"id": _required(payload, "issue_id")}}))
    return None


def _todoist(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "TODOIST_API_TOKEN"))
    base = "https://api.todoist.com/rest/v2"
    if action in {"search", "read"}:
        resource = str(payload.get("resource") or "tasks").strip()
        if resource not in {"tasks", "projects", "sections", "labels"}:
            raise ValueError("Todoist resource must be tasks, projects, sections, or labels.")
        return _result("todoist", action, _http_json("GET", f"{base}/{resource}", headers))
    if action == "create":
        return _result("todoist", action, _http_json("POST", f"{base}/tasks", headers, json_body={k: v for k, v in payload.items() if k in {"content", "description", "project_id", "section_id", "parent_id", "order", "labels", "priority", "due_string", "due_date", "due_datetime", "due_lang", "assignee_id"}}))
    if action == "update":
        task_id = _required(payload, "task_id")
        return _result("todoist", action, _http_json("POST", f"{base}/tasks/{task_id}", headers, json_body={k: v for k, v in payload.items() if k not in {"task_id"}}))
    if action == "delete":
        return _result("todoist", action, _http_json("DELETE", f"{base}/tasks/{_required(payload, 'task_id')}", headers))
    return None


def _resend(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "RESEND_API_KEY"))
    base = "https://api.resend.com"
    if action == "read":
        return _result("resend", action, _http_json("GET", f"{base}/domains", headers))
    if action == "send":
        body = {
            "from": _required(payload, "from"),
            "to": payload.get("to") if isinstance(payload.get("to"), list) else [_required(payload, "to")],
            "subject": _required(payload, "subject"),
            "text": str(payload.get("text") or payload.get("body") or ""),
        }
        if payload.get("html"):
            body["html"] = payload["html"]
        return _result("resend", action, _http_json("POST", f"{base}/emails", headers, json_body=body))
    return None


def _firecrawl(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "FIRECRAWL_API_KEY"))
    base = "https://api.firecrawl.dev/v1"
    if action == "read":
        body = {"url": _required(payload, "url")}
        if payload.get("formats"):
            body["formats"] = payload["formats"]
        return _result("firecrawl", action, _http_json("POST", f"{base}/scrape", headers, json_body=body))
    if action == "search":
        return _result("firecrawl", action, _http_json("POST", f"{base}/search", headers, json_body={"query": _required(payload, "query"), "limit": _limit(payload)}))
    return None


def _apify(action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    headers = _bearer_headers(_require_key(env, "APIFY_TOKEN"))
    base = "https://api.apify.com/v2"
    if action in {"search", "read"}:
        if payload.get("dataset_id"):
            return _result("apify", action, _http_json("GET", f"{base}/datasets/{payload['dataset_id']}/items?{_qs(limit=_limit(payload))}", headers))
        return _result("apify", action, _http_json("GET", f"{base}/acts?{_qs(limit=_limit(payload))}", headers))
    if action == "create":
        actor_id = _required(payload, "actor_id")
        return _result("apify", action, _http_json("POST", f"{base}/acts/{urllib.parse.quote(actor_id, safe='~')}/runs", headers, json_body=payload.get("input") or {}))
    return None


def _telegram(action: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    if action != "send":
        return None
    bot_cfg = _selected_bot(config, payload.get("bot"))
    if not bot_cfg:
        raise ValueError("Telegram send requires a configured bot in the Telegram plugin.")
    token = _required(bot_cfg, "token")
    chat_id = _required(payload, "chat_id")
    text = _required(payload, "text")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _result("telegram", action, _http_json("POST", url, {}, json_body={"chat_id": chat_id, "text": text, "parse_mode": payload.get("parse_mode") or None}))


def _email(action: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    if action != "send":
        return None
    handler = _selected_email_handler(config, payload.get("handler"))
    if not handler:
        raise ValueError("Email send requires a configured Email integration handler.")
    msg = MIMEMultipart("alternative")
    body = str(payload.get("body") or payload.get("text") or "")
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if payload.get("html"):
        msg.attach(MIMEText(str(payload["html"]), "html", "utf-8"))
    msg["From"] = str(payload.get("from") or handler.get("username") or "")
    msg["To"] = _required(payload, "to")
    msg["Subject"] = _required(payload, "subject")
    server_name = _required(handler, "smtp_server")
    port = int(handler.get("smtp_port") or 587)
    username = _required(handler, "username")
    password = _required(handler, "password")
    with smtplib.SMTP(server_name, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(username, password)
        server.send_message(msg)
    return {"ok": True, "connector": "email", "action": action, "result": {"sent": True, "to": msg["To"], "subject": msg["Subject"]}}


def _generic_api(manifest: Any, action: str, payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any] | None:
    url = str(payload.get("url") or "").strip()
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" and not payload.get("allow_http"):
        raise ValueError("Generic connector HTTP actions require an https URL unless allow_http=true.")
    token = _first_key(env, getattr(manifest, "env_keys", ()))
    headers = dict(payload.get("headers") or {})
    if token and not any(key.lower() == "authorization" for key in headers):
        auth_header = str(payload.get("auth_header") or "Authorization")
        auth_prefix = str(payload.get("auth_prefix") or "Bearer")
        headers[auth_header] = token if auth_header.lower() != "authorization" else f"{auth_prefix} {token}".strip()
    method = str(payload.get("method") or _default_method(action)).upper()
    body = payload.get("body")
    json_body = payload.get("json")
    data = _http_json(method, url, headers, json_body=json_body, form=payload.get("form"), raw_body=body)
    return _result(str(manifest.id), action, data, generic=True)


def _http_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    *,
    json_body: Any = None,
    form: dict[str, Any] | None = None,
    raw_body: Any = None,
    timeout: int = 30,
) -> dict[str, Any]:
    headers = dict(headers or {})
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        data = urllib.parse.urlencode({k: v for k, v in form.items() if v is not None}).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif raw_body is not None:
        data = raw_body if isinstance(raw_body, bytes) else str(raw_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status_code": response.status, "body": _parse_response(text)}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status_code": exc.code, "body": _parse_response(text), "error": str(exc)}
    except urllib.error.URLError as exc:
        return {"ok": False, "status_code": 0, "error": str(exc)}


def _result(connector: str, action: str, data: dict[str, Any], *, generic: bool = False) -> dict[str, Any]:
    return {
        "ok": bool(data.get("ok")),
        "status": "executed" if data.get("ok") else "request_failed",
        "label": "Executed" if data.get("ok") else "Request failed",
        "connector_id": connector,
        "action": action,
        "generic_http": generic,
        "http_status": data.get("status_code"),
        "data": data.get("body"),
        "error": data.get("error"),
    }


def _parse_response(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return text[:20000]


def _bearer_headers(token: str, *, accept: str = "application/json") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": accept}


def _basic_headers(secret: str) -> dict[str, str]:
    token = base64.b64encode(f"{secret}:".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _required(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required field: {key}")
    return str(value).strip()


def _require_key(env: dict[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise ValueError(f"Missing required credential: {key}")
    return value


def _first_key(env: dict[str, str], keys: tuple[str, ...] | list[str]) -> str:
    for key in keys:
        if env.get(key):
            return env[key]
    return ""


def _qs(**params: Any) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return urllib.parse.urlencode(clean, doseq=True)


def _limit(payload: dict[str, Any], default: int = 20) -> int:
    try:
        value = int(payload.get("limit") or payload.get("per_page") or default)
    except Exception:
        value = default
    return max(1, min(value, 100))


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records")
    if isinstance(records, list):
        return records
    if isinstance(payload.get("fields"), dict):
        record: dict[str, Any] = {"fields": payload["fields"]}
        if payload.get("record_id"):
            record["id"] = payload["record_id"]
        return [record]
    raise ValueError("Airtable action requires records or fields.")


def _selected_bot(config: dict[str, Any], name: Any) -> dict[str, Any] | None:
    bots = config.get("bots") if isinstance(config, dict) else []
    if not isinstance(bots, list):
        return None
    for bot in bots:
        if not isinstance(bot, dict) or bot.get("enabled") is False:
            continue
        if not name or bot.get("name") == name:
            return bot
    return None


def _selected_email_handler(config: dict[str, Any], name: Any) -> dict[str, Any] | None:
    handlers = config.get("handlers") if isinstance(config, dict) else []
    if not isinstance(handlers, list):
        return None
    for handler in handlers:
        if not isinstance(handler, dict) or handler.get("enabled") is False:
            continue
        if not name or handler.get("name") == name:
            return handler
    return None


def _default_method(action: str) -> str:
    if action in {"create", "send"}:
        return "POST"
    if action == "update":
        return "PATCH"
    if action == "delete":
        return "DELETE"
    return "GET"
