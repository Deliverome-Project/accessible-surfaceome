"""Agent payload builder + create-or-update for the surface triage agent.

Pure-model inference: no custom tools, no builtins, no web search. The
agent emits a single ``TriageRecordDraft`` JSON object per gene from its
trained knowledge of human protein localization and topology. Designed to
be cheap and fast for genome-scale triage; the deep-dive agent picks up
verbatim-evidence work on the proteins triage flags.

Model: Claude Haiku 4.5 (smallest model that holds up on the benchmark).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anthropic import Anthropic

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Surface Accessibility Triage"
AGENT_MODEL = "claude-haiku-4-5"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "Pure-model per-protein triage of human surface accessibility. "
            "Emits a single TriageRecordDraft JSON (verdict yes/contextual/no "
            "+ structured reason). No tools, no web search."
        ),
        "model": AGENT_MODEL,
        "system": read_system_prompt(),
        # Tools-free: pure trained-knowledge inference. The orchestrator
        # registers no custom tools and no built-in toolset; the agent
        # cannot make tool calls. This keeps every triage run a single
        # short model turn.
        "tools": [],
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
