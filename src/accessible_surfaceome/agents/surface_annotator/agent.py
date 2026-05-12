"""Agent payload builder + create-or-update for the surface annotator.

Built-in toolset: keep ``read``, ``grep``, ``glob``, ``web_fetch``, ``web_search``;
disable ``bash``, ``write``, ``edit`` — the orchestrator owns all persistence.
The agent never needs to mutate the container's filesystem; it works through
the ``gene_lookup`` custom tool and emits a single JSON block as its final
response.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .tool_registry import custom_tool_definitions

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Surface Proteome Annotator"
# v0.4.0 refocus: default to Sonnet 4.6 (was Opus 4.7). The refocused
# schema is small enough that a single Sonnet agent should handle it,
# at ~5x lower cost per gene. Override via the orchestrator if Opus is
# wanted for a specific run.
AGENT_MODEL = "claude-sonnet-4-6"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "Annotates human cell-surface proteins by querying the M1 candidate "
            "universe and UniProt through custom tools. Emits one GeneAnnotation "
            "JSON record per gene."
        ),
        "model": AGENT_MODEL,
        "system": read_system_prompt(),
        "tools": [
            {
                "type": "agent_toolset_20260401",
                "default_config": {"enabled": False},
                "configs": [
                    {"name": "read", "enabled": True},
                    {"name": "grep", "enabled": True},
                    {"name": "glob", "enabled": True},
                    {"name": "web_fetch", "enabled": True},
                    {"name": "web_search", "enabled": True},
                ],
            },
            *custom_tool_definitions(),
        ],
        "metadata": {
            "owner": "accessible-surfaceome",
            "managed_by": "src/accessible_surfaceome/agents/surface_annotator",
        },
    }


def upsert_agent(
    client: Anthropic,
    *,
    current_id: str | None,
    current_version: int | None,
):
    """Create the agent if absent, otherwise update in place.

    Returns the live agent object so the caller can persist ``id`` + ``version``
    to the registry. Agent array fields (``tools``) are fully replaced on
    update — always send the complete desired set.
    """

    payload = build_agent_payload()
    if current_id is None:
        return client.beta.agents.create(**payload)
    if current_version is None:
        # We're tracking the agent but lost the version pin; refresh from the API.
        current = client.beta.agents.retrieve(current_id)
        current_version = getattr(current, "version", None)
    if current_version is None:
        raise RuntimeError(
            f"agent {current_id} has no version on the API; cannot update without a version precondition"
        )
    return client.beta.agents.update(current_id, version=current_version, **payload)
