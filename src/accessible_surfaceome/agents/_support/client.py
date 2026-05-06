"""Anthropic SDK client factory.

The SDK reads ``ANTHROPIC_API_KEY`` from the environment and sets the
``managed-agents-2026-04-01`` beta header automatically on every
``client.beta.{agents,environments,sessions,vaults,memory_stores}.*`` call —
no need to pass it manually.
"""

from __future__ import annotations

from anthropic import Anthropic


def get_client() -> Anthropic:
    return Anthropic()
