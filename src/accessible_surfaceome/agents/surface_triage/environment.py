"""Environment payload builder for the surface triage agent.

Mirrors the deep-dive's environment: the agent doesn't mount any repos;
upstream calls go through the custom tools that run in the orchestrator
process. Only the built-in ``web_fetch`` / ``web_search`` need network,
so ``unrestricted`` is fine for v0.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

ENVIRONMENT_NAME = "surface-triage-py-3-12"


def build_environment_payload() -> dict[str, Any]:
    return {
        "name": ENVIRONMENT_NAME,
        "config": {
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
        "metadata": {
            "managed_by": "src/accessible_surfaceome/agents/surface_triage",
        },
    }


def environment_config_blob() -> str:
    payload = build_environment_payload()
    return json.dumps(payload, sort_keys=True)


def upsert_environment(
    client: Anthropic,
    *,
    current_id: str | None,
):
    payload = build_environment_payload()
    if current_id is None:
        return client.beta.environments.create(**payload)
    return client.beta.environments.update(current_id, **payload)
