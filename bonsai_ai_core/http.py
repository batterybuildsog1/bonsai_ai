"""Tiny JSON-over-HTTP helpers with stdlib only."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib import error, request

from .errors import ProviderError


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int = 600,  # 10 minutes — complex buildings need time, quality over speed
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code} calling {url}: {body}") from exc
    except error.URLError as exc:
        raise ProviderError(f"Network error calling {url}: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Upstream response was not valid JSON: {body[:500]}") from exc

