"""v1.0.0 deep-dive orchestrator.

Dispatches the documented 3-agent topology, promotes the merged
``EvidenceClaim`` ledger into substring-anchored ``Evidence``, derives the
deterministic ``filters`` rollups, stubs ``deterministic_features`` (the
DeepTMHMM / Compara / AlphaFold fetchers are deferred), and assembles a full
``SurfaceomeRecord`` written to ``data/annotations/{gene}.json``.

Pipeline:

    1. gene_lookup.resolve(symbol) → IdentifierBundle → GeneIdentifier
    2. parallel dispatch A1 (Surface Evidence Compiler) ∥ A2 (Biology Compiler)
       — shared SourceTextStore + retraction_index across both agents
    3. promote EvidenceClaim → Evidence (substring-anchored against the
       merged source store)
    4. dispatch B (Synthesizer) over both drafts in-memory; B has no tools
       so it physically can't invent citations
    5. derive 14 deterministic Filters rollups from B's blocks + the
       (stubbed) DeterministicFeatures
    6. assemble SurfaceomeRecord and persist

The orchestrator never writes to ``deterministic_features`` from anywhere
except its own fetchers; the schema's Draft-level ``_reject_deterministic_features``
validator enforces the same boundary on the agent side.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents.biology_compiler.runner import (
    A2Result,
    run_biology_compiler,
)
from accessible_surfaceome.agents._support.evidence_promotion import promote_claim
from accessible_surfaceome.agents.surface_evidence_compiler.runner import (
    A1Result,
    run_surface_evidence_compiler,
)
from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    BResult,
    run_synthesizer_with_drafts,
)
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared import retraction_watch as _retraction_watch
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContext,
    DeterministicFeatures,
    Evidence,
    EvidenceDensity,
    ExecutiveSummary,
    Filters,
    GeneIdentifier,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
    SurfaceEvidence,
    SurfaceomeRecord,
    SynthesizerLLMFilters,
    TriageRecord,
    TriageSignal,
)
from accessible_surfaceome.tools._shared.source_text import SourceTextStore
from accessible_surfaceome.tools.gene_lookup import resolve as _resolve

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-6"  # all three agents currently run on Sonnet 4.6
SCHEMA_VERSION_LITERAL = "1.0.0"
RUNS_DIR = Path(".runs")


@dataclass
class AnnotateResult:
    """Outcome of one v1.0.0 annotate run.

    Cost properties (``a1_cost_usd`` etc.) are derived from each agent's
    ``UsageSummary`` and are ``0.0`` when the corresponding agent didn't run
    (e.g. resolver failed before A1 dispatch). The orchestrator persists the
    per-iteration usage trace into ``.runs/{a1,a2,b}_<gene>.meta.json``
    alongside the existing tool-call trace.
    """

    gene: str
    record: SurfaceomeRecord | None
    a1: A1Result | None
    a2: A2Result | None
    b: BResult | None
    annotation_path: Path | None
    error: str | None = None

    @property
    def a1_cost_usd(self) -> float:
        return self.a1.usage.cost_usd if self.a1 is not None else 0.0

    @property
    def a2_cost_usd(self) -> float:
        return self.a2.usage.cost_usd if self.a2 is not None else 0.0

    @property
    def b_cost_usd(self) -> float:
        return self.b.usage.cost_usd if self.b is not None else 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.a1_cost_usd + self.a2_cost_usd + self.b_cost_usd


def annotate(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    persist: bool = True,
) -> AnnotateResult:
    """Run the v1.0.0 deep-dive pipeline on one gene.

    Parameters
    ----------
    gene:
        HGNC symbol or UniProt accession.
    client / http:
        Optional reuse hooks for testing or batch runs.
    persist:
        When True (default) writes ``data/annotations/{symbol}.json``.
    """
    own_http = http is None
    client = client or get_client()
    http = http or open_default_client()
    try:
        return _annotate(client, http, gene, persist=persist)
    finally:
        if own_http:
            http.close()


def _annotate(
    client: Anthropic,
    http: CachedHTTP,
    gene: str,
    *,
    persist: bool,
) -> AnnotateResult:
    # ----------------------------- step 1: resolve identifiers -----------------------------
    bundle = _resolve(gene, http=http)
    gene_id = GeneIdentifier(
        hgnc_symbol=bundle.hgnc_symbol,
        hgnc_id=bundle.hgnc_id,
        uniprot_acc=bundle.uniprot_acc,
        ncbi_gene_id=bundle.ncbi_gene_id,
        ensembl_gene=bundle.ensembl_gene,
    )
    logger.info(
        "v1 orchestrator: resolved %s → %s / %s",
        gene, gene_id.hgnc_symbol, gene_id.uniprot_acc,
    )

    # ----------------------------- step 2: A1 ∥ A2 parallel dispatch -----------------------
    # Single SourceTextStore + retraction_index so every tool-result body lands
    # in one place; promote_claim() in step 3 substring-matches against it.
    source_store = SourceTextStore()
    retraction_index = _retraction_watch.from_http(http)
    logger.info("v1 orchestrator: dispatching A1 ∥ A2 for %s", gene_id.hgnc_symbol)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="surfaceome_v1") as ex:
        a1_future = ex.submit(
            run_surface_evidence_compiler,
            gene_id.hgnc_symbol,
            client=client, http=http,
            source_store=source_store, retraction_index=retraction_index,
        )
        a2_future = ex.submit(
            run_biology_compiler,
            gene_id.hgnc_symbol,
            client=client, http=http,
            source_store=source_store, retraction_index=retraction_index,
        )
        a1 = a1_future.result()
        a2 = a2_future.result()

    # Persist per-iteration usage + tool-call traces regardless of validation
    # outcome. The meta file is the durable record of "what did this run
    # spend / do?" — losing it on a bad-JSON failure is exactly the case we
    # want to debug from.
    _write_meta(gene_id.hgnc_symbol, "a1", a1=a1)
    _write_meta(gene_id.hgnc_symbol, "a2", a2=a2)

    if a1.draft is None:
        msg = f"A1 returned invalid draft for {gene_id.hgnc_symbol}: {a1.validation_error}"
        logger.error(msg)
        return AnnotateResult(gene_id.hgnc_symbol, None, a1, a2, None, None, error=msg)
    if a2.draft is None:
        msg = f"A2 returned invalid draft for {gene_id.hgnc_symbol}: {a2.validation_error}"
        logger.error(msg)
        return AnnotateResult(gene_id.hgnc_symbol, None, a1, a2, None, None, error=msg)
    logger.info(
        "v1 orchestrator: A1+A2 done (a1=%d claims, a2=%d claims, a1 repairs=%d, a2 repairs=%d)",
        len(a1.draft.evidence_claims), len(a2.draft.evidence_claims),
        a1.n_repair_attempts, a2.n_repair_attempts,
    )

    # ----------------------------- step 3: dispatch B over both drafts ---------------------
    logger.info("v1 orchestrator: dispatching B (Synthesizer) for %s", gene_id.hgnc_symbol)
    b = run_synthesizer_with_drafts(
        gene_id.hgnc_symbol,
        a1_draft=a1.draft, a2_draft=a2.draft, client=client,
    )
    _write_meta(gene_id.hgnc_symbol, "b", b=b)
    if b.draft is None:
        msg = f"B returned invalid draft for {gene_id.hgnc_symbol}: {b.validation_error}"
        logger.error(msg)
        return AnnotateResult(gene_id.hgnc_symbol, None, a1, a2, b, None, error=msg)

    # ----------------------------- step 4: promote claims → Evidence -----------------------
    merged_claims = list(a1.draft.evidence_claims) + list(a2.draft.evidence_claims)
    evidence: list[Evidence] = [
        promote_claim(claim, store=source_store) for claim in merged_claims
    ]
    n_verified = sum(1 for e in evidence if e.entailment_verified)
    logger.info(
        "v1 orchestrator: promoted %d claims → Evidence (substring-anchored: %d/%d)",
        len(evidence), n_verified, len(evidence),
    )

    # ----------------------------- step 5: derive filters ----------------------------------
    det_features = _stub_deterministic_features(gene_id.uniprot_acc)
    filters = _derive_filters(
        executive_summary=b.draft.executive_summary,
        surface_evidence=a1.draft.surface_evidence,
        biological_context=a2.draft.biological_context,
        accessibility_risks=b.draft.accessibility_risks,
        filters_llm=b.draft.filters_llm,
        deterministic_features=det_features,
        n_evidence=len(evidence),
    )

    # ----------------------------- step 6: assemble + persist ------------------------------
    primary = sum(1 for e in evidence if e.evidence_tier == "primary")
    secondary = sum(1 for e in evidence if e.evidence_tier == "secondary")
    record = SurfaceomeRecord(
        schema_version=SCHEMA_VERSION_LITERAL,
        gene=gene_id,
        triage_signal=_load_triage_signal(gene_id.hgnc_symbol),
        executive_summary=b.draft.executive_summary,
        filters=filters,
        surface_evidence=a1.draft.surface_evidence,
        biological_context=a2.draft.biological_context,
        deterministic_features=det_features,
        accessibility_risks=b.draft.accessibility_risks,
        evidence=evidence,
        search_log=[],
        evidence_count=len(evidence),
        primary_evidence_count=primary,
        secondary_evidence_count=secondary,
        confidence=b.draft.confidence,
        confidence_reasoning=b.draft.confidence_reasoning,
        model_path=AGENT_MODEL,
        record_generated_at=datetime.now(UTC),
    )

    annotation_path: Path | None = None
    if persist:
        annotation_path = DATA_DIR / "annotations" / f"{gene_id.hgnc_symbol}.json"
        annotation_path.parent.mkdir(parents=True, exist_ok=True)
        annotation_path.write_text(record.model_dump_json(indent=2))
        logger.info("v1 orchestrator: wrote %s", annotation_path)

    return AnnotateResult(
        gene=gene_id.hgnc_symbol,
        record=record, a1=a1, a2=a2, b=b,
        annotation_path=annotation_path,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_meta(
    gene: str,
    agent: str,
    *,
    a1: A1Result | None = None,
    a2: A2Result | None = None,
    b: BResult | None = None,
) -> None:
    """Persist ``.runs/{agent}_{gene}.meta.json`` with tool-calls + usage.

    Mirrors the JSON shape the standalone-CLI ``_main`` blocks already write,
    so a meta file produced by ``annotate`` and one produced by running an
    individual runner module are interchangeable for downstream cost analysis.
    """
    RUNS_DIR.mkdir(exist_ok=True)
    if agent == "a1" and a1 is not None:
        meta: dict[str, object] = {
            "gene": gene,
            "n_tool_calls": a1.n_tool_calls,
            "n_repair_attempts": a1.n_repair_attempts,
            "tool_calls": [
                {"name": tc.name, "input": tc.input_summary, "error": tc.is_error}
                for tc in a1.tool_calls
            ],
            "validation_error": a1.validation_error,
            "usage": a1.usage.as_dict(),
        }
    elif agent == "a2" and a2 is not None:
        meta = {
            "gene": gene,
            "n_tool_calls": a2.n_tool_calls,
            "n_repair_attempts": a2.n_repair_attempts,
            "tool_calls": [
                {"name": tc.name, "input": tc.input_summary, "error": tc.is_error}
                for tc in a2.tool_calls
            ],
            "validation_error": a2.validation_error,
            "usage": a2.usage.as_dict(),
        }
    elif agent == "b" and b is not None:
        meta = {
            "gene": gene,
            "n_tool_calls": b.n_tool_calls,
            "n_repair_attempts": b.n_repair_attempts,
            "validation_error": b.validation_error,
            "usage": b.usage.as_dict(),
        }
    else:
        return
    (RUNS_DIR / f"{agent}_{gene}.meta.json").write_text(json.dumps(meta, indent=2))


_TRIAGE_VERDICT_TO_SIGNAL: dict[str, TriageSignal] = {
    "yes": "likely_accessible",
    "contextual": "possibly_accessible",
    "no": "unlikely",
}


def _load_triage_signal(symbol: str) -> TriageSignal:
    """Map the latest persisted triage record (if any) onto the record's
    ``triage_signal`` enum; default ``unknown`` when no triage exists.
    """
    triage_path = DATA_DIR / "triage" / f"{symbol}.json"
    if not triage_path.exists():
        return "unknown"
    try:
        record = TriageRecord.model_validate_json(triage_path.read_text())
    except Exception as exc:  # noqa: BLE001 — best-effort; a malformed triage shouldn't fail annotate
        logger.warning("triage record for %s failed to parse: %s", symbol, exc)
        return "unknown"
    return _TRIAGE_VERDICT_TO_SIGNAL.get(record.verdict, "unknown")


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
        afdb_id=f"AF-{uniprot_acc}-F1-model_v4",
        afdb_version="v4",
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

    # restricted_subdomain rollup: either the explicit risk flag fires, OR any
    # anatomical_accessibility entry tags the orientation as restricted.
    has_restricted = (
        accessibility_risks.restricted_subdomain.present
        or any(
            obs.accessibility_implication == "restricted"
            for obs in biological_context.anatomical_accessibility
        )
    )

    # max-paralog identity is None when there are no paralogs (the stub case
    # while fetchers are deferred); same for cross-species rollups.
    max_paralog = (
        max((p.ecd_pct_identity for p in deterministic_features.paralogs), default=None)
        if deterministic_features.paralogs
        else None
    )

    def _canonical_species_identity(entries: list) -> float | None:
        for e in entries:
            if e.is_canonical:
                return e.ecd_pct_identity_to_human_canonical
        return None

    return Filters(
        # D — from executive_summary (B)
        surface_accessibility=executive_summary.surface_accessibility,
        confidence=executive_summary.confidence,
        subcategory=executive_summary.subcategory,
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
        has_epitope_masking=accessibility_risks.epitope_masking.severity in ("high", "moderate"),
        has_restricted_subdomain=has_restricted,
        # D — deterministic rollups (None until fetchers land)
        max_paralog_ecd_pct_identity=max_paralog,
        mouse_ortholog_ecd_pct_identity=_canonical_species_identity(deterministic_features.orthologs.mouse),
        cyno_ortholog_ecd_pct_identity=_canonical_species_identity(deterministic_features.orthologs.cynomolgus),
        # D — canonical topology terminal orientations
        n_term_extracellular=canon.n_terminal_orientation == "extracellular",
        c_term_extracellular=canon.c_terminal_orientation == "extracellular",
    )


def _main(argv: list[str] | None = None) -> int:
    import sys

    from accessible_surfaceome.env import load_env

    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = argv if argv is not None else sys.argv[1:]
    gene = args[0] if args else "EGFR"

    result = annotate(gene)
    print(f"\n=== v1.0.0 annotate result for {gene} ===")
    if result.error:
        print(f"FAILED: {result.error}")
        return 1
    assert result.record is not None  # for ty
    rec = result.record
    print(f"VALID — wrote {result.annotation_path}")
    print(
        f"executive: accessibility={rec.executive_summary.surface_accessibility} "
        f"grade={rec.surface_evidence.evidence_grade} confidence={rec.confidence}"
    )
    print(
        f"counts: methods={len(rec.surface_evidence.methods)} "
        f"tissues={len(rec.biological_context.tissues)} "
        f"evidence={rec.evidence_count} (primary={rec.primary_evidence_count} "
        f"secondary={rec.secondary_evidence_count})"
    )
    print(
        f"cost: A1=${result.a1_cost_usd:.4f}  A2=${result.a2_cost_usd:.4f}  "
        f"B=${result.b_cost_usd:.4f}  total=${result.total_cost_usd:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
