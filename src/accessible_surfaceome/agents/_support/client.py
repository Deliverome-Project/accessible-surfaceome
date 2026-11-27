"""Anthropic SDK client factory.

The SDK reads ``ANTHROPIC_API_KEY`` from the environment and sets the
``managed-agents-2026-04-01`` beta header automatically on every
``client.beta.{agents,environments,sessions,vaults,memory_stores}.*`` call —
no need to pass it manually.
"""

from __future__ import annotations

import importlib

import anthropic
import httpx
from anthropic import Anthropic

# ``anthropic>=2`` switched its transport from ``httpx`` to ``httpx2`` and
# rejects ``httpx.Timeout``. Prefer ``anthropic.Timeout`` (or ``httpx2.Timeout``)
# when present so this factory works cleanly on both SDK 1.x and 2.x.
_TIMEOUT_CLS: type = getattr(anthropic, "Timeout", None) or httpx.Timeout
if getattr(anthropic, "Timeout", None) is None:
    try:
        _TIMEOUT_CLS = importlib.import_module("httpx2").Timeout
    except ImportError:
        pass

# The managed-agent session event stream (``sessions.events.stream``) is a
# long-poll SSE connection that idles between events while the model
# generates or runs a tool. A short read timeout makes those idle gaps
# surface as ``httpx.ReadTimeout`` mid-run. Give the stream a generous read
# budget; ``connect`` stays short so a genuinely unreachable API still
# fails fast.
_AGENT_TIMEOUT = _TIMEOUT_CLS(connect=10.0, read=600.0, write=30.0, pool=10.0)

# SDK default is 2. Real-world ANT-side TLS / connection blips happen mid-run
# (observed: APIConnectionError, "SSL: SSLV3_ALERT_BAD_RECORD_MAC") and an
# agentic run accumulates many ``messages.create`` calls, so any single
# blip can fail the whole run. 5 keeps us robust without masking sustained
# outages.
_AGENT_MAX_RETRIES = 5


def get_client() -> Anthropic:
    return Anthropic(timeout=_AGENT_TIMEOUT, max_retries=_AGENT_MAX_RETRIES)
