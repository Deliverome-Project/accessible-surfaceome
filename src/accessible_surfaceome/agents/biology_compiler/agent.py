"""Agent payload builder for the Biology Compiler (A2).

Stub only — see ``__init__.py`` for context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"

AGENT_NAME = "Biology Compiler (A2)"
AGENT_MODEL = "claude-sonnet-4-6"


def read_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text()


def build_agent_payload() -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": (
            "v1.0.0 deep-dive Compiler A2. Evidence-grounded write of the "
            "biological_context block: tissues (expression-level enum × disease_context), "
            "cell_types, cell_states, subcellular_localization, anatomical_accessibility, "
            "and accessibility_modulation with triage-aligned cell_state_trigger / "
            "restricted_lineage / dual_loc_partner_compartment sub-enums. Runs in "
            "parallel with surface_evidence_compiler; output feeds the synthesizer."
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
            "managed_by": "src/accessible_surfaceome/agents/biology_compiler",
            "role": "compiler_a2",
            "schema_version": "v1.0.0-stub",
        },
    }
