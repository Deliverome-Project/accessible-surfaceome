"""Drift-guard: every SurfaceomeRecord field is surfaced in the markdown
exporter, or explicitly allow-listed as intentionally omitted.

The per-gene markdown export (``viewer/scripts/build-markdown-exports.mjs``)
is meant to be a rich human-readable mirror of the record. Nothing stops a
future schema field from being added but silently never wired into the
markdown — which is exactly the gap a 2026-05 coverage audit had to close by
hand. This test makes "rich markdown" a maintained invariant: it introspects
every (nested) field name on ``SurfaceomeRecord`` and asserts each one either
appears in the generator source OR is on the curated ``OMITTED`` allow-list.

It's deliberately a NAME-level check (does the field name appear anywhere in
the generator?), not a render-path check — coarse, but it reliably catches
the real regression (a new distinctively-named field that was never touched
by the generator) with zero false negatives for that case. Adding a field to
``OMITTED`` is a deliberate, reviewable choice to NOT surface it (internal
bookkeeping: hashes, QA flags, retrieval timestamps, re-fetch IDs).
"""
from __future__ import annotations

import typing
from pathlib import Path

from pydantic import BaseModel

from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

_GENERATOR = (
    Path(__file__).resolve().parents[1]
    / "viewer"
    / "scripts"
    / "build-markdown-exports.mjs"
).read_text()


def _nested_models(annotation: object) -> list[type[BaseModel]]:
    """Every BaseModel subclass reachable from a type annotation (through
    Optional / list / dict / Union wrappers)."""
    out: list[type[BaseModel]] = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        out.append(annotation)
    for arg in typing.get_args(annotation):
        out.extend(_nested_models(arg))
    return out


def _all_field_names(
    model: type[BaseModel], seen: set[type[BaseModel]] | None = None
) -> set[str]:
    """Recursively collect every field name on ``model`` and its nested
    models (deduped; self-references terminate via ``seen``)."""
    seen = seen if seen is not None else set()
    if model in seen:
        return set()
    seen.add(model)
    names: set[str] = set()
    for fname, field in model.model_fields.items():
        names.add(fname)
        for nested in _nested_models(field.annotation):
            names |= _all_field_names(nested, seen)
    return names


