"""HTTP client for ClevAgent API.

Uses `requests` (only external dependency) with a 5-second timeout and 1 retry.
X-API-Key auth header is set automatically from _state.
"""

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger("clevagent")

_TIMEOUT = 5   # seconds per request
_RETRIES = 1   # retry once on network error


def send_heartbeat(
    endpoint: str,
    api_key: str,
    agent: str,
    **payload: Any,
) -> Optional[dict]:
    """
    POST /api/v1/heartbeat.

    Returns the parsed JSON response on success, or None on failure.
    Never raises — all errors are logged as warnings.
    """
    url = f"{endpoint}/api/v1/heartbeat"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    body = {"agent": agent, **{k: v for k, v in payload.items() if v is not None}}

    last_err: Optional[Exception] = None
    for attempt in range(_RETRIES + 1):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            last_err = exc
            if attempt < _RETRIES:
                logger.debug("Heartbeat attempt %d failed, retrying: %s", attempt + 1, exc)

    logger.warning(
        "Heartbeat failed after %d attempt(s) — agent=%s error=%s",
        _RETRIES + 1, agent, last_err,
    )
    return None
