"""NCBI E-utilities API-key helpers.

The pipeline can run with either one key (``NCBI_API_KEY``) or a shared,
comma/whitespace-separated key pool (``NCBI_API_KEYS``). Callers should use
``next_ncbi_api_key`` or the small param/URL helpers here instead of reading
``os.environ`` directly, so key rotation and rate limiting stay consistent.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.parse
from collections.abc import MutableMapping
from typing import Any

_SPLIT_RE = re.compile(r"[\s,;]+")
_LOCK = threading.Lock()
_STATE: tuple[tuple[str, ...], int] = ((), 0)


def ncbi_api_keys() -> tuple[str, ...]:
    """Configured NCBI API keys, deduped in deterministic order.

    ``NCBI_API_KEYS`` is the preferred multi-key setting. ``NCBI_API_KEY`` is
    appended for backward compatibility, so existing single-key environments
    keep working and a local key can be included in the pool without changing
    old scripts.
    """

    raw_values = [
        os.environ.get("NCBI_API_KEYS", ""),
        os.environ.get("NCBI_API_KEY", ""),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_values:
        for token in _SPLIT_RE.split(raw.strip()):
            key = token.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
    return tuple(out)


def next_ncbi_api_key() -> str | None:
    """Return the next key in a process-local round-robin, or ``None``.

    The state resets automatically when the env-provided key tuple changes,
    which keeps tests and long-lived REPL sessions predictable.
    """

    keys = ncbi_api_keys()
    if not keys:
        return None
    global _STATE
    with _LOCK:
        state_keys, idx = _STATE
        if state_keys != keys:
            state_keys, idx = keys, 0
        key = state_keys[idx % len(state_keys)]
        _STATE = (state_keys, idx + 1)
        return key


def add_ncbi_api_key_param(params: MutableMapping[str, Any]) -> None:
    """Mutate ``params`` to include a rotated ``api_key`` when configured."""

    key = next_ncbi_api_key()
    if key:
        params["api_key"] = key


def with_ncbi_api_key_url(url: str) -> str:
    """Append a rotated ``api_key`` query parameter when configured."""

    key = next_ncbi_api_key()
    if not key:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}api_key={urllib.parse.quote(key)}"


__all__ = [
    "add_ncbi_api_key_param",
    "ncbi_api_keys",
    "next_ncbi_api_key",
    "with_ncbi_api_key_url",
]
