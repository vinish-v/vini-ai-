from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_MAX_CHARS = 16000
USER_AGENT = "ViniAI/1.0 (+local browser extraction)"
BLOCKED_PATTERNS = (
    r"\bcloudflare\b",
    r"\bcaptcha\b",
    r"\bverify you are human\b",
    r"\bare you a robot\b",
    r"\baccess denied\b",
)


class ReadableHtmlParser(HTMLParser):
    def __init__(self, *, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.links: list[dict[str, str]] = []
        self.headings: list[dict[str, str]] = []
        self.forms: list[dict[str, Any]] = []
        self._parts: list[str] = []
        self._skip_depth = 0
        self._current_heading: dict[str, str] | None = None
        self._current_link: dict[str, str] | None = None
        self._current_form: dict[str, Any] | None = None
        self._title_open = False
        self._textarea_open = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._title_open = True
        elif tag == "meta" and attrs_dict.get("name", "").lower() == "description":
            self.description = _normalize_text(attrs_dict.get("content", ""))[:500]
        elif tag in {"p", "div", "section", "article", "main", "li", "tr", "br"}:
            self._parts.append("\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")
            self._current_heading = {
                "level": tag,
                "text": "",
                "selector": _stable_selector(tag, attrs_dict),
            }
        elif tag == "a":
            href = _absolute_url(attrs_dict.get("href", ""), self.base_url)
            self._current_link = {
                "url": href,
                "text": "",
                "selector": _stable_selector(tag, attrs_dict),
            }
        elif tag == "form":
            self._current_form = {
                "action": _absolute_url(attrs_dict.get("action", ""), self.base_url),
                "method": (attrs_dict.get("method") or "get").lower(),
                "selector": _stable_selector(tag, attrs_dict),
                "fields": [],
            }
        elif tag in {"input", "select", "textarea", "button"} and self._current_form is not None:
            self._current_form["fields"].append(
                {
                    "tag": tag,
                    "type": attrs_dict.get("type", ""),
                    "name": attrs_dict.get("name", ""),
                    "placeholder": attrs_dict.get("placeholder", ""),
                    "selector": _stable_selector(tag, attrs_dict),
                }
            )
            if tag == "textarea":
                self._textarea_open = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._title_open = False
        elif tag in {"p", "div", "section", "article", "main", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")
        if self._current_heading and tag == self._current_heading["level"]:
            text = _normalize_text(self._current_heading.get("text", ""))
            if text:
                self.headings.append({**self._current_heading, "text": text})
            self._current_heading = None
        if tag == "a" and self._current_link:
            text = _normalize_text(self._current_link.get("text", ""))
            if self._current_link.get("url") and text:
                self.links.append({**self._current_link, "text": text})
            self._current_link = None
        if tag == "form" and self._current_form:
            self.forms.append(self._current_form)
            self._current_form = None
        if tag == "textarea":
            self._textarea_open = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _normalize_text(data)
        if not text:
            return
        if self._title_open:
            self.title = _normalize_text(f"{self.title} {text}")[:300]
        if self._current_heading is not None:
            self._current_heading["text"] = f"{self._current_heading.get('text', '')} {text}"
        if self._current_link is not None:
            self._current_link["text"] = f"{self._current_link.get('text', '')} {text}"
        if self._textarea_open and self._current_form and self._current_form["fields"]:
            self._current_form["fields"][-1]["value_hint"] = text[:200]
        self._parts.append(f"{text} ")

    def readable_text(self) -> str:
        text = html.unescape("".join(self._parts))
        lines = [_normalize_text(line) for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()


def extract_page(
    url: str,
    *,
    timeout: int | float = DEFAULT_TIMEOUT_SECONDS,
    max_chars: int = DEFAULT_MAX_CHARS,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized_url = _require_http_url(url)
    started = time.time()
    request_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }
    req = urllib.request.Request(normalized_url, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(1, float(timeout))) as response:
            raw = response.read(min(max(1024, int(max_chars) * 8), 2_000_000))
            status_code = int(getattr(response, "status", 0) or 0)
            final_url = response.geturl() or normalized_url
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read(12000).decode("utf-8", errors="replace")
        return _error_result(normalized_url, "http_error", str(exc), status_code=exc.code, body=body)
    except urllib.error.URLError as exc:
        return _error_result(normalized_url, "request_failed", str(exc))

    text = raw.decode(_charset_from_content_type(content_type), errors="replace")
    parser = ReadableHtmlParser(base_url=final_url)
    parser.feed(text)
    readable = parser.readable_text()
    blocked = _blocked_reason(readable or text)
    content = readable[:max(1, int(max_chars))]
    fingerprint_source = _normalize_text(content).lower()
    return {
        "ok": not bool(blocked) and bool(content),
        "status": "blocked" if blocked else "extracted" if content else "empty",
        "url": normalized_url,
        "final_url": final_url,
        "http_status": status_code,
        "content_type": content_type,
        "title": parser.title,
        "description": parser.description,
        "content": content,
        "content_length": len(content),
        "fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest() if fingerprint_source else "",
        "blocked_reason": blocked,
        "headings": parser.headings[:40],
        "links": _dedupe_links(parser.links)[:80],
        "forms": parser.forms[:12],
        "selector_hints": _selector_hints(parser),
        "extraction_mode": "static_html",
        "duration_ms": round((time.time() - started) * 1000),
    }


def _error_result(url: str, status: str, error: str, *, status_code: int = 0, body: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "url": url,
        "final_url": url,
        "http_status": status_code,
        "content": "",
        "error": error,
        "blocked_reason": _blocked_reason(body),
        "extraction_mode": "static_html",
    }


def _require_http_url(url: str) -> str:
    value = str(url or "").strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("extract_page requires an http(s) URL.")
    return value


def _absolute_url(value: str, base_url: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    return urllib.parse.urljoin(base_url, value)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_selector(tag: str, attrs: dict[str, str]) -> str:
    if attrs.get("id"):
        return f"{tag}#{attrs['id']}"
    if attrs.get("name"):
        return f"{tag}[name='{attrs['name']}']"
    if attrs.get("aria-label"):
        return f"{tag}[aria-label='{attrs['aria-label'][:80]}']"
    classes = [item for item in str(attrs.get("class", "")).split() if item][:2]
    return tag + ("." + ".".join(classes) if classes else "")


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", str(content_type or ""), re.I)
    return match.group(1).strip('"') if match else "utf-8"


def _blocked_reason(text: str) -> str:
    haystack = str(text or "").lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, haystack, re.I):
            return pattern.strip(r"\b")
    return ""


def _dedupe_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for link in links:
        url = str(link.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(link)
    return out


def _selector_hints(parser: ReadableHtmlParser) -> dict[str, list[str]]:
    return {
        "headings": [item["selector"] for item in parser.headings if item.get("selector")][:20],
        "links": [item["selector"] for item in parser.links if item.get("selector")][:20],
        "forms": [item["selector"] for item in parser.forms if item.get("selector")][:12],
    }
