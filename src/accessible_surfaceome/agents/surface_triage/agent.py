"""Agent payload builder + create-or-update for the surface triage agent.

Sonnet-driven, lightweight cousin of the surface_annotator. Same toolset
(``gene_lookup``, ``patent_lookup``, ``gene_literature``); the *prompt*
enforces the lightweight tool-use budget rather than restricting tools.

Built-in toolset: keep ``read``, ``grep``, ``glob``, ``web_fetch``,
``web_search``; disable ``bash``, ``write``, ``edit`` — the orchestrator
owns persistence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anthropic import Anthropic

# Triage-local tool registry: same custom tools as the deep dive, but the
# gene_lookup handler is wrapped to filter `patent_handle` and `deeptmhmm`
# out of the db_panel view (see surface_triage/tool_registry.py).
from .tool_registry import custom_tool_definitions

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Surface Accessibility Triage"
AGENT_MODEL = "claude-sonnet-4-6"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "Lightweight per-protein triage that decides whether a deep-dive "
            "annotation is warranted. Emits one TriageRecordDraft JSON per "
            "gene (verdict + accessibility_signal + evidence)."
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
            "managed_by": "src/accessible_surfaceome/agents/surface_triage",
        },
    }


def upsert_agent(
    client: Anthropic,
    *,
    current_id: str | None,
    current_version: int | None,
):
    payload = build_agent_payload()
    if current_id is None:
        return client.beta.agents.create(**payload)
    if current_version is None:
        current = client.beta.agents.retrieve(current_id)
        current_version = getattr(current, "version", None)
    if current_version is None:
        raise RuntimeError(
            f"agent {current_id} has no version on the API; cannot update without a version precondition"
        )
    return client.beta.agents.update(current_id, version=current_version, **payload)
