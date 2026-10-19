"""Ask one model (Opus or Sonnet) to grade intrinsic endocytic propensity from
sequence + topology. Model-parameterized because ``call_builder`` is Sonnet-locked."""

from __future__ import annotations

import hashlib
from typing import Any, TypeVar

from pydantic import BaseModel

from accessible_surfaceome.agents._support.structured_call import (  # re-exported for callers
    MAX_REPAIRS as MAX_REPAIRS,
    MAX_TOKENS as MAX_TOKENS,
    SONNET_MODEL as SONNET_MODEL,
    call_model_structured as call_model_structured,
    extract_json_object as extract_json_object,
)
from accessible_surfaceome.agents.internalization.models import (
    MODEL_PRIOR_PROMPT_VERSION,
    ModelPriorLLMOut,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext

T = TypeVar("T", bound=BaseModel)

# Authoritative model-prior default lives in runner.DEFAULT_MODELS; this is a
# convenience constant kept in sync (opus-5 = production sweep model).
OPUS_MODEL = "claude-opus-5"







def _build_user_prompt(gene_symbol: str, isoforms: list[IsoformContext]) -> str:
    # gene_symbol is intentionally NOT written into the prompt, and isoform
    # accessions are replaced with generic labels: the model must grade
    # endocytic propensity from sequence + topology ALONE, blind to which
    # protein this is. Grades are re-attached to the real isoform IDs by INPUT
    # position in ``grade_isoforms_with_model`` (the parameter is kept for
    # caller compatibility).
    lines = [
        "Grade this protein's INTRINSIC / BASAL endocytic (internalization) "
        "propensity per isoform, using ONLY the amino-acid sequences and the "
        "extracellular/cytoplasmic (E/C) topology below. You are NOT told which "
        "protein this is; do not try to identify it or recall any specific "
        "protein's known biology — reason only from sequence and topology. "
        "Topology gives the extracellular vs cytoplasmic (inside/outside) "
        "sidedness — endocytic sorting motifs only function in CYTOPLASMIC "
        "regions, so weigh motifs against it. Source is DeepTMHMM (per-residue "
        "inside/outside prediction) where available, else UniProt topology "
        "features (annotated on the canonical isoform).",
        "",
        "Where a DeepTMHMM per-residue topology string is given, it is "
        "residue-aligned to the sequence (same length, position i of the "
        "topology string is the compartment of residue i). Alphabet: "
        "S=signal peptide, I=cytoplasmic (inside), O=extracellular (outside), "
        "M=transmembrane helix, B=β-barrel TM strand. Use it to place each "
        "candidate motif in its actual compartment.",
        "",
    ]
    for i, iso in enumerate(isoforms, 1):
        label = f"Isoform {i}" + (" (canonical)" if iso.is_canonical else "")
        lines += [
            f"### {label}",
            f"Length: {iso.length_aa} aa",
            f"Topology ({iso.topology_source}): {iso.topology_summary}",
            "Sequence:",
            iso.sequence,
        ]
        if iso.topology_per_residue:
            lines += [
                "Per-residue topology (S/I/O/M/B, aligned to the sequence above):",
                iso.topology_per_residue,
            ]
        lines.append("")
    lines.append(
        "Return a single ```json fenced object matching the required schema."
    )
    return "\n".join(lines)




def prompt_sha(system_prompt: str) -> str:
    """sha256 of the exact system-prompt text this track ran under — the
    content fingerprint that makes a stale record detectable."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()


def grade_isoforms_with_model(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    gene_symbol: str,
    isoforms: list[IsoformContext],
    usage_sink: list[Any] | None = None,
    prompt_version: str = MODEL_PRIOR_PROMPT_VERSION,
) -> ModelPriorTrack:
    out = call_model_structured(
        client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=_build_user_prompt(gene_symbol, isoforms),
        schema=ModelPriorLLMOut,
        usage_sink=usage_sink,
    )
    # The model graded anonymized isoforms (generic labels, no real accession),
    # so each returned ``isoform_id`` is a placeholder. Re-attach real identity
    # by INPUT position — index i -> isoforms[i] — overwriting isoform_id,
    # is_canonical, and length_aa with the trusted input values. ``zip`` is a
    # best-effort pair by index: extra graded isoforms are dropped and missing
    # ones are simply not emitted (never crash on a count mismatch).
    per_isoform = [
        graded.model_copy(
            update={
                "isoform_id": ctx.isoform_id,
                "is_canonical": ctx.is_canonical,
                "length_aa": ctx.length_aa,
                # Re-stamp the per-residue topology from the trusted input — the
                # model is never asked to echo the long string back.
                "topology_per_residue": ctx.topology_per_residue,
            }
        )
        for graded, ctx in zip(out.per_isoform, isoforms)
    ]
    return ModelPriorTrack(
        model=model,
        overall_grade=out.overall_grade,
        overall_confidence=out.overall_confidence,
        model_reasoning=out.model_reasoning,
        per_isoform=per_isoform,
        prompt_sha=prompt_sha(system_prompt),
        prompt_version=prompt_version,
    )
