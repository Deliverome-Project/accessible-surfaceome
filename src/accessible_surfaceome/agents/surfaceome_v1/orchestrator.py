"""Shared deep-dive helpers (formerly the v1 deep-dive orchestrator).

The v1 Managed-Agent ``annotate`` entry point and its 3-agent topology
(Surface Evidence Compiler ∥ Biology Compiler → Synthesizer) were removed —
v1 is deprecated; the production deep-dive is ``surfaceome_v2``. What survives
here are the deterministic, agent-agnostic helpers that v2, the
plan-trim-select runner, the deterministic-feature backfill scripts, and the
tests still import:

* ``_derive_filters`` — the 14-field deterministic Filters rollup.
* ``_attach_deterministic_families`` — curator-assigned family tags from the
  resolved IdentifierBundle.
* ``scrub_headline_risks`` — drop unbacked headline-risk entries.
* ``_load_triage_record`` / ``_triage_signal_and_reasoning_from_record`` and
  the D1 triage loaders.
* ``_stub_deterministic_features`` — the no-D1 placeholder.

TODO (follow-up): relocate these out of the ``surfaceome_v1`` package (e.g.
to ``agents/_support/``) so the v1 package shell can be deleted.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path


from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContext,
    DeterministicFeatures,
    EvidenceDensity,
    ExecutiveSummary,
    Filters,
    IdentifierBundle,
    InductionTrigger,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
    SurfaceEvidence,
    SynthesizerLLMFilters,
    TriageRecord,
    TriageSignal,
)

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-6"  # all three agents currently run on Sonnet 4.6
SCHEMA_VERSION_LITERAL = "1.0.0"
RUNS_DIR = Path(".runs")




def _hgnc_id_for_symbol(symbol: str) -> str | None:
    """Look up the HGNC ID for a symbol from D1 ``gene_identifier``.

    Tries ``hgnc_symbol`` first (HGNC's official symbol) then
    ``cohort_symbol`` (the symbol the M1 cohort row used) — those
    sometimes diverge when HGNC has updated a symbol but the cohort
    TSV hasn't been regenerated. Returns ``None`` for an unknown
    symbol so the caller can raise its own ``LookupError`` with
    domain context.
    """
    # Local import keeps the D1 dependency out of import-time for code
    # paths that never need symbol lookup (most of the runner code).
    from accessible_surfaceome.cloud.d1_client import D1Client, D1Error

    try:
        d1 = D1Client()
    except D1Error:
        # D1 credentials not configured — annotation can still run if
        # the caller passes an accession or HGNC ID, so re-raise as
        # LookupError with a migration hint instead of crashing the
        # whole annotate() call.
        raise LookupError(
            f"cannot resolve symbol {symbol!r} without D1 credentials. "
            "Either set CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN + "
            "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID, or pass a UniProt accession "
            "(e.g. Q9UBP8) / HGNC ID (e.g. HGNC:4526) directly."
        ) from None
    rows = d1.query(
        "SELECT hgnc_id FROM gene_identifier "
        "WHERE hgnc_symbol = ? OR cohort_symbol = ? LIMIT 1;",
        [symbol, symbol],
    )
    if not rows:
        return None
    return rows[0]["hgnc_id"]








# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------




_TRIAGE_VERDICT_TO_SIGNAL: dict[str, TriageSignal] = {
    "yes": "likely_accessible",
    "contextual": "possibly_accessible",
    "no": "unlikely",
}


def _load_triage_signal(symbol: str) -> TriageSignal:
    """Map the latest persisted triage record (if any) onto the record's
    ``triage_signal`` enum; default ``unknown`` when no triage exists.
    """
    record = _load_triage_record(symbol)
    if record is None:
        return "unknown"
    return _TRIAGE_VERDICT_TO_SIGNAL.get(record.verdict, "unknown")


def _triage_signal_and_reasoning_from_record(
    record: TriageRecord | None,
) -> tuple[TriageSignal, str | None]:
    """Derive the ``triage_signal`` enum and verdict prose from an
    already-loaded ``TriageRecord``.

    Mirrors :func:`_load_triage_signal` but operates on a record the
    caller already fetched, so the deep-dive orchestrator can carry the
    triage's "why" onto the ``SurfaceomeRecord`` without a second D1
    round-trip. The signal is the verdict-derived enum; the reasoning is
    the triage agent's ``verdict_reasoning`` prose. Returns
    ``("unknown", None)`` when no triage exists.
    """
    if record is None:
        return "unknown", None
    signal = _TRIAGE_VERDICT_TO_SIGNAL.get(record.verdict, "unknown")
    return signal, record.verdict_reasoning


def _load_triage_record(symbol: str) -> TriageRecord | None:
    """Return the full persisted ``TriageRecord`` (verdict +
    verdict_reasoning + reason taxonomy + key_uncertainty + confidence),
    or ``None`` when no triage exists.

    The deep-dive's planner + synthesizer read this so they can see the
    triage agent's prose justification + structured reason taxonomy,
    not just the verdict-derived ``triage_signal`` enum — per the
    original design's "common preamble" requirement (PR #23 design doc
    §1110-1116).

    Resolution order:

    1. Local file at ``data/triage/{symbol}.json`` (gitignored;
       populated when a local triage sweep runs against the gene).
    2. Public D1 ``triage_run_public`` Sonnet hit, preferring the
       canonical run / variant. This lets a one-off deep-dive on a
       gene that isn't in the local cache still see the genome-wide
       triage prior — without the user having to manually hydrate
       the local file first.

    Returns ``None`` only when neither source has a hit. D1 errors
    are logged and swallowed (annotate must keep running).
    """
    triage_path = DATA_DIR / "triage" / f"{symbol}.json"
    if triage_path.exists():
        try:
            return TriageRecord.model_validate_json(triage_path.read_text())
        except Exception as exc:  # noqa: BLE001 — best-effort; a malformed triage shouldn't fail annotate
            logger.warning("triage record for %s failed to parse: %s", symbol, exc)
            return None
    return _load_triage_record_from_d1(symbol)


# Priority list for the D1 fallback. We prefer the bench's canonical
# Sonnet variant (richest, most-trusted) over the genome-wide sweep,
# and fall back to "any Sonnet hit" if neither preferred run_id is
# present. The "ncbi" variant is the production prompt the cohort
# sweeps run with; the others (web_ncbi, pubmed_ncbi, recent_corpus)
# add tool-use variants we don't want to elevate to the headline
# triage_signal without explicit configuration.
_D1_TRIAGE_PRIORITY: list[tuple[str, str]] = [
    ("mainbench_canonical_v1", "ncbi"),
    ("genome_full_sonnet_ncbi_v1__resolver_v3_fix", "ncbi"),
    ("genome_full_sonnet_ncbi_v1", "ncbi"),
]


def _load_triage_record_from_d1(symbol: str) -> TriageRecord | None:
    """Hydrate a ``TriageRecord`` from public D1 ``triage_run_public``.

    See ``_D1_TRIAGE_PRIORITY`` for the (run_id, variant) priority
    list. Each step queries D1 once; first hit wins. All errors are
    logged + swallowed so a D1 outage doesn't fail annotate — the
    caller falls back to ``triage_signal=unknown``, which is the same
    behavior as before this fallback existed.
    """

    try:
        # Imports are local: keeps `D1Client` out of the hot path for
        # the case where the local file is present (common in CI / on
        # cohort sweeps that pre-populate ``data/triage/``).
        import os

        from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
        from accessible_surfaceome.env import load_env

        load_env()
        public_db_id = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        if not (public_db_id and account_id and api_token):
            logger.info(
                "no D1 public credentials in env; skipping triage D1 fallback for %s",
                symbol,
            )
            return None
        cfg = D1Config(
            account_id=account_id,
            database_id=public_db_id,
            api_token=api_token,
        )
        with D1Client(cfg) as d1:
            for run_id, variant in _D1_TRIAGE_PRIORITY:
                rows = d1.query(
                    """
                    SELECT predicted_verdict, predicted_reason,
                           predicted_confidence, predicted_key_uncertainty,
                           verdict_reasoning, uniprot_acc,
                           model, prompt_variant, run_id, replicate
                    FROM triage_run_public
                    WHERE gene_symbol = ?
                      AND run_id = ?
                      AND prompt_variant = ?
                      AND model LIKE '%sonnet%'
                      AND predicted_verdict IS NOT NULL
                    ORDER BY replicate ASC, created_at DESC
                    LIMIT 1;
                    """,
                    [symbol, run_id, variant],
                )
                if rows:
                    # Companion query against gene_identifier_public to fill
                    # the full GeneIdentifier bundle (hgnc_id / ncbi_gene_id /
                    # ensembl_gene) — the triage_run_public row only carries
                    # uniprot_acc + gene_symbol. Failure is non-fatal; the
                    # loader falls back to empty placeholders.
                    identifier_row: dict[str, object] | None = None
                    try:
                        id_rows = d1.query(
                            """
                            SELECT hgnc_id, ncbi_gene_id, ensembl_gene
                            FROM gene_identifier_public
                            WHERE uniprot_acc = ?
                            LIMIT 1;
                            """,
                            [rows[0].get("uniprot_acc")],
                        )
                        if id_rows:
                            identifier_row = id_rows[0]
                    except Exception as exc:  # noqa: BLE001 — keep going on identifier-lookup failure
                        logger.warning(
                            "gene_identifier_public lookup for %s failed: %s; "
                            "triage record will have empty hgnc_id / ncbi_gene_id / ensembl_gene",
                            symbol,
                            exc,
                        )
                    return _triage_record_from_d1_row(
                        symbol, rows[0], identifier_row=identifier_row
                    )
    except Exception as exc:  # noqa: BLE001 — never fail annotate over a triage miss
        logger.warning(
            "triage D1 fallback for %s failed: %s; using triage_signal=unknown",
            symbol,
            exc,
        )
        return None
    return None


def _triage_record_from_d1_row(
    symbol: str,
    row: dict[str, object],
    *,
    identifier_row: dict[str, object] | None = None,
) -> TriageRecord | None:
    """Construct a ``TriageRecord`` from one ``triage_run_public`` row.

    When ``identifier_row`` is supplied (the caller paired the triage
    query with a ``gene_identifier_public`` lookup), the resulting
    ``GeneIdentifier`` carries the full bundle; otherwise the per-gene
    IDs default to empty placeholders. Either way, the synthesizer only
    reads ``verdict_reasoning`` / ``reason`` / ``confidence`` /
    ``key_uncertainty``, so a placeholder-only record still annotates
    correctly — the IDs matter for audit + downstream analytics.

    Returns ``None`` if the row can't be schema-validated (e.g. the
    D1 reason taxonomy drifted from the v1 verdict-vs-reason
    cross-check the model enforces). Logged at WARNING so drift
    becomes visible rather than silently masking the triage.

    D1's ``predicted_confidence`` and the schema's ``TriageConfidence``
    both use the same ``low|medium|high`` alphabet, so no remapping is
    needed — pass the value through and let Pydantic catch any drift.
    """

    verdict = row.get("predicted_verdict")
    reason = row.get("predicted_reason")
    conf_raw = row.get("predicted_confidence")
    reasoning = row.get("verdict_reasoning") or ""
    key_uncertainty = row.get("predicted_key_uncertainty")
    uniprot_acc = row.get("uniprot_acc") or ""

    confidence = str(conf_raw).lower() if conf_raw else "medium"

    # Identifier fields: prefer the companion gene_identifier_public row
    # when the caller passed it; fall back to empty placeholders.
    hgnc_id = ""
    ncbi_gene_id = 0
    ensembl_gene = ""
    if identifier_row is not None:
        hgnc_id = str(identifier_row.get("hgnc_id") or "")
        ncbi_raw = identifier_row.get("ncbi_gene_id")
        try:
            ncbi_gene_id = int(ncbi_raw) if ncbi_raw is not None else 0  # ty:ignore[invalid-argument-type]
        except (TypeError, ValueError):
            ncbi_gene_id = 0
        ensembl_gene = str(identifier_row.get("ensembl_gene") or "")

    try:
        from accessible_surfaceome.tools._shared.models import (
            GeneIdentifier,
            TriageProvenance,
            TriageRecord,
        )

        provenance: TriageProvenance | None = None
        model_id = row.get("model")
        prompt_variant = row.get("prompt_variant")
        run_id = row.get("run_id")
        if model_id and prompt_variant and run_id:
            replicate_raw = row.get("replicate")
            replicate: int | None
            if replicate_raw is None:
                replicate = None
            else:
                try:
                    replicate = int(replicate_raw)  # ty:ignore[invalid-argument-type]
                except (TypeError, ValueError):
                    replicate = None
            provenance = TriageProvenance(
                model=str(model_id),
                prompt_variant=str(prompt_variant),
                run_id=str(run_id),
                replicate=replicate,
            )

        return TriageRecord(
            gene=GeneIdentifier(
                hgnc_symbol=symbol,
                hgnc_id=hgnc_id,
                uniprot_acc=str(uniprot_acc),
                ncbi_gene_id=ncbi_gene_id,
                ensembl_gene=ensembl_gene,
            ),
            # The verdict / reason / confidence values come straight from D1
            # as strings; their *runtime* validity is what the TriageRecord
            # constructor enforces (the `_check_reason_matches_verdict`
            # model-validator + the Literal type narrowing). Static checkers
            # can't see the narrowing, so silence the literal-mismatch.
            verdict=str(verdict),  # ty:ignore[invalid-argument-type]
            verdict_reasoning=str(reasoning),
            reason=str(reason),  # ty:ignore[invalid-argument-type]
            confidence=confidence,  # ty:ignore[invalid-argument-type]
            key_uncertainty=str(key_uncertainty) if key_uncertainty else None,
            provenance=provenance,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "triage D1 row for %s failed schema validation: %s; "
            "verdict=%r reason=%r conf=%r",
            symbol, exc, verdict, reason, conf_raw,
        )
        return None


def _stub_deterministic_features(uniprot_acc: str) -> DeterministicFeatures:
    """Minimal valid ``DeterministicFeatures`` for sub-step 1.

    The DeepTMHMM / Ensembl Compara / AlphaFold DB fetchers are deferred until
    the broader v1.0.0 cutover lands. Until then we emit a schema-valid
    placeholder so the assembled record validates and downstream consumers
    (viewer, D1) can wire against the real shape. The placeholder is
    explicitly labeled in ``structure.source`` so a reader doesn't mistake
    zero-pLDDT for a real measurement.
    """
    now = datetime.now(UTC)
    canonical = IsoformTopology(
        isoform_id=f"{uniprot_acc}-1",
        uniprot_acc=uniprot_acc,
        tm_helix_count=0,
        n_terminal_orientation="extracellular",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=0,
        ecd_length_residues=0,
        icd_length_residues=0,
        per_residue_topology="",
        tool_version="stub-no-fetchers-v1.0.0",
        retrieved_at=now,
    )
    structure = StructureFeatures(
        # Placeholders track LATEST_KNOWN_AFDB_VERSION (viewer/lib/
        # structure-viewer-types.ts). Mirror the d1_deterministic
        # stub so a future v6 → v7 bump only needs a grep for "v6"
        # to find all the cosmetic defaults.
        afdb_id=f"AF-{uniprot_acc}-F1-model_v6",
        afdb_version="v6",
        ecd_mean_plddt=0.0,
        ecd_disordered_fraction=0.0,
        source="AlphaFold DB (STUB — fetchers not yet built)",
        license="CC BY 4.0",
        attribution="© DeepMind / EMBL-EBI",
        citations=["10.1038/s41586-021-03819-2", "10.1093/nar/gkad1011"],
    )
    return DeterministicFeatures(
        canonical_topology=canonical,
        isoform_topologies=[],
        orthologs=Orthologs(),
        paralogs=[],
        structure=structure,
    )


def _evidence_density(n: int) -> EvidenceDensity:
    """Bucket evidence count into the ``Filters.evidence_density`` enum.

    Doc spec: ``≥30 → high, ≥10 → moderate, else → low``.
    """
    if n >= 30:
        return "high"
    if n >= 10:
        return "moderate"
    return "low"


def scrub_headline_risks(
    executive_summary: "ExecutiveSummary",
    accessibility_risks: "AccessibilityRisks",
) -> "ExecutiveSummary":
    """Drop ``headline_risks`` entries whose structured field disagrees.

    The synthesizer occasionally writes a ``headline_risks`` list that
    over-claims relative to the structured ``accessibility_risks`` block
    it produced in the same call — e.g. listing ``co_receptor`` while
    setting ``co_receptor_requirements.surface_expression_dependency =
    "modulatory"`` (not ``"required"``), or listing ``epitope_masked``
    while ``epitope_masking.severity = "none"``. Reviewers spotted this
    on CD81. The structured fields are the canonical signal — the
    headline_risks list is a free-text reading. We scrub the list to
    match the structured fields, never the other way around.

    Returns a new :class:`ExecutiveSummary` with the cleaned list.
    Logs (info) when entries are dropped.
    """

    risks = list(executive_summary.headline_risks)
    dropped: list[str] = []

    em_sev = accessibility_risks.epitope_masking.severity
    if "epitope_masked" in risks and em_sev in ("none", "low"):
        dropped.append("epitope_masked")

    if (
        "shed_form" in risks
        and not accessibility_risks.shed_form.present
    ):
        dropped.append("shed_form")

    if (
        "secreted_form" in risks
        and not accessibility_risks.secreted_form.present
    ):
        dropped.append("secreted_form")

    cr_dep = accessibility_risks.co_receptor_requirements.surface_expression_dependency
    if "co_receptor" in risks and cr_dep != "required":
        dropped.append("co_receptor")

    # NOTE: ``restricted_subdomain`` is no longer in the ``HeadlineRisk``
    # enum (post-design-review slim from 11 → 5 values). It was a direct
    # copy of ``accessibility_risks.restricted_subdomain.present`` and
    # the reader sees the structured field on the page. The scrub call
    # for it has been removed; if the model ever emits the obsolete
    # value, Pydantic validation rejects it before this scrub runs.

    if not dropped:
        return executive_summary
    cleaned = [r for r in risks if r not in dropped]
    logger.info(
        "scrubbed headline_risks (no structured backing): dropped=%s; kept=%s",
        dropped,
        cleaned,
    )
    return executive_summary.model_copy(update={"headline_risks": cleaned})


def _attach_deterministic_families(
    executive_summary: "ExecutiveSummary",
    bundle: "IdentifierBundle",
) -> "ExecutiveSummary":
    """Inject the deterministic, curator-assigned family tags onto the summary.

    The synthesizer emits ``llm_family`` (its high-level functional call). The
    deterministic family tags — HGNC gene groups and the UniProt SIMILARITY
    family — are NOT model-emitted; the orchestrator overwrites them from the
    resolved :class:`IdentifierBundle` so they stay ground-truth regardless of
    what the model did or didn't say. Returns a new ExecutiveSummary; the input
    is left untouched.
    """
    return executive_summary.model_copy(
        update={
            "hgnc_gene_groups": list(bundle.hgnc_gene_groups),
            "uniprot_family": bundle.uniprot_family,
        }
    )


def _derive_filters(
    *,
    executive_summary: ExecutiveSummary,
    surface_evidence: SurfaceEvidence,
    biological_context: BiologicalContext,
    accessibility_risks: AccessibilityRisks,
    filters_llm: SynthesizerLLMFilters,
    deterministic_features: DeterministicFeatures,
    n_evidence: int,
) -> Filters:
    """Build the 17-field top-level ``Filters`` from B's blocks + the
    deterministic side. 14 fields are derived deterministically; 3 come from
    B's :class:`SynthesizerLLMFilters` (expression_level / breadth /
    surface_specificity)."""
    canon = deterministic_features.canonical_topology

    # restricted_subdomain rollup: mirror the §Risks restricted-subdomain
    # block EXACTLY. (Previously this also OR'd in any anatomical-
    # accessibility row tagged "restricted", which made the §01
    # ``has_restricted_subdomain`` chip read "restricted membrane subdomain
    # · present" even when the dedicated subdomain block was absent —
    # contradicting the §03 card for genes like SRC. The anatomical-
    # restriction signal is already surfaced in the §03 anatomical-
    # accessibility table, so the chip mirrors only the subdomain block.)
    has_restricted = accessibility_risks.restricted_subdomain.present

    # max-paralog identity is None when there are no paralogs (the stub case
    # while fetchers are deferred) OR when every paralog has NULL identity
    # (ECD-less proteins — SRC-family kinases / soluble proteins).
    _paralog_ids = [
        p.ecd_pct_identity
        for p in deterministic_features.paralogs
        if p.ecd_pct_identity is not None
    ]
    max_paralog = max(_paralog_ids) if _paralog_ids else None

    # Stance-map counts (5b.8) — derived from
    # ``surface_evidence.claim_stances`` so the catalog can distinguish
    # "conflicting grade with 1 contradiction → likely artifact" from
    # "conflicting grade with ≥3 contradictions → real disagreement"
    # without re-parsing grade_rationale prose. Empty stance map →
    # both counts are 0 (backward-compat for records emitted before
    # the stance field existed).
    n_supporting_hi = sum(
        1 for s in surface_evidence.claim_stances
        if s.stance == "supports_surface" and s.weight == "high"
    )
    n_contradicting_hi = sum(
        1 for s in surface_evidence.claim_stances
        if s.stance == "contradicts_surface" and s.weight == "high"
    )

    # OE-with-surface-localization derived bool. True iff any
    # MethodObservation pairs an overexpression / mixed expression
    # system with a direct or surface-localization accessibility
    # tier. Signals "OE-based validation has been done for this
    # target." Filter on it to find genes amenable to OE follow-up.
    _SURFACE_TIERS = {
        "direct_surface_accessibility",
        "supports_surface_localization",
    }
    _OE_SYSTEMS = {"overexpression", "mixed"}
    _oe_methods = [
        m
        for m in surface_evidence.methods
        if m.expression_system in _OE_SYSTEMS
        and m.accessibility_relevance in _SURFACE_TIERS
    ]
    oe_surface_observed = len(_oe_methods) > 0
    # Composed rationale for the OE-surface derived boolean — names the
    # triggering method observation(s) so the chip's "why" is auditable.
    if oe_surface_observed:
        # Prefer the OE-specific cites the methods builder isolated into the
        # method's ``overexpression`` block (e.g. the transfected-line flow
        # data) over the method's FULL cite list. A "mixed" method's full
        # cites also carry its endogenous + methodology cites, which don't
        # speak to the overexpression-surface point — citing all of them
        # makes the OE rationale look mis-cited (the reader can't tell which
        # id is the OE one). Fall back to the full list only when the
        # overexpression block carried no cites of its own.
        _oe_cites = sorted(
            {
                cid
                for m in _oe_methods
                for cid in (
                    m.overexpression.cited_evidence_ids
                    if (m.overexpression and m.overexpression.cited_evidence_ids)
                    else m.cited_evidence_ids
                )
            }
        )
        oe_rationale = (
            f"{len(_oe_methods)} method observation(s) pair an "
            "overexpression/mixed expression system with a "
            "surface-localization readout"
            + (f" (cites {', '.join(_oe_cites)})" if _oe_cites else "")
            + "."
        )
    else:
        oe_rationale = (
            "No method observation pairs an overexpression/mixed expression "
            "system with a direct or supportive surface-accessibility readout."
        )

    # Derived boolean for the low-endogenous-exposure chip.
    #
    # Two cases trip the flag:
    #   1. Outright low / absent baseline expression
    #      (``expression_level ∈ {low, absent}``).
    #   2. Moderate baseline that's concentrated in one or two tissues
    #      (``expression_level=='moderate'`` AND
    #      ``expression_breadth=='restricted'``). Catches the GPR75-class
    #      gene where the synth call is "moderate" but the breadth is
    #      narrow enough that endogenous burden in non-target tissues is
    #      effectively low — relevant for ADC therapeutic-window
    #      framing.
    #
    # Surface_specificity is intentionally NOT in this rule even when it's
    # ``restricted`` / ``tumor_enriched``: that field has its own catalog
    # chip, and folding it in here would have the same biology fire two
    # correlated rationales for the reader.
    _low_endog = filters_llm.expression_level in ("low", "absent") or (
        filters_llm.expression_level == "moderate"
        and filters_llm.expression_breadth == "restricted"
    )
    # The rationale text the reader sees is the synth's
    # ``expression_level_rationale`` verbatim — natural-language reasoning
    # anchored by cites. No pipeline-internal preamble (no enum names,
    # no boolean arithmetic, no "Derived from" framing): those leaked
    # schema state into user prose and added nothing the synth's
    # rationale didn't already say. Empty rationale falls back to the
    # field default ``""``, which the viewer renders as no expansion.
    low_endog_rationale = filters_llm.expression_level_rationale

    def _canonical_species_identity(entries: list) -> float | None:
        for e in entries:
            if e.is_canonical:
                return e.ecd_pct_identity_to_human_canonical
        return None

    # ---- deep-block rollups -------------------------------------------
    # tumor_associated — any tissue row in a tumor / tumor-adjacent disease
    # context at a non-absent protein level. Oncology-target triage facet.
    _TUMOR_CTX = {"tumor", "tumor_adjacent"}
    _PRESENT_LEVELS = {"high", "moderate", "low", "mixed"}
    tumor_associated = any(
        t.disease_context in _TUMOR_CTX and t.present in _PRESENT_LEVELS
        for t in biological_context.expression
    )

    # induction_trigger — dominant stimulus bucket across the modulation
    # rows' cell_state_trigger. surface_call_reason carries the *mechanism*;
    # this is the *trigger*. Buckets, picked most-targeting-relevant first.
    _TRIGGER_BUCKET = {
        "oncogenic_transformation": "oncogenic",
        "immune_activation": "immune",
        "antigen_stimulation": "immune",
        "cytokine_stimulation": "immune",
        "ER_stress": "stress_hypoxia",
        "heat_shock": "stress_hypoxia",
        "oxidative_stress": "stress_hypoxia",
        "DNA_damage_response": "stress_hypoxia",
        "hypoxia": "stress_hypoxia",
        "nutrient_deprivation": "stress_hypoxia",
        "hyperthermia": "stress_hypoxia",
        "mechanical_stress": "stress_hypoxia",
        "apoptosis": "cell_death",
        "necroptosis": "cell_death",
        "infection_viral": "infection",
        "infection_bacterial": "infection",
        "other": "other",
        "unknown": "other",
    }
    _buckets = {
        _TRIGGER_BUCKET.get(m.cell_state_trigger, "other")
        for m in biological_context.accessibility_modulation
        if m.cell_state_trigger is not None
    }
    if "oncogenic" in _buckets:
        induction_trigger: InductionTrigger = "oncogenic"
    elif "immune" in _buckets:
        induction_trigger = "immune"
    elif "stress_hypoxia" in _buckets:
        induction_trigger = "stress_hypoxia"
    elif "cell_death" in _buckets:
        induction_trigger = "cell_death"
    elif "infection" in _buckets:
        induction_trigger = "infection"
    elif "other" in _buckets:
        induction_trigger = "other"
    else:
        induction_trigger = "none"

    # has_live_cell_surface_evidence — a DIRECT surface readout on
    # live/intact cells in an endogenous context (flow cytometry, surface
    # biotinylation, or proximity labeling; NOT permeabilizable IF/IHC).
    _LIVE_CELL_FAMILIES = {"flow_cytometry", "biotinylation", "proximity_labeling"}
    _ENDOG_SYSTEMS = {"endogenous", "mixed"}
    has_live_cell_surface_evidence = any(
        m.method_family in _LIVE_CELL_FAMILIES
        and m.accessibility_relevance == "direct_surface_accessibility"
        and m.expression_system in _ENDOG_SYSTEMS
        for m in surface_evidence.methods
    )

    return Filters(
        # D — from executive_summary (B)
        surface_accessibility=executive_summary.surface_accessibility,
        confidence=executive_summary.confidence,
        subcategory=executive_summary.subcategory,
        # D — state_dependence rolled up from executive_summary so the
        # catalog can D1-filter "show me state-conditional candidates"
        # without joining through executive_summary.
        state_dependence=executive_summary.state_dependence,
        # D — surface_call_reason rolled up from the synthesizer's
        # re-derived call (NOT inherited from the triage record).
        surface_call_reason=executive_summary.surface_call_reason,
        # D — llm_family rolled up from executive_summary so the
        # catalog filter mirrors the headline value (single source of
        # truth: the synthesizer's call).
        llm_family=executive_summary.llm_family,
        # D — from surface_evidence (A1)
        evidence_grade=surface_evidence.evidence_grade,
        # D — from accessibility_risks (B)
        ecd_accessibility_class=accessibility_risks.ecd_size_assessment.ecd_accessibility_class,
        # D — bucketed
        evidence_density=_evidence_density(n_evidence),
        # L — from B's SynthesizerLLMFilters
        expression_level=filters_llm.expression_level,
        expression_breadth=filters_llm.expression_breadth,
        surface_specificity=filters_llm.surface_specificity,
        # D — accessibility-risks booleans
        has_shed_form=accessibility_risks.shed_form.present,
        has_secreted_form=accessibility_risks.secreted_form.present,
        requires_coreceptor_for_expression=(
            accessibility_risks.co_receptor_requirements.surface_expression_dependency == "required"
        ),
        # D — full 4-value enum so 'modulatory' isn't flattened away.
        co_receptor_dependency=(
            accessibility_risks.co_receptor_requirements.surface_expression_dependency
        ),
        has_epitope_masking=accessibility_risks.epitope_masking.severity in ("high", "moderate"),
        has_restricted_subdomain=has_restricted,
        # D — deterministic rollups (None until fetchers land)
        max_paralog_ecd_pct_identity=max_paralog,
        mouse_ortholog_ecd_pct_identity=_canonical_species_identity(deterministic_features.orthologs.mouse),
        cyno_ortholog_ecd_pct_identity=_canonical_species_identity(deterministic_features.orthologs.cynomolgus),
        # D — canonical topology terminal orientations
        n_term_extracellular=canon.n_terminal_orientation == "extracellular",
        c_term_extracellular=canon.c_terminal_orientation == "extracellular",
        # D — derived from filters_llm.expression_level so the headline
        # signal can't drift from this catalog filter. Replaces the
        # now-dropped HeadlineRisk.low_endogenous_expression value.
        low_endogenous_expression=_low_endog,
        # L — orphan-receptor flag from SynthesizerLLMFilters. Replaces
        # the now-dropped HeadlineRisk.ligand_unknown value.
        has_known_ligand=filters_llm.has_known_ligand,
        # D — stance-map counts derived above
        n_supporting_claims_high_weight=n_supporting_hi,
        n_contradicting_claims_high_weight=n_contradicting_hi,
        # D — OE+surface-localization derived above
        overexpression_surface_localization_observed=oe_surface_observed,
        # D — deep-block rollups derived above
        tumor_associated=tumor_associated,
        induction_trigger=induction_trigger,
        has_live_cell_surface_evidence=has_live_cell_surface_evidence,
        # ---- per-chip rationales ----------------------------------------
        # L — the four LLM-emitted rollup rationales, passed through verbatim.
        expression_level_rationale=filters_llm.expression_level_rationale,
        expression_breadth_rationale=filters_llm.expression_breadth_rationale,
        surface_specificity_rationale=filters_llm.surface_specificity_rationale,
        has_known_ligand_rationale=filters_llm.has_known_ligand_rationale,
        # D — the two composed rationales for the derived booleans.
        low_endogenous_expression_rationale=low_endog_rationale,
        overexpression_surface_localization_observed_rationale=oe_rationale,
    )
