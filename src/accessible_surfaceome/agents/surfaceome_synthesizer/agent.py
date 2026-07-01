"""Agent payload builder for the Synthesizer (B).

Stub only — see ``__init__.py`` for context. Built-in toolset is empty:
the Synthesizer is cite-only over the merged Compiler ledger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.model_config import deep_dive_model

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Surfaceome Synthesizer (B)"
AGENT_MODEL = deep_dive_model()  # SURFACEOME_DEEP_DIVE_MODEL override


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "v1.0.0 deep-dive Synthesizer. Integrates the A1 (surface_evidence) "
            "and A2 (biological_context) outputs plus deterministic_features into "
            "the executive_summary, filters (17 fields), accessibility_risks, "
            "confidence + confidence_reasoning. Cite-only — no tool access. The "
            "no-tools constraint is the load-bearing guarantee that every claim "
            "traces to the merged Compiler ledger."
        ),
        "model": AGENT_MODEL,
        "system": read_system_prompt(),
        "tools": [
            # No tools by design. Cite-only over A1 + A2's merged evidence ledger.
            {
                "type": "agent_toolset_20260401",
                "default_config": {"enabled": False},
                "configs": [
                    {"name": "read", "enabled": False},
                    {"name": "grep", "enabled": False},
                    {"name": "glob", "enabled": False},
                    {"name": "web_fetch", "enabled": False},
                    {"name": "web_search", "enabled": False},
                ],
            },
        ],
        "metadata": {
            "owner": "accessible-surfaceome",
            "managed_by": "src/accessible_surfaceome/agents/surfaceome_synthesizer",
            "role": "synthesizer_b",
            "schema_version": "v1.0.0-stub",
        },
    }
