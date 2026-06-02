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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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
from accessible_surfaceome.agents.plan_trim_select.runner import (
    SearchLogEntry,
    _summarize_triage_for_planner,
)
from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    BResult,
    run_synthesizer_with_drafts,
)
from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _attach_deterministic_families,
    _derive_filters,
    _attach_deterministic_families,
    scrub_headline_risks,
    _load_triage_record,
    _TRIAGE_VERDICT_TO_SIGNAL,
    _stub_deterministic_features,
)
from accessible_surfaceome.agents.surfaceome_v2.builders import (
    EvidenceGradeBlock,
    build_accessibility_modulation,
    build_anatomical_accessibility,
    build_cell_states,
    build_contradictions,
    build_evidence_grade,
    build_expression,
    build_methods,
    build_subcellular_localization,
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
    IsoformTopology,
    SearchEntry,
    SourceType,
    SurfaceEvidence,
    SurfaceEvidenceDraft,
    SurfaceomeRecord,
)
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-6"
SCHEMA_VERSION_LITERAL = "1.1.0"
RUNS_DIR = Path(".runs")


def _triage_signal_and_reasoning_from_record(rec):
    """Map a loaded ``TriageRecord`` onto the deep-dive record's
    ``(triage_signal, triage_reasoning)`` pair.

    Local helper (previously imported from the v1 orchestrator, which no
    longer exports it). Reuses v1's ``_TRIAGE_VERDICT_TO_SIGNAL`` map so the
    verdict→signal mapping stays single-sourced; the reasoning prose is the
    triage's own ``verdict_reasoning``. ``rec`` may be ``None`` when no triage
    exists for the gene → default to the unknown signal + empty prose.
    """
    if rec is None:
        return "unknown", ""
    return _TRIAGE_VERDICT_TO_SIGNAL.get(rec.verdict, "unknown"), rec.verdict_reasoning

# Maximum block-builders to dispatch concurrently. There are 7 builders
# total (3 A1 + 4 A2 — tissues + cell_types merged into one `expression`
# builder); they consume independent claim slices and each makes a single
# Sonnet call, so a worker pool sized to ``7`` lets every builder kick off
# immediately. The Anthropic client is thread-safe
# (httpx underneath) and each builder writes to its own ``usage_sink``
# list so there's no shared mutable state across workers. The shared
# ``TimingRecorder`` appends rows from multiple threads — CPython's
# ``list.append`` is atomic under the GIL, so the list stays
# well-formed; the resulting timing-row order is non-deterministic but
# the viewer sorts by ``elapsed_s`` anyway.
BUILDER_CONCURRENCY = 7


def _secreted_isoform_ids(isoform_topologies: list[IsoformTopology]) -> list[str]:
    """IDs of isoforms that are soluble forms by topology alone.

    A TM-less alternative isoform that still carries a real ECD (≥30 aa) is a
    soluble/secreted species: the membrane anchor is gone but the ectodomain
    is retained (e.g. EGFR's sEGFR isoforms). ``isoform_topologies`` holds
    ONLY the alternative isoforms (the canonical lives in
    ``canonical_topology``), so every entry is non-canonical by construction
    — there is NO ``is_canonical`` field on ``IsoformTopology`` (referencing
    one raised AttributeError and crashed every v2 run; see the regression
    test). Extracted so the secreted-form upgrade is unit-testable without a
    full annotate run."""
    return [
        iso.isoform_id
        for iso in isoform_topologies
        if iso.tm_helix_count == 0 and iso.ecd_length_residues >= 30
    ]


