from __future__ import annotations

import json
from typing import Any


def normalize_payload(value: dict | str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any]
    if isinstance(value, dict):
        payload = dict(value)
    elif isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            payload = {"text": value}
    else:
        payload = {}

    for key, item in (extra or {}).items():
        if key in {"confirmed"} or item is None:
            continue
        if key not in payload:
            payload[key] = item
    return payload
