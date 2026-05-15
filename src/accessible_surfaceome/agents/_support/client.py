"""Anthropic SDK client factory.

The SDK reads ``ANTHROPIC_API_KEY`` from the environment and sets the
``managed-agents-2026-04-01`` beta header automatically on every
``client.beta.{agents,environments,sessions,vaults,memory_stores}.*`` call —
no need to pass it manually.
"""

from __future__ import annotations

import httpx
from anthropic import Anthropic

# The managed-agent session event stream (``sessions.events.stream``) is a
# long-poll SSE connection that idles between events while the model
# generates or runs a tool. A short read timeout makes those idle gaps
# surface as ``httpx.ReadTimeout`` mid-run. Give the stream a generous read
# budget; ``connect`` stays short so a genuinely unreachable API still
# fails fast.
_AGENT_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)


def get_client() -> Anthropic:
    return Anthropic(timeout=_AGENT_TIMEOUT)