def _wall_clock_for_timing(timing: list[StepTiming]) -> float:
    """End-to-end wall clock for a timing list.

    Same semantics as :attr:`TimingRecorder.wall_clock_s`: parses each
    row's ``started_at`` ISO string and returns ``max(end) - min(start)``.
    Used by ``write_summary_meta`` because it operates on a frozen
    ``list[StepTiming]`` snapshot rather than the live recorder.
    """
    if not timing:
        return 0.0
    starts: list[float] = []
    ends: list[float] = []
    for e in timing:
        try:
            t = datetime.fromisoformat(
                e.started_at.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            continue
        starts.append(t)
        ends.append(t + e.elapsed_s)
    if not starts:
        return 0.0
    return round(max(ends) - min(starts), 3)


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
class _BuilderSpec:
    """One block-builder invocation packaged for concurrent dispatch.

    Carries the builder callable + its claim slice + the gene context
    dict the builder expects. ``phase`` is the timing-bucket label so
    the HTML viewer's Section 0.5 can color A1 vs A2 builders distinctly.
    """

    name: str
    phase: str  # "builders_a1" or "builders_a2"
    fn: Callable[..., Any]
    claims: list[EvidenceClaim]
    ctx: dict[str, Any]


def _run_builders_concurrently(
    specs: list[_BuilderSpec],
    *,
    client: Anthropic,
    timing: TimingRecorder,
    builder_usage: dict[str, BlockBuilderUsage],
) -> dict[str, Any]:
    """Dispatch every builder spec on a thread pool, gather results.

    Side effects:
      * Populates ``builder_usage[spec.name]`` with the per-builder
        UsageRecord list (so the existing cost-rollup properties keep
        working).
      * Appends one ``StepTiming`` row per builder to ``timing``.

    Concurrency invariants:
      * The Anthropic client object is shared across workers — that's
        safe (the SDK uses httpx with connection pooling).
      * Each builder writes only to its own ``UsageRecord`` list, so
        token-accounting state is per-thread.
      * Two threads never race on the same ``builder_usage`` key (each
        spec has a unique ``name``); CPython's GIL makes the individual
        dict ``__setitem__`` atomic.
      * Reads from ``builder_usage`` happen only after every future has
        resolved, eliminating publication races.

    A worker exception propagates through ``Future.result()`` and
    aborts the whole annotate run — matches the pre-parallel behavior
    where a builder failure raised out of the orchestrator.
    """

    def _runner(spec: _BuilderSpec) -> tuple[str, Any, list[UsageRecord]]:
        records: list[UsageRecord] = []
        with timing.step(
            f"builder:{spec.name}",
            phase=spec.phase,
            n_items=len(spec.claims),
            model=AGENT_MODEL,
        ) as handle:
            result = spec.fn(
                spec.claims, client=client, usage_sink=records, context=spec.ctx
            )
            handle.set_usage(records, model=AGENT_MODEL)
        return spec.name, result, records

    outputs: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=BUILDER_CONCURRENCY) as executor:
        futures = [executor.submit(_runner, spec) for spec in specs]
        for fut in futures:
            name, result, records = fut.result()
            outputs[name] = result
            builder_usage[name] = BlockBuilderUsage(name, records)
    return outputs


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

    # ---- steps 2+3: A1+A2 block builders (parallel dispatch) ---------------
    # All 8 builders consume independent claim slices and emit independent
    # blocks, so we fan them out concurrently. The Anthropic SDK client
    # is thread-safe; each builder writes only into its own ``usage_sink``;
    # the shared TimingRecorder uses CPython's atomic ``list.append``.
    a1_ctx = {"gene": gene_id.hgnc_symbol}
    a2_ctx = {"gene": gene_id.hgnc_symbol}
    specs: list[_BuilderSpec] = [
        _BuilderSpec("methods", "builders_a1", build_methods, a1_claims, a1_ctx),
        _BuilderSpec(
            "contradictions",
            "builders_a1",
            build_contradictions,
            a1_claims,
            a1_ctx,
        ),
        _BuilderSpec(
            "evidence_grade",
            "builders_a1",
            build_evidence_grade,
            a1_claims,
            a1_ctx,
        ),
        _BuilderSpec(
            "expression", "builders_a2", build_expression, a2_claims, a2_ctx
        ),
        _BuilderSpec(
            "cell_states", "builders_a2", build_cell_states, a2_claims, a2_ctx
        ),
        _BuilderSpec(
            "subcellular_localization",
            "builders_a2",
            build_subcellular_localization,
            a2_claims,
            a2_ctx,
        ),
        _BuilderSpec(
            "anatomical_accessibility",
            "builders_a2",
            build_anatomical_accessibility,
            a2_claims,
            a2_ctx,
        ),
        _BuilderSpec(
            "accessibility_modulation",
            "builders_a2",
            build_accessibility_modulation,
            a2_claims,
            a2_ctx,
        ),
    ]
    outputs = _run_builders_concurrently(
        specs, client=client, timing=timing, builder_usage=builder_usage
    )
    grade_block: EvidenceGradeBlock = outputs["evidence_grade"]

    surface_evidence = SurfaceEvidence(
        evidence_grade=grade_block.evidence_grade,
        grade_rationale=grade_block.grade_rationale,
        # Per-claim stance map from the evidence_grade builder (5b.8).
        # Drives the derived ``n_supporting_claims_high_weight`` +
        # ``n_contradicting_claims_high_weight`` Filter fields in
        # ``_derive_filters``.
        claim_stances=grade_block.claim_stances,
        methods=outputs["methods"],
        non_surface_expression=grade_block.non_surface_expression,
        contradicting_evidence=outputs["contradictions"],
    )

    biological_context = BiologicalContext(
        expression=outputs["expression"],
        cell_states=outputs["cell_states"],
        subcellular_localization=outputs["subcellular_localization"],
        anatomical_accessibility=outputs["anatomical_accessibility"],
        accessibility_modulation=outputs["accessibility_modulation"],
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
        # Compute the triage prior once for the synthesizer's task
        # message. ``plan_trim_select`` already computed its own copy
        # during ``_build_gene_context`` (cheap file read); we compute
        # again here so a synthesizer-only re-invocation doesn't depend
        # on plumbing it from the earlier phase. Implements PR #23
        # design doc §1110-1116's "common preamble — triage_record" for
        # the v2 pipeline's B agent.
        triage_record = _load_triage_record(gene_id.hgnc_symbol)
        triage_summary_json = (
            _summarize_triage_for_planner(triage_record)
            if triage_record is not None
            else None
        )
        b = run_synthesizer_with_drafts(
            gene_id.hgnc_symbol,
            a1_draft=a1_draft,
            a2_draft=a2_draft,
            client=client,
            triage_summary_json=triage_summary_json,
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

    # ---- step 5.5: scrub headline_risks for structured coherence ---------
    # Reviewers (CD81 audit) caught the synthesizer over-claiming
    # ``co_receptor`` / ``epitope_masked`` in headline_risks even when
    # the corresponding structured risk field doesn't back it. The
    # structured fields are the canonical signal; drop unbacked entries
    # from the list before they reach the record. ``b.draft`` is
    # non-None here (guarded above); take a narrowed local handle that
    # downstream code reads from instead of ``b.draft``.
    synth_draft = b.draft
    assert synth_draft is not None  # for ty — narrowed by the guard above
    synth_draft = synth_draft.model_copy(
        update={
            # Inject curator-assigned deterministic family tags (HGNC gene
            # groups + UniProt SIMILARITY family) from the resolved bundle.
            # These are ground truth, NOT model output (the synthesizer
            # leaves them at their defaults). v1 does this via
            # _attach_deterministic_families; v2 previously skipped it, so
            # every v2 record shipped with empty family fields. Runs on
            # every LLM pass, so deterministic family lands automatically.
            "executive_summary": _attach_deterministic_families(
                scrub_headline_risks(
                    synth_draft.executive_summary,
                    synth_draft.accessibility_risks,
                ),
                dual.bundle,
            )
        }
    )

    # ---- step 5.6: attach deterministic family tags ----------------------
    # hgnc_gene_groups + uniprot_family are curator-assigned ground truth, not
    # model output. v1 overwrites them from the resolved bundle; v2 must too,
    # or it ships records with empty family fields (which blanks the viewer's
    # Family chip). Free — reuses the already-resolved ``dual.bundle``.
    synth_draft = synth_draft.model_copy(
        update={
            "executive_summary": _attach_deterministic_families(
                synth_draft.executive_summary, dual.bundle
            )
        }
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

    # ---- step 6.25: cross-planner duplicate marking -----------------------
    # A1 (surface evidence) and A2 (biological context) run independently
    # and frequently both pull the same paper / same span (e.g. SRC's
    # PMC10356899 sEV paper landed as both a1_evi_10 + a2_evi_09).
    # We can't drop the duplicate — each planner's builders cite by
    # evidence_id, so removing the row would break references — but we
    # CAN mark the non-canonical entries with ``duplicate_of`` so the
    # viewer collapses them onto one card per unique source span.
    #
    # Dedup key: ``(spans[0].source.source_id, spans[0].quote_sha256)``
    # — same source, same exact extracted quote. Records without a
    # populated first span (entailment_verified=False, no anchored
    # span) skip dedup; they're rare and inherently uncomparable.
    #
    # Canonical pick: A1 ids ("a1_evi_*") sort before A2 ids
    # ("a2_evi_*") under lex compare, and within a planner the
    # earlier-numbered id wins. A1's claim_type/direction frame is
    # anchored on surface methodology, which is what most downstream
    # readers care about — also a desirable default.
    with timing.step("evidence_dedup", phase="post"):
        clusters: dict[tuple[str, str], list[int]] = {}
        for i, ev in enumerate(evidence):
            if not ev.spans:
                continue
            first = ev.spans[0]
            src = (first.source.source_id or "").strip()
            qsha = (first.quote_sha256 or "").strip()
            if not src or not qsha:
                continue
            clusters.setdefault((src, qsha), []).append(i)
        n_dups = 0
        n_clusters_with_dups = 0
        for indices in clusters.values():
            if len(indices) < 2:
                continue
            n_clusters_with_dups += 1
            canonical_i = min(
                indices, key=lambda j: evidence[j].evidence_id
            )
            canonical_id = evidence[canonical_i].evidence_id
            for j in indices:
                if j == canonical_i:
                    continue
                evidence[j].duplicate_of = canonical_id
                n_dups += 1
        if n_dups > 0:
            logger.info(
                "evidence_dedup: %d duplicate(s) marked across %d cluster(s) "
                "(viewer collapses; citations still resolve)",
                n_dups,
                n_clusters_with_dups,
            )

    # ---- step 6.5: deterministic species post-pass ------------------------
    # Two passes:
    # 1. Cell-line gazetteer over each row's free text (MC3T3-E1 →
    #    mouse, U251 MG → human, FRTL-5 → rat).
    # 2. Cite-aggregation over each row's cited_evidence_ids — pulls
    #    species from the cited Evidence's AssayContext.species and
    #    fills the row if all cited evidence agrees. Catches abstract
    #    tissue rows like ``tissue="bone"`` where the cell-line name
    #    doesn't appear in the row itself but the cited paper's
    #    assay_context.species was already populated by the agent.
    # Doesn't override anything the builders set explicitly.
    with timing.step("species_post_pass", phase="post"):
        from accessible_surfaceome.agents.surfaceome_v2.species_postpass import (
            apply_species_post_pass,
        )

        apply_species_post_pass(
            biological_context=biological_context,
            surface_evidence=surface_evidence,
            evidence=evidence,
        )

    # ---- step 7: deterministic features stub (reused from v1) -------------
    # Pull the real DeepTMHMM topology + Compara paralog + cross-species
    # ortholog ECD rows from public D1 (uploaded by PR #29's
    # ``scripts/run_topology_sweep.py``). Falls back to the labeled
    # stub if D1 is unreachable (no creds in the worktree) or the gene
    # isn't in this sweep's coverage. Mirrors the v1 orchestrator's
    # try/D1/fallback pattern landed in PR #29.
    with timing.step("deterministic_features", phase="post"):
        try:
            from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
                fetch_deterministic_features,
            )
            det_features = fetch_deterministic_features(gene_id.uniprot_acc)
        except Exception as exc:  # noqa: BLE001 — keep the run going if D1 is down
            logger.warning(
                "DeterministicFeatures D1 fetch failed for %s (%s); using stub",
                gene_id.uniprot_acc,
                exc,
            )
            det_features = _stub_deterministic_features(gene_id.uniprot_acc)

    # ---- step 7.5: deterministic secreted_form upgrade -------------------
    # The synthesizer ran before isoform topology was fetched (step 7), so it
    # could not see a TM-less splice isoform implying a soluble species. Apply
    # the topology-derived upgrade now — after the fetch, before _derive_filters
    # (step 8) reads accessibility_risks. Only ever upgrades; never downgrades a
    # literature-backed call. Module-level + importable for backfill parity.
    with timing.step("secreted_form_post_pass", phase="post"):
        from accessible_surfaceome.agents.surfaceome_v2.secreted_form_postpass import (
            apply_secreted_form_post_pass,
        )

        apply_secreted_form_post_pass(
            accessibility_risks=synth_draft.accessibility_risks,
            deterministic_features=det_features,
        )

    # ---- step 8: derive filters (reused from v1) --------------------------
    with timing.step(
        "filters_derivation",
        phase="post",
        n_items=len(evidence),
    ):
        filters = _derive_filters(
            executive_summary=synth_draft.executive_summary,
            surface_evidence=surface_evidence,
            biological_context=biological_context,
            accessibility_risks=synth_draft.accessibility_risks,
            filters_llm=synth_draft.filters_llm,
            deterministic_features=det_features,
            n_evidence=len(evidence),
        )

    # ---- step 9: assemble SurfaceomeRecord --------------------------------
    primary = sum(1 for e in evidence if e.evidence_tier == "primary")
    secondary = sum(1 for e in evidence if e.evidence_tier == "secondary")
    # Reuse the ``triage_record`` already loaded above for the synthesizer's
    # task message — derive both the signal enum and the verdict prose from
    # it so the record carries the triage's "why" without a second D1 fetch.
    triage_signal_value, triage_reasoning_value = (
        _triage_signal_and_reasoning_from_record(triage_record)
    )
    search_log = _build_search_log(dual)
    try:
        record = SurfaceomeRecord(
            schema_version=SCHEMA_VERSION_LITERAL,
            gene=gene_id,
            triage_signal=triage_signal_value,
            triage_reasoning=triage_reasoning_value,
            executive_summary=synth_draft.executive_summary,
            filters=filters,
            surface_evidence=surface_evidence,
            biological_context=biological_context,
            deterministic_features=det_features,
            accessibility_risks=synth_draft.accessibility_risks,
            evidence=evidence,
            search_log=search_log,
            evidence_count=len(evidence),
            primary_evidence_count=primary,
            secondary_evidence_count=secondary,
            confidence=synth_draft.confidence,
            confidence_reasoning=synth_draft.confidence_reasoning,
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


def _build_search_log(dual: DualPlanTrimSelectResult) -> list[SearchEntry]:
    """Translate plan-trim-select's per-search records into ``SearchEntry``
    rows for the SurfaceomeRecord.

    A1 and A2 are concatenated in execution order with ``agent_focus``
    threaded onto each entry's ``query`` so downstream consumers can
    distinguish what each agent looked at. ``sources_seen`` and
    ``contributed_evidence_ids`` are intentionally left empty for now —
    threading per-search source-id lists would require widening
    ``SearchLogEntry`` upstream; the per-tool / per-mode breakdown is
    enough to answer the primary audit question ("was the shedding
    literature checked for this gene?"). Tightening source attribution
    is a follow-up.
    """
    now = datetime.now(UTC)
    entries: list[SearchEntry] = []
    for focus, log in (("a1", dual.a1.search_log), ("a2", dual.a2.search_log)):
        for row in log:
            entries.append(_search_log_entry_to_search_entry(row, focus, now))
    return entries


def _search_log_entry_to_search_entry(
    row: SearchLogEntry, agent_focus: str, retrieved_at: datetime
) -> SearchEntry:
    params = dict(row.params)
    mode: str | None = params.pop("mode", None)
    if mode is None and row.tool == "evidence_retrieval":
        category = params.get("category")
        mode = str(category) if category is not None else None
    query: dict[str, Any] = {"agent_focus": agent_focus, "intent": row.intent}
    query.update(params)
    if row.error is not None:
        query["error"] = row.error
    return SearchEntry(
        tool=row.tool,
        mode=mode,
        query=query,
        n_results=row.n_papers,
        sources_seen=[],
        retrieved_at=retrieved_at,
        contributed_evidence_ids=[],
    )


def _count_blocks(
    se: SurfaceEvidence, bc: BiologicalContext
) -> dict[str, int]:
    return {
        "methods": len(se.methods),
        "non_surface_expression": len(se.non_surface_expression),
        "contradicting_evidence": len(se.contradicting_evidence),
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
        # NCBI PMC's path requires the ``PMC`` prefix on the accession.
        # Source ids come in two flavors (``PMC:PMC12345`` /
        # ``PMC:12345``); normalize before formatting. Linking to
        # ncbi.nlm.nih.gov rather than europepmc.org because the latter
        # has had availability issues.
        pmc = source_id.split(":", 1)[1]
        if not pmc.upper().startswith("PMC"):
            pmc = f"PMC{pmc}"
        return (f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc}/", "pmc")
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
        "total_elapsed_s": _wall_clock_for_timing(result.timing),
        "total_step_seconds": round(
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