# Fields intentionally NOT surfaced in the human-facing markdown. Each entry
# is a deliberate choice — internal bookkeeping that would add noise without
# helping a reader. To surface one, render it in the generator and delete it
# here; to add a new omission, add it here WITH the reasoning in review.
OMITTED: dict[str, str] = {
    # --- search / tool-consultation log (provenance, not findings) ---
    "search_log": "tool consultation log; provenance not findings",
    "query": "search query string; provenance",
    "n_results": "result count for a search; provenance",
    "sources_seen": "sources a search returned; provenance",
    "source_id": "internal source row id; re-fetch only",
    "source_type": "source kind enum; the link itself is shown",
    "content_sha256": "source content hash; tamper bookkeeping",
    "publication_type": "source publication type; low value vs the link",
    "retraction_checked_at": "retraction-check timestamp; bookkeeping",
    "is_retracted": "retraction flag; surfaced upstream, not per-record md",
    "contributed_evidence_ids": "search→evidence linkage; provenance",
    # --- evidence-span verification / tamper bookkeeping ---
    "quote_sha256": "quote tamper hash; not human-facing",
    "normalized_source_sha256": "normalization hash; not human-facing",
    "char_offset": "char offset into source; internal",
    "figure_or_table_id": "figure/table ref; low value vs the quote",
    "section": "paper section of a quote; low value vs the quote",
    "evidence_type": "redundant with method_family / claim_type",
    "confidence": "per-evidence-span confidence; the tier is shown",
    "entailment_verified": "substring-check flag; QA bookkeeping",
    "entailment_audit_passed": "Sonnet audit flag; QA bookkeeping",
    "validation_warnings": "normalization warnings; QA bookkeeping",
    "duplicate_of": "cross-planner dedup marker; folded silently",
    # --- counts shown via computed values, not the stored field ---
    "evidence_count": "shown as evidence[].length in the ledger header",
    "primary_evidence_count": "computed inline in the ledger header",
    "secondary_evidence_count": "computed inline in the ledger header",
    # --- ECD % similarity (secondary to the % identity that IS shown) ---
    "ecd_pct_similarity_to_canonical": "secondary to ECD %identity (shown)",
    "ecd_pct_similarity_to_human_canonical": "secondary to ECD %identity (shown)",
    # --- Schweke 2024 homo-oligomer prior (piped into synthesizer; no viewer card yet) ---
    "homo_oligomerization": "Schweke 2024 prior — fed to synthesizer for epitope-masking prior, not rendered standalone",
    "is_homo_oligomer": "Schweke 2024 prior — boolean fed to synthesizer",
    "stoichiometry": "Schweke 2024 prior — cyclic-symmetry order, fed to synthesizer",
    "af_model_num": "Schweke 2024 model rank — viewer-side PDB URL builder, not surfaced in markdown",
    "is_ecd_only": "Schweke 2024 ECD-only flag — viewer-side caption, not surfaced in markdown",
    "has_higher_order_complex": "Schweke 2024 complex flag — viewer-side caption, not surfaced in markdown",
    "dimer_pdb_filename": "Schweke 2024 dimer PDB filename — viewer-side asset URL, not surfaced in markdown",
    "complex_pdb_filename": "Schweke 2024 complex PDB filename — viewer-side asset URL, not surfaced in markdown",
    # --- topology projection / model internals (shown qualitatively) ---
    "deeptmhmm_label": "categorical label; the per-residue string is shown",
    "topology_projection_source": "projection provenance; internal",
    "tm_absent_from_model": "truncated-model flag; internal",
    "n_tm_regions_absent": "truncated-model count; internal",
    "species_inferred": "inference flag accompanying species; internal",
    # --- "checked, none found" sentinels (presence flags; absence implicit in md) ---
    "checked": "orthologs checked-but-empty sentinel; absence implicit in md",
    "paralogs_checked": "paralogs checked-but-empty sentinel; absence implicit in md",
    "isoform_topologies_checked": "isoform-topology checked-but-empty sentinel; absence implicit in md",
    # --- re-fetch identifiers (programmatic, not human-facing) ---
    "ensembl_id": "ortholog Ensembl id; re-fetch only",
    "family_id": "Compara family id; re-fetch only",
    "cellosaurus_id": "cell-line ontology id; re-fetch only",
    "retrieved_at": "per-source fetch timestamp; internal",
    # --- assay-context inner detail (the assay summary line is shown) ---
    "cell_context": "container; useful fields summarized in the assay line",
    "material_kind": "assay material kind; summarized in the assay line",
    "material_kind_other_label": "free-text escape for material_kind",
    "cell_line_name": "covered by cell_type_or_line in the assay summary",
    "activation_state": "covered by the cell-state pivot / assay summary",
    "disease_state": "covered by tissues disease_context",
    # --- niche modulation sub-fields ---
    "category_other_label": "free-text escape for 'other' modulation category",
    "dual_loc_partner_compartment": "niche modulation sub-field",
    # --- superseded ---
    "requires_coreceptor_for_expression": "superseded by co_receptor_dependency (shown)",
}


def test_every_record_field_is_surfaced_or_omitted() -> None:
    names = _all_field_names(SurfaceomeRecord)
    missing = sorted(n for n in names if n not in OMITTED and n not in _GENERATOR)
    assert not missing, (
        "These SurfaceomeRecord fields are neither rendered in "
        "build-markdown-exports.mjs nor allow-listed in OMITTED — either wire "
        "them into the generator or add them to OMITTED with a reason:\n  "
        + "\n  ".join(missing)
    )


def test_omitted_entries_are_real_fields() -> None:
    """Keep OMITTED honest: every allow-listed name must still be a real
    field on the schema (so the list can't rot with stale entries)."""
    names = _all_field_names(SurfaceomeRecord)
    stale = sorted(k for k in OMITTED if k not in names)
    assert not stale, f"OMITTED names no longer on the schema (remove them): {stale}"
