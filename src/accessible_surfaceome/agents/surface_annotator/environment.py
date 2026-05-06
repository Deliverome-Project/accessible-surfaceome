"""Environment payload builder for the surface annotator.

The agent does not mount any repos or files — every upstream call routes
through the ``gene_lookup`` custom tool that runs in the orchestrator process,
not the cloud container. The container only needs network access for the
agent's built-in ``web_fetch`` / ``web_search`` fallback tools, so we run
``unrestricted`` for v0. Tighten when a real production lane appears.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

ENVIRONMENT_NAME = "surface-annotator-py-3-12"


def build_environment_payload() -> dict[str, Any]:
    return {
        "name": ENVIRONMENT_NAME,
        "config": {
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
        "metadata": {
            "managed_by": "src/accessible_surfaceome/agents/surface_annotator",
        },
    }


def environment_config_blob() -> str:
    """Canonical serialization for sha256 drift detection in the registry."""

    payload = build_environment_payload()
    return json.dumps(payload, sort_keys=True)


def upsert_environment(
    client: Anthropic,
    *,
    current_id: str | None,
):
    """Create the environment if absent. Environments are not Anthropic-versioned;
    we recreate when the local config sha changes (orchestrator handles that).
    """

    payload = build_environment_payload()
    if current_id is None:
        return client.beta.environments.create(**payload)
    return client.beta.environments.update(current_id, **payload)
