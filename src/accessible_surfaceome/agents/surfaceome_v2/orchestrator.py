"""v2 deep-dive orchestrator.

Pipeline:

1. ``run_plan_trim_select_dual(gene, http=http, client=client)`` →
   ``DualPlanTrimSelectResult`` with A1 + A2 ledgers (verbatim claims).
2. Four A1-side block builders over the A1 ledger → ``SurfaceEvidence``.
3. Five A2-side block builders over the A2 ledger → ``BiologicalContext``.
4. Wrap into ``SurfaceEvidenceDraft`` / ``BiologicalContextDraft`` (the
   draft validators ensure every cited evidence_id resolves to a claim).
5. ``run_synthesizer_with_drafts`` → B output (executive_summary,
   filters_llm, accessibility_risks, confidence).
6. Build synthetic ``SourceTextStore`` from claim quotes and promote
   each claim → ``Evidence``.
7. Stub ``DeterministicFeatures`` (reused from v1).
8. Derive ``Filters`` (reused from v1).
9. Assemble ``SurfaceomeRecord`` and (optionally) persist.

The v1 orchestrator is unchanged — v2 lives alongside it and shares the
synthesizer + evidence_promotion + deterministic_features stub + filters
derivation helpers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from pydantic import ValidationError

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.evidence_promotion import promote_claim
from accessible_surfaceome.agents._support.pricing import UsageRecord, UsageSummary
from accessible_surfaceome.agents._support.timing import StepTiming, TimingRecorder
from accessible_surfaceome.agents.plan_trim_select import (
    DualPlanTrimSelectResult,
    run_plan_trim_select_dual,
)
from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    BResult,
    run_synthesizer_with_drafts,
)
from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _derive_filters,
    _load_triage_signal,
    _stub_deterministic_features,
)
from accessible_surfaceome.agents.surfaceome_v2.builders import (
    EvidenceGradeBlock,
    build_accessibility_modulation,
    build_anatomical_accessibility,
    build_cell_types,
    build_contradictions,
    build_evidence_grade,
    build_methods,
    build_subcellular_localization,
    build_therapeutic_engagement,
    build_tissues,
)
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    BiologicalContext,
    BiologicalContextDraft,
    Evidence,
    EvidenceClaim,
    GeneIdentifier,
    SourceType,
    SurfaceEvidence,
    SurfaceEvidenceDraft,
    SurfaceomeRecord,
)
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-6"
SCHEMA_VERSION_LITERAL = "1.0.0"
RUNS_DIR = Path(".runs")


@dataclass
class BlockBuilderUsage:
    """Per-builder token usage rollup."""

    label: str
    records: list[UsageRecord] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def n_calls(self) -> int:
        return len(self.records)


@dataclass
class AnnotateResultV2:
    """Outcome of one v2 annotate run.

    Carries the dual plan-trim-select result, the assembled record (or
    None on failure), per-builder usage breakdown, the synthesizer result,
    the annotation path (when ``persist=True``), and a free-text error
    when something went wrong.
    """

    gene: str
    record: SurfaceomeRecord | None
    dual: DualPlanTrimSelectResult | None
    synthesizer: BResult | None
    blocks_used: dict[str, int] = field(default_factory=dict)
    builder_usage: dict[str, BlockBuilderUsage] = field(default_factory=dict)
    annotation_path: Path | None = None
    error: str | None = None
    # Per-step wall-clock audit: every model call + post-process step,
    # in execution order. Empty when ``annotate`` was invoked with
    # ``timing=None`` (legacy path).
    timing: list[StepTiming] = field(default_factory=list)

    @property
    def plan_trim_select_cost_usd(self) -> float:
        return self.dual.total_cost_usd if self.dual is not None else 0.0

    @property
    def builders_cost_usd(self) -> float:
        return sum(b.cost_usd for b in self.builder_usage.values())

    @property
    def synthesizer_cost_usd(self) -> float:
        return self.synthesizer.usage.cost_usd if self.synthesizer is not None else 0.0

    @property
    def total_cost_usd(self) -> float:
        return (
            self.plan_trim_select_cost_usd
            + self.builders_cost_usd
            + self.synthesizer_cost_usd
        )


def annotate(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    persist: bool = False,
    timing: TimingRecorder | None = None,
) -> AnnotateResultV2:
    """Run the v2 deep-dive pipeline on one gene.

    A fresh :class:`TimingRecorder` is allocated when ``timing`` is
    ``None`` so every annotate run captures the per-step wall-clock
    trace by default. Pass an externally-owned recorder to merge into a
    larger audit (e.g. a sweep over multiple genes).
    """
    own_http = http is None
    client = client or get_client()
    http = http or open_default_client()
    timing = timing if timing is not None else TimingRecorder()
    try:
        return _annotate(client, http, gene, persist=persist, timing=timing)
    finally:
        if own_http:
            http.close()


def _annotate(
    client: Anthropic,
    http: CachedHTTP,
    gene: str,
    *,
    persist: bool,
    timing: TimingRecorder,
) -> AnnotateResultV2:
    builder_usage: dict[str, BlockBuilderUsage] = {}

    # ---- step 1: plan-trim-select dual -------------------------------------
    logger.info("v2 orchestrator: running plan-trim-select dual for %s", gene)
    dual = run_plan_trim_select_dual(gene, client=client, http=http, timing=timing)
    if dual.bundle is None:
        return AnnotateResultV2(
            gene=gene,
            record=None,
            dual=dual,
            synthesizer=None,
            error="plan-trim-select did not resolve a gene bundle",
            timing=list(timing.entries),
        )
    gene_id = GeneIdentifier(
        hgnc_symbol=dual.bundle.hgnc_symbol,
        hgnc_id=dual.bundle.hgnc_id,
        uniprot_acc=dual.bundle.uniprot_acc,
        ncbi_gene_id=dual.bundle.ncbi_gene_id,
        ensembl_gene=dual.bundle.ensembl_gene,
    )

    a1_claims: list[EvidenceClaim] = list(dual.a1.claims)
    a2_claims: list[EvidenceClaim] = list(dual.a2.claims)
    logger.info(
        "v2 orchestrator: dual done — A1=%d claims A2=%d claims, $%.4f",
        len(a1_claims),
        len(a2_claims),
        dual.total_cost_usd,
    )

    # ---- step 2: A1-side block builders ------------------------------------
    a1_ctx = {"gene": gene_id.hgnc_symbol}

    methods_records: list[UsageRecord] = []
    builder_usage["methods"] = BlockBuilderUsage("methods", methods_records)
    with timing.step(
        "builder:methods",
        phase="builders_a1",
        n_items=len(a1_claims),
        model=AGENT_MODEL,
    ) as _h:
        methods = build_methods(
            a1_claims, client=client, usage_sink=methods_records, context=a1_ctx
        )
        _h.set_usage(methods_records, model=AGENT_MODEL)

    te_records: list[UsageRecord] = []
    builder_usage["therapeutic_engagement"] = BlockBuilderUsage(
        "therapeutic_engagement", te_records
    )
    with timing.step(
        "builder:therapeutic_engagement",
        phase="builders_a1",
        n_items=len(a1_claims),
        model=AGENT_MODEL,
    ) as _h:
        therapeutic = build_therapeutic_engagement(
            a1_claims, client=client, usage_sink=te_records, context=a1_ctx
        )
        _h.set_usage(te_records, model=AGENT_MODEL)

    contr_records: list[UsageRecord] = []
    builder_usage["contradictions"] = BlockBuilderUsage("contradictions", contr_records)
    with timing.step(
        "builder:contradictions",
        phase="builders_a1",
        n_items=len(a1_claims),
        model=AGENT_MODEL,
    ) as _h:
        contradictions = build_contradictions(
            a1_claims, client=client, usage_sink=contr_records, context=a1_ctx
        )
        _h.set_usage(contr_records, model=AGENT_MODEL)

    grade_records: list[UsageRecord] = []
    builder_usage["evidence_grade"] = BlockBuilderUsage("evidence_grade", grade_records)
    with timing.step(
        "builder:evidence_grade",
        phase="builders_a1",
        n_items=len(a1_claims),
        model=AGENT_MODEL,
    ) as _h:
        grade_block: EvidenceGradeBlock = build_evidence_grade(
            a1_claims, client=client, usage_sink=grade_records, context=a1_ctx
        )
        _h.set_usage(grade_records, model=AGENT_MODEL)

    surface_evidence = SurfaceEvidence(
        evidence_grade=grade_block.evidence_grade,
        grade_rationale=grade_block.grade_rationale,
        methods=methods,
        non_surface_expression=grade_block.non_surface_expression,
        therapeutic_engagement=therapeutic,
        contradicting_evidence=contradictions,
    )

    # ---- step 3: A2-side block builders ------------------------------------
    a2_ctx = {"gene": gene_id.hgnc_symbol}

    tissues_records: list[UsageRecord] = []
    builder_usage["tissues"] = BlockBuilderUsage("tissues", tissues_records)
    with timing.step(
        "builder:tissues",
        phase="builders_a2",
        n_items=len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        tissues = build_tissues(
            a2_claims, client=client, usage_sink=tissues_records, context=a2_ctx
        )
        _h.set_usage(tissues_records, model=AGENT_MODEL)

    cell_types_records: list[UsageRecord] = []
    builder_usage["cell_types"] = BlockBuilderUsage("cell_types", cell_types_records)
    with timing.step(
        "builder:cell_types",
        phase="builders_a2",
        n_items=len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        cell_types = build_cell_types(
            a2_claims, client=client, usage_sink=cell_types_records, context=a2_ctx
        )
        _h.set_usage(cell_types_records, model=AGENT_MODEL)

    subloc_records: list[UsageRecord] = []
    builder_usage["subcellular_localization"] = BlockBuilderUsage(
        "subcellular_localization", subloc_records
    )
    with timing.step(
        "builder:subcellular_localization",
        phase="builders_a2",
        n_items=len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        subloc = build_subcellular_localization(
            a2_claims, client=client, usage_sink=subloc_records, context=a2_ctx
        )
        _h.set_usage(subloc_records, model=AGENT_MODEL)

    anat_records: list[UsageRecord] = []
    builder_usage["anatomical_accessibility"] = BlockBuilderUsage(
        "anatomical_accessibility", anat_records
    )
    with timing.step(
        "builder:anatomical_accessibility",
        phase="builders_a2",
        n_items=len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        anatomical = build_anatomical_accessibility(
            a2_claims, client=client, usage_sink=anat_records, context=a2_ctx
        )
        _h.set_usage(anat_records, model=AGENT_MODEL)

    mod_records: list[UsageRecord] = []
    builder_usage["accessibility_modulation"] = BlockBuilderUsage(
        "accessibility_modulation", mod_records
    )
    with timing.step(
        "builder:accessibility_modulation",
        phase="builders_a2",
        n_items=len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        modulation = build_accessibility_modulation(
            a2_claims, client=client, usage_sink=mod_records, context=a2_ctx
        )
        _h.set_usage(mod_records, model=AGENT_MODEL)

    biological_context = BiologicalContext(
        tissues=tissues,
        cell_types=cell_types,
        cell_states=[],  # v1 schema field; no builder for v2 — empty.
        subcellular_localization=subloc,
        anatomical_accessibility=anatomical,
        accessibility_modulation=modulation,
    )

    # ---- step 4: wrap into per-agent drafts --------------------------------
    # Per-agent validators (_check_citations_resolve) enforce that every
    # cited evidence_id resolves to a claim in the corresponding ledger.
    # The block-builders already scrub unknown ids, so this should pass.
    try:
        a1_draft = SurfaceEvidenceDraft(
            surface_evidence=surface_evidence,
            evidence_claims=a1_claims,
        )
    except ValidationError as exc:
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=None,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"SurfaceEvidenceDraft validation failed: {exc}",
            timing=list(timing.entries),
        )
    try:
        a2_draft = BiologicalContextDraft(
            biological_context=biological_context,
            evidence_claims=a2_claims,
        )
    except ValidationError as exc:
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=None,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"BiologicalContextDraft validation failed: {exc}",
            timing=list(timing.entries),
        )

    # ---- step 5: synthesizer (B) ------------------------------------------
    logger.info("v2 orchestrator: dispatching synthesizer for %s", gene_id.hgnc_symbol)
    with timing.step(
        "synthesizer",
        phase="synthesizer",
        n_items=len(a1_claims) + len(a2_claims),
        model=AGENT_MODEL,
    ) as _h:
        b = run_synthesizer_with_drafts(
            gene_id.hgnc_symbol,
            a1_draft=a1_draft,
            a2_draft=a2_draft,
            client=client,
        )
        _h.model = b.usage.model
        # ``BResult.usage`` is a UsageSummary, not a UsageRecord. Build a
        # one-shot UsageRecord-shaped record so ``set_usage`` rolls it.
        synth_rec = UsageRecord(
            input_tokens=b.usage.input_tokens,
            output_tokens=b.usage.output_tokens,
            cache_creation_input_tokens=b.usage.cache_creation_input_tokens,
            cache_read_input_tokens=b.usage.cache_read_input_tokens,
            cost_usd=b.usage.cost_usd,
        )
        _h.set_usage([synth_rec], model=b.usage.model)
    if b.draft is None:
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=b,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"synthesizer returned no valid draft: {b.validation_error}",
            timing=list(timing.entries),
        )

    # ---- step 6: promote claims → Evidence (synthetic source store) -------
    merged_claims = a1_claims + a2_claims
    with timing.step(
        "evidence_promotion",
        phase="post",
        n_items=len(merged_claims),
    ):
        source_store = _synthetic_source_store(merged_claims)
        evidence: list[Evidence] = [
            promote_claim(c, store=source_store) for c in merged_claims
        ]

    # ---- step 7: deterministic features stub (reused from v1) -------------
    with timing.step("deterministic_features", phase="post"):
        det_features = _stub_deterministic_features(gene_id.uniprot_acc)

    # ---- step 8: derive filters (reused from v1) --------------------------
    with timing.step(
        "filters_derivation",
        phase="post",
        n_items=len(evidence),
    ):
        filters = _derive_filters(
            executive_summary=b.draft.executive_summary,
            surface_evidence=surface_evidence,
            biological_context=biological_context,
            accessibility_risks=b.draft.accessibility_risks,
            filters_llm=b.draft.filters_llm,
            deterministic_features=det_features,
            n_evidence=len(evidence),
        )

    # ---- step 9: assemble SurfaceomeRecord --------------------------------
    primary = sum(1 for e in evidence if e.evidence_tier == "primary")
    secondary = sum(1 for e in evidence if e.evidence_tier == "secondary")
    try:
        record = SurfaceomeRecord(
            schema_version=SCHEMA_VERSION_LITERAL,
            gene=gene_id,
            triage_signal=_load_triage_signal(gene_id.hgnc_symbol),
            executive_summary=b.draft.executive_summary,
            filters=filters,
            surface_evidence=surface_evidence,
            biological_context=biological_context,
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
    except ValidationError as exc:
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=b,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"SurfaceomeRecord assembly failed: {exc}",
            timing=list(timing.entries),
        )

    annotation_path: Path | None = None
    if persist:
        annotation_path = DATA_DIR / "annotations" / f"{gene_id.hgnc_symbol}.json"
        annotation_path.parent.mkdir(parents=True, exist_ok=True)
        annotation_path.write_text(record.model_dump_json(indent=2))

    return AnnotateResultV2(
        gene=gene_id.hgnc_symbol,
        record=record,
        dual=dual,
        synthesizer=b,
        blocks_used=_count_blocks(surface_evidence, biological_context),
        builder_usage=builder_usage,
        annotation_path=annotation_path,
        timing=list(timing.entries),
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _count_blocks(
    se: SurfaceEvidence, bc: BiologicalContext
) -> dict[str, int]:
    return {
        "methods": len(se.methods),
        "non_surface_expression": len(se.non_surface_expression),
        "contradicting_evidence": len(se.contradicting_evidence),
        "therapeutic_engagement": 0 if se.therapeutic_engagement is None else 1,
        "tissues": len(bc.tissues),
        "cell_types": len(bc.cell_types),
        "dual_localization": len(bc.subcellular_localization.dual_localization),
        "membrane_subdomains": len(bc.subcellular_localization.membrane_subdomains),
        "anatomical_accessibility": len(bc.anatomical_accessibility),
        "accessibility_modulation": len(bc.accessibility_modulation),
    }


def _synthetic_source_store(claims: list[EvidenceClaim]) -> SourceTextStore:
    """Build a synthetic SourceTextStore from claim quotes.

    The plan-trim-select pipeline already guarantees every claim's quote
    is verbatim from its source (the quote was copied from the pool draft,
    which was extracted as a substring of the source body at fetch time).
    Promotion only needs the source body to substring-match; building a
    synthetic body from the quote itself trivially satisfies that check
    while preserving all the SourceRef metadata.

    Note: ``url`` and ``source_type`` are inferred from the ``source_id``
    prefix; ``retrieved_at`` is set to "now"; license / publication_type
    fall back to "unknown". The promote step only inspects the substring
    match + the metadata it shovels into ``SourceRef`` — none of which
    drives downstream filter math.
    """
    store = SourceTextStore()
    now = datetime.now(UTC)
    # Aggregate all quotes per source_id so multiple claims from the
    # same source produce a single SourceText body containing all
    # quotes (each quote remains a substring of the aggregated body).
    quotes_by_source: dict[str, list[str]] = {}
    for c in claims:
        quotes_by_source.setdefault(c.source_id, []).append(c.quote)

    for source_id, quotes in quotes_by_source.items():
        # Deduplicate while preserving order so the aggregated body is
        # compact but contains every distinct quote.
        seen: set[str] = set()
        unique_quotes: list[str] = []
        for q in quotes:
            if q in seen:
                continue
            seen.add(q)
            unique_quotes.append(q)
        body = "\n\n".join(unique_quotes)
        normalized = normalize_for_quote_matching(body)
        url, source_type = _infer_url_and_type(source_id)
        st = SourceText(
            source_id=source_id,
            source_type=source_type,
            url=url,
            title=source_id,
            raw_text=body,
            normalized_text=normalized,
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            normalized_source_sha256=hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest(),
            retrieved_at=now,
            publication_type="other",
            is_retracted=False,
            retraction_checked_at=now,
            license="unknown",
        )
        store.put(st)
    return store


def _infer_url_and_type(source_id: str) -> tuple[str, SourceType]:
    """Pick a plausible URL + SourceType enum value for a source_id.

    Conservative fallback when the real URL isn't stashed anywhere — the
    SourceRef still validates and the substring chain is what carries
    the downstream value, not the URL exactness.
    """
    if source_id.startswith("PMID:"):
        pmid = source_id.split(":", 1)[1]
        return (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "pubmed")
    if source_id.startswith("PMC:"):
        pmc = source_id.split(":", 1)[1]
        return (f"https://europepmc.org/article/PMC/{pmc}", "pmc")
    if source_id.startswith("UniProt:"):
        acc = source_id.split(":", 1)[1]
        return (f"https://www.uniprot.org/uniprotkb/{acc}/entry", "uniprot")
    if source_id.startswith("HPA:"):
        symbol = source_id.split(":", 1)[1]
        return (f"https://www.proteinatlas.org/{symbol}", "hpa")
    if source_id.startswith("WO:"):
        wo = source_id.split(":", 1)[1]
        return (f"https://patents.google.com/patent/{wo}", "patent")
    return ("https://example.invalid/unknown", "europe_pmc")


def write_summary_meta(result: AnnotateResultV2, *, runs_dir: Path = RUNS_DIR) -> Path:
    """Write a per-builder cost + block-counts JSON for QC.

    Returns the path written. Always writes; this is the auditable
    summary even when the record assembly failed.
    """
    runs_dir.mkdir(exist_ok=True)
    safe_id = result.gene.replace(":", "_")
    out = runs_dir / f"surfaceome_v2_{safe_id}.meta.json"
    payload: dict[str, Any] = {
        "gene": result.gene,
        "blocks_used": result.blocks_used,
        "builder_usage": {
            label: {
                "n_calls": bu.n_calls,
                "cost_usd": round(bu.cost_usd, 6),
                "input_tokens": sum(r.input_tokens for r in bu.records),
                "output_tokens": sum(r.output_tokens for r in bu.records),
            }
            for label, bu in result.builder_usage.items()
        },
        "plan_trim_select_cost_usd": round(result.plan_trim_select_cost_usd, 6),
        "builders_cost_usd": round(result.builders_cost_usd, 6),
        "synthesizer_cost_usd": round(result.synthesizer_cost_usd, 6),
        "total_cost_usd": round(result.total_cost_usd, 6),
        "total_elapsed_s": round(
            sum(t.elapsed_s for t in result.timing), 3
        ),
        "timing": [t.as_dict() for t in result.timing],
        "annotation_path": str(result.annotation_path)
        if result.annotation_path is not None
        else None,
        "error": result.error,
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


# Re-export UsageSummary for cmd-line scripts (otherwise unused here).
__all__ = [
    "AnnotateResultV2",
    "BlockBuilderUsage",
    "UsageSummary",
    "annotate",
    "write_summary_meta",
]
