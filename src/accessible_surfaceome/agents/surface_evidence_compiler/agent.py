"""Agent payload builder for the Surface Evidence Compiler (A1).

Stub only — see ``__init__.py`` for context. The payload shape mirrors
``surface_annotator.agent`` so the registry / upsert flow can address
this agent once the full v1.0.0 implementation lands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Surface Evidence Compiler (A1)"
AGENT_MODEL = "claude-sonnet-4-6"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "v1.0.0 deep-dive Compiler A1. Evidence-grounded write of the "
            "surface_evidence block: evidence_grade, methods (with permeabilization, "
            "expression_system, antibody validation, expression_observations), "
            "non_surface_expression, therapeutic_engagement, contradicting_evidence. "
            "Runs in parallel with biology_compiler; output feeds the synthesizer."
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
            # Custom tools land with v1.0.0 implementation: gene_lookup + gene_literature.
        ],
        "metadata": {
            "owner": "accessible-surfaceome",
            "managed_by": "src/accessible_surfaceome/agents/surface_evidence_compiler",
            "role": "compiler_a1",
            "schema_version": "v1.0.0-stub",
        },
    }
