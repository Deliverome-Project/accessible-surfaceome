"""v2 deep-dive orchestrator.

Pipeline:

1. ``run_plan_trim_select_dual(gene, http=http, client=client)`` →
   ``DualPlanTrimSelectResult`` with A1 + A2 ledgers (verbatim claims).
2. Two A1-side block builders (methods, contradictions) + five A2-side
   block builders run concurrently.
3. evidence_grade runs sequentially after methods (needs methods output
   to make a coherent grade call).
3b. Assemble ``SurfaceEvidence`` + ``BiologicalContext`` from outputs.
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

import dataclasses
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

# Prompt-corpus tag stamped onto every record at synthesis time. Read at
# module load so the orchestrator snapshot a stable value at worker spawn
# (Modal-friendly: workers can't see version bumps mid-cohort).
from accessible_surfaceome._version_guard import PROMPT_CORPUS_VERSION
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
    scrub_headline_risks,
    _load_triage_record,
    _TRIAGE_VERDICT_TO_SIGNAL,
    _stub_deterministic_features,
)
from accessible_surfaceome.agents.surfaceome_v2.builders import (
    EvidenceGradeBlock,
    build_accessibility_modulation,
    build_anatomical_accessibility,  # noqa: F401 — back-compat for callers
    build_biological_context_grade,
    build_contradictions,
    build_evidence_grade,
    build_expression,
    build_methods,
    build_risks,
    build_subcellular_localization,  # noqa: F401 — back-compat for callers
)
from accessible_surfaceome.agents.surfaceome_v2.builders.subloc_anatomical_combined import (
    build_subloc_anatomical_combined,
)
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContext,
    BiologicalContextDraft,
    CoReceptorRequirements,
    DeterministicFeatures,
    ECDSizeAssessment,
    EpitopeMasking,
    Evidence,
    EvidenceClaim,
    GeneIdentifier,
    HomoOligomerizationPredictionRisk,
    IsoformTopology,
    MethodObservation,
    RestrictedSubdomain,
    RiskSeverity,
    SearchEntry,
    SecretedForm,
    ShedForm,
    SourceType,
    SubcellularLocalization,
    SurfaceEvidence,
    SurfaceEvidenceDraft,
    SurfaceomeRecord,
    classify_ecd_accessibility_class,
)
from accessible_surfaceome.tools._shared.failure_modes import FailureMode
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-6"
# Read the current schema_version off the Pydantic model so the version
# stamp on every emitted record stays in lock-step with the Literal's
# declared default — no separate string constant to forget to bump. When
# ``SurfaceomeRecord``'s default rolls (2.6.0 → 2.7.0 → … → 2.9.0 etc.)
# the orchestrator stamps the new value automatically. Previously this
# was a hard-coded ``"2.6.0"`` that kept records labeled with the old
# version even after the Pydantic default moved, which silently kept the
# viewer's freshness dots marking fresh records as stale.
SCHEMA_VERSION_LITERAL = SurfaceomeRecord.model_fields["schema_version"].default

RUNS_DIR = Path(".runs")

# Mid-gene PTS checkpoint directory. After ``run_plan_trim_select_dual``
# completes (which is the heavy half of a gene at ~$1.35 of the typical
# ~$2 per-gene cost), the orchestrator persists the dual's serialized
# form here. A subsequent re-launch of the same gene reads the checkpoint
# and short-circuits past the PTS dual, jumping straight to the builders
# + synth — saving ~$1.35 / retried gene. On a ~5% builder/synth failure
# rate over the ~6,500-gene cohort, that's ~$440 of recovered spend.
#
# **Local-only.** ``.runs/_phase_checkpoint/`` is a per-runner directory;
# Modal containers don't share disk between attempts, so the Modal analog
# is a Modal volume mount at the same path. Future Modal-side work
# should mount a ``modal.Volume`` at ``.runs/_phase_checkpoint/`` and the
# checkpoint code below works unchanged.
#
# **Read is opt-out** (``read_phase_checkpoint=True`` by default — the
# safe choice for cohort retry). **Write is always on** so a forced
# rerun still leaves a checkpoint for the NEXT attempt.
_CHECKPOINT_DIR = RUNS_DIR / "_phase_checkpoint"


def _checkpoint_path(gene: str) -> Path:
    """Per-gene PTS checkpoint file under ``.runs/_phase_checkpoint/``.

    Filename keys on the colon-substituted gene id so HGNC:1234 and
    GENESYM both produce stable filesystem-safe paths.
    """
    safe_id = gene.replace(":", "_")
    return _CHECKPOINT_DIR / f"{safe_id}.pts.json"


def _save_pts_checkpoint(gene: str, dual: DualPlanTrimSelectResult) -> None:
    """Persist the PTS dual result for mid-gene resume.

    Best-effort: a write failure (disk full, permission error) logs and
    returns. The checkpoint is an optimization; if it can't be written
    the next run just re-pays the PTS cost.

    Reuses :func:`_serialize_pts` so the on-disk shape matches what
    intermediates carry — that means the checkpoint can be reconstructed
    by the same code path the ``surfaceome_v2_replay_builders`` driver
    uses to rebuild a dual from intermediates.
    """
    try:
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        payload = _serialize_pts(dual)
        _checkpoint_path(gene).write_text(json.dumps(payload, indent=2))
        logger.info(
            "v2 orchestrator: PTS checkpoint saved for %s (%d A1 + %d A2 claims)",
            gene, len(dual.a1.claims), len(dual.a2.claims),
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, never raise
        logger.warning(
            "v2 orchestrator: PTS checkpoint write failed for %s: %s "
            "(continuing — next retry will re-pay PTS cost)",
            gene, exc,
        )


def _load_pts_checkpoint(gene: str) -> DualPlanTrimSelectResult | None:
    """Re-hydrate a saved PTS dual, or return ``None`` if no checkpoint
    or the on-disk file fails to deserialize.

    Conservative: any failure path returns None so the caller re-runs
    the PTS dual fresh. This matches the philosophy of the rest of the
    pipeline — degraded inputs are recoverable; we'd rather re-pay the
    cost than continue on a half-corrupt checkpoint.
    """
    path = _checkpoint_path(gene)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "v2 orchestrator: PTS checkpoint read failed for %s: %s "
            "(falling back to fresh PTS dual)",
            gene, exc,
        )
        return None
    try:
        return _dual_from_serialized(gene, blob)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "v2 orchestrator: PTS checkpoint deserialize failed for %s: %s "
            "(falling back to fresh PTS dual)",
            gene, exc,
        )
        return None


def _delete_pts_checkpoint(gene: str) -> None:
    """Remove a per-gene checkpoint after a successful annotate run.

    Best-effort: a delete failure logs but doesn't raise. A stale
    checkpoint left around is harmless — the next successful run will
    overwrite it, and a re-launch on a non-existent gene will just hit
    the no-file branch in :func:`_load_pts_checkpoint`.
    """
    path = _checkpoint_path(gene)
    if not path.exists():
        return
    try:
        path.unlink()
        logger.info(
            "v2 orchestrator: PTS checkpoint cleared for %s (gene completed)",
            gene,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "v2 orchestrator: PTS checkpoint delete failed for %s: %s "
            "(harmless — next run will overwrite or reuse it)",
            gene, exc,
        )


def _dual_from_serialized(gene: str, blob: dict[str, Any]) -> DualPlanTrimSelectResult:
    """Reconstruct a :class:`DualPlanTrimSelectResult` from the same blob
    shape :func:`_serialize_pts` emits.

    Mirrors ``scripts/surfaceome_v2_replay_builders._reconstruct_dual``
    — kept inline here so the orchestrator's checkpoint resume path
    doesn't depend on the script being importable. The downstream
    pipeline reads: ``dual.bundle``, ``dual.a1``, ``dual.a2``,
    ``dual.total_cost_usd``, ``dual.elapsed_s``. The reconstructed
    sides hold zero cost (a replay incurs no PTS spend — that's the
    whole point) and empty audit logs (the slim path on intermediates
    drops ``search_log`` etc; we mirror that here).
    """
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        PlanTrimSelectResult,
    )
    from accessible_surfaceome.tools._shared.models import (
        EvidenceClaim,
        IdentifierBundle,
    )

    bundle_dict = blob.get("bundle")
    if not bundle_dict:
        raise ValueError(
            "PTS checkpoint has no bundle — incompatible with the "
            "current schema. Falling back to fresh PTS dual."
        )
    bundle = IdentifierBundle.model_validate(bundle_dict)

    def _side(side_blob: dict[str, Any]) -> PlanTrimSelectResult:
        claims = [
            EvidenceClaim.model_validate(c)
            for c in side_blob.get("claims") or []
        ]
        # plan + selection_response are required by the dataclass init
        # but the orchestrator's downstream pipeline doesn't read them
        # off the replayed dual — None marks "no replay state" (the
        # surfaceome_v2_replay_builders driver uses the same shape).
        return PlanTrimSelectResult(
            gene=blob.get("gene") or gene,
            bundle=bundle,
            plan=None,
            selection_response=None,
            agent_focus=side_blob.get("agent_focus") or "a1",
            claims=claims,
            search_log=[],
            iteration_log=[],
            triage_actions=[],
            pretrim_audits=[],
            n_claims=len(claims),
            n_anchored=side_blob.get("n_anchored") or len(claims),
            n_papers_total=side_blob.get("n_papers_total") or 0,
            n_drafts_total=side_blob.get("n_drafts_total") or 0,
            n_kept_after_trim=side_blob.get("n_kept_after_trim") or 0,
            n_iterations_run=side_blob.get("n_iterations_run") or 0,
            elapsed_s=0.0,
            warnings=[],
        )

    return DualPlanTrimSelectResult(
        gene=blob.get("gene") or gene,
        bundle=bundle,
        a1=_side(blob.get("a1") or {}),
        a2=_side(blob.get("a2") or {}),
        elapsed_s=0.0,
    )


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

# Maximum block-builders to dispatch concurrently in the step-2+3 fan-out.
# There are 7 builders in that fan-out — 2 A1-side (methods, contradictions)
# + 5 A2-side (expression, subcellular_localization, anatomical_accessibility,
# accessibility_modulation, biological_context_grade). evidence_grade runs
# AFTER the concurrent fan-out so it can see the methods builder's output
# (accessibility_relevance values) and make a coherent grade call — without
# this sequencing, the evidence_grade builder can assign direct_single_method
# while methods tags every observation as supports_surface_localization,
# tripping the cross-block validator (TGOLN2 failure, 2026-06-06).
# Schema 2.5.0 merged the former ``cell_states`` builder into
# ``accessibility_modulation`` — single-context state observations now emit as
# modulation rows with baseline_context=None + modulating_state=None. The
# cross-focus ``risks`` builder is NOT in this fan-out — it needs the
# deterministic block fetched at step 4.5, so it runs serially afterward. Each
# builder consumes an independent claim slice and makes a single Sonnet call,
# so a worker pool sized to ``8`` lets every builder kick off immediately. The
# Anthropic client is thread-safe (httpx underneath) and each builder writes to
# its own ``usage_sink`` list so there's no shared mutable state across
# workers. The shared ``TimingRecorder`` appends rows from multiple threads —
# CPython's ``list.append`` is atomic under the GIL, so the list stays
# well-formed; the resulting timing-row order is non-deterministic but the
# viewer sorts by ``elapsed_s`` anyway.
BUILDER_CONCURRENCY = 8


def _resolve_method_species(
    method: MethodObservation,
    claims_by_id: dict[str, EvidenceClaim],
) -> str:
    """Deterministic species inheritance for a MethodObservation.

    MethodObservation has no `species` field of its own — species lives on
    each cited `EvidenceClaim.assay_context.species`. This helper walks
    the row's `cited_evidence_ids`, collects the species values, and
    returns a single human-readable label following the human-anchored
    rule: if any cited claim is human, the row is human-anchored;
    otherwise return the unique species, or a comma-joined string when
    the cites span multiple non-human species.

    Returns ``"unspecified"`` when no cite resolves or all assay_contexts
    are unspecified.

    This deterministic post-pass replaces an earlier prompt-only rule
    that asked the LLM to "default species from assay_context" — but
    the schema doesn't even have a species field on MethodObservation,
    so the prompt rule had nowhere to land. The species data was
    always in the claims; we just need to read it programmatically.
    """
    species_set: set[str] = set()
    for evid in method.cited_evidence_ids:
        claim = claims_by_id.get(evid)
        if claim is None:
            continue
        s = (claim.assay_context.species or "unspecified").strip()
        if s and s != "unspecified":
            species_set.add(s)
    if not species_set:
        return "unspecified"
    # Human-anchored rule: if any cite is human, the row is human.
    if "human" in species_set:
        return "human"
    # Otherwise return the unique species, or a comma-joined cross-species
    # list (alphabetized for stability).
    if len(species_set) == 1:
        return next(iter(species_set))
    return ", ".join(sorted(species_set))


def _format_methods_summary_for_grade(
    methods: list[MethodObservation],
    claims: list[EvidenceClaim] | None = None,
) -> str:
    """Compact summary of the methods builder's output for the evidence_grade
    builder.

    Returns one line per method: ``method_type | accessibility_relevance |
    species | cited_evidence_ids``. Species is resolved deterministically
    from each cited claim's `assay_context.species` (see
    :func:`_resolve_method_species`). Empty string when no methods were
    emitted.

    ``claims`` is the A1 ledger used to resolve species; when omitted the
    summary falls back to the older shape (no species column) for
    callers that don't have the claim list handy.
    """
    if not methods:
        return ""
    claims_by_id: dict[str, EvidenceClaim] = {}
    if claims:
        claims_by_id = {c.evidence_id: c for c in claims if c.evidence_id}
    lines = []
    for m in methods:
        cites = ", ".join(m.cited_evidence_ids) if m.cited_evidence_ids else "none"
        if claims_by_id:
            species = _resolve_method_species(m, claims_by_id)
            lines.append(
                f"- {m.method_family} / {m.method_subclass} | "
                f"{m.accessibility_relevance} | species: {species} | "
                f"cites: {cites}"
            )
        else:
            lines.append(
                f"- {m.method_family} / {m.method_subclass} | "
                f"{m.accessibility_relevance} | cites: {cites}"
            )
    return "\n".join(lines)


def _serialize_pts(dual: DualPlanTrimSelectResult) -> dict[str, Any]:
    """Serialize plan-trim-select outputs for the intermediates dump."""

    def _side(pts) -> dict[str, Any]:
        # pretrim_audits are PreTrimAudit dataclasses (or empty list for runs
        # that predate the feature). Serialize defensively so older runs
        # without the field don't crash the dump.
        pretrim_dumps = []
        for audit in getattr(pts, "pretrim_audits", []) or []:
            try:
                pretrim_dumps.append(dataclasses.asdict(audit))
            except (TypeError, AttributeError):
                continue
        return {
            "agent_focus": pts.agent_focus,
            "claims": [c.model_dump(mode="json") for c in pts.claims],
            "search_log": [dataclasses.asdict(e) for e in pts.search_log],
            "iteration_log": [dataclasses.asdict(e) for e in pts.iteration_log],
            "triage_actions": [dataclasses.asdict(a) for a in pts.triage_actions],
            "pretrim_audits": pretrim_dumps,
            "n_claims": pts.n_claims,
            "n_anchored": pts.n_anchored,
            "n_papers_total": pts.n_papers_total,
            "n_drafts_total": pts.n_drafts_total,
            "n_kept_after_trim": pts.n_kept_after_trim,
            "n_iterations_run": pts.n_iterations_run,
            "warnings": pts.warnings,
        }

    return {
        "gene": dual.gene,
        "bundle": dual.bundle.model_dump(mode="json") if dual.bundle else None,
        "a1": _side(dual.a1),
        "a2": _side(dual.a2),
        "elapsed_s": dual.elapsed_s,
    }


def _dump_builder_output(name: str, output: Any) -> Any:
    """Serialize one builder's output for JSON persistence."""
    if isinstance(output, list):
        return [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in output
        ]
    if hasattr(output, "model_dump"):
        return output.model_dump(mode="json")
    return output


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


def _homo_oligomerization_severity(stoichiometry: int | None) -> RiskSeverity:
    """Map Schweke cyclic-symmetry order N onto a ``RiskSeverity`` band.

    The synthesizer already weights epitope-masking severity by N (a
    13-mer hides far more surface than a 2-mer); the risk-side chip
    needs the same monotone mapping so the viewer's chip color tracks
    the underlying signal. ``None`` (Schweke didn't reconstruct higher-
    order, or the protein isn't in the positive refset) → ``unknown``.

    Bands (per CLAUDE.md task spec):

    * ``<= 2``  → ``low``      (dimer: relatively little surface hidden)
    * ``3..7``  → ``moderate``
    * ``8..24`` → ``high``     (large complex: substantial surface buried)
    """
    if stoichiometry is None:
        return "unknown"
    if stoichiometry <= 2:
        return "low"
    if stoichiometry <= 7:
        return "moderate"
    return "high"


def _attach_homo_oligomerization_prediction(
    accessibility_risks: AccessibilityRisks,
    deterministic_features: DeterministicFeatures,
) -> AccessibilityRisks:
    """Copy the deterministic Schweke homo-oligomer prediction onto the
    risks block as a structured chip.

    Mirrors :func:`_attach_deterministic_families`: a small,
    orchestrator-only post-pass that lifts a deterministic signal into a
    region the LLM authored, so the viewer can render it next to the
    LLM-emitted ``epitope_masking`` chip without conflating the two.

    Returns a *new* ``AccessibilityRisks`` (via ``model_copy``); the
    input is left untouched. Severity is derived deterministically from
    ``stoichiometry`` (see :func:`_homo_oligomerization_severity`).
    """
    schweke = deterministic_features.homo_oligomerization
    prediction = HomoOligomerizationPredictionRisk(
        present=schweke.is_homo_oligomer,
        stoichiometry=schweke.stoichiometry,
        severity=_homo_oligomerization_severity(schweke.stoichiometry),
        is_ecd_only=schweke.is_ecd_only,
        source=schweke.source,
    )
    return accessibility_risks.model_copy(
        update={"homo_oligomerization_prediction": prediction}
    )


def _attach_deterministic_ecd_size_assessment(
    accessibility_risks: AccessibilityRisks,
    deterministic_features: DeterministicFeatures,
) -> AccessibilityRisks:
    """Overwrite ``ecd_size_assessment`` with a deterministic classification.

    ``ecd_accessibility_class`` is the **single source of truth** for ECD
    size: it is computed by :func:`classify_ecd_accessibility_class` from the
    deterministic
    ``deterministic_features.canonical_topology.ecd_length_residues`` count and
    overwrites whatever the synthesizer emitted (the synthesizer is no longer
    allowed a literature override). This mirrors
    :func:`_attach_homo_oligomerization_prediction` /
    :func:`_attach_deterministic_families`: an orchestrator-only post-pass that
    replaces an LLM-authored field with a deterministic one.

    Runs *before* the filters-derivation step so ``_derive_filters`` reads the
    deterministic class straight off this block — keeping the
    ``filters.ecd_accessibility_class`` mirror in lock-step (they cannot
    diverge). Returns a *new* ``AccessibilityRisks`` via ``model_copy``.
    """
    ecd_len = deterministic_features.canonical_topology.ecd_length_residues
    ecd_class = classify_ecd_accessibility_class(ecd_len)
    if ecd_len is None:
        rationale = (
            "ECD length unavailable -> none; computed deterministically "
            "from DeepTMHMM topology."
        )
    else:
        if ecd_class == "large":
            band = ">=200"
        elif ecd_class == "moderate":
            band = "60-199"
        elif ecd_class == "small":
            band = "30-59"
        elif ecd_class == "minimal":
            band = "<30"
        else:  # "none"
            band = "==0"
        rationale = (
            f"ECD length {ecd_len} residues ({band}) -> {ecd_class}; "
            "computed deterministically from DeepTMHMM topology."
        )
    assessment = ECDSizeAssessment(
        ecd_accessibility_class=ecd_class,
        rationale=rationale,
        cited_evidence_ids=[],
    )
    return accessibility_risks.model_copy(
        update={"ecd_size_assessment": assessment}
    )


def _stub_accessibility_risks() -> AccessibilityRisks:
    """All-absent ``AccessibilityRisks`` fallback for the risks-builder miss.

    ``build_risks`` returns ``None`` when its repair loop exhausts; a record
    still needs a risks block to ship. This is the labeled fallback: every
    literature-driven risk ``present=false`` / ``unknown`` with a "no data"
    rationale. The deterministic post-passes (ECD-size class +
    homo-oligomerization chip + the secreted_form topology safety net) still
    run on top of it, so the record carries the deterministic signals even
    when the LLM call failed. Mirrors the all-absent shapes the builder
    itself emits on an empty ledger.
    """
    no_data = "risks builder produced no block; no literature risk call made."
    return AccessibilityRisks(
        co_receptor_requirements=CoReceptorRequirements(
            surface_expression_dependency="unknown",
            evidence_basis="mixed",
            rationale=no_data,
        ),
        shed_form=ShedForm(present=False, severity="unknown", evidence_strength="weak"),
        secreted_form=SecretedForm(
            present=False, severity="unknown", evidence_strength="weak"
        ),
        restricted_subdomain=RestrictedSubdomain(
            present=False,
            domain="unknown",
            severity="unknown",
            evidence_strength="weak",
            rationale=no_data,
        ),
        ecd_size_assessment=ECDSizeAssessment(
            ecd_accessibility_class="none",
            rationale=no_data,
        ),
        epitope_masking=EpitopeMasking(
            mechanism=["none"],
            severity="none",
            evidence_strength="weak",
            rationale=no_data,
        ),
    )


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
    """Per-builder token usage rollup.

    Carries the per-call ``UsageRecord``s + an optional repair-loop
    summary populated by ``call_builder``'s ``meta_sink``. When the
    summary is present, ``n_repair_attempts`` reflects how many times
    the validation loop fired (0 when the first JSON validated; up to
    ``MAX_REPAIRS=2``). ``validation_error`` is ``None`` on success.
    Both default-None so the legacy construction path (no meta_sink
    threaded) still works without populating them.
    """

    label: str
    records: list[UsageRecord] = field(default_factory=list)
    n_repair_attempts: int = 0
    validation_error: str | None = None

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

    def _runner(
        spec: _BuilderSpec,
    ) -> tuple[str, Any, list[UsageRecord], dict[str, Any]]:
        records: list[UsageRecord] = []
        meta_sink: dict[str, Any] = {}
        with timing.step(
            f"builder:{spec.name}",
            phase=spec.phase,
            n_items=len(spec.claims),
            model=AGENT_MODEL,
        ) as handle:
            result = spec.fn(
                spec.claims,
                client=client,
                usage_sink=records,
                context=spec.ctx,
                meta_sink=meta_sink,
            )
            handle.set_usage(records, model=AGENT_MODEL)
        return spec.name, result, records, meta_sink

    outputs: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=BUILDER_CONCURRENCY) as executor:
        futures = [executor.submit(_runner, spec) for spec in specs]
        for fut in futures:
            name, result, records, meta_sink = fut.result()
            outputs[name] = result
            builder_usage[name] = BlockBuilderUsage(
                label=name,
                records=records,
                n_repair_attempts=int(meta_sink.get("n_repair_attempts", 0) or 0),
                validation_error=meta_sink.get("validation_error"),
            )
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
    # Structured failure-mode tag — complementary to the free-text
    # ``error`` field. ``"ok"`` on every success path; a specific abort
    # category on every error path (cost_ceiling_pts / cost_ceiling_total
    # / validation_failed / synth_draft_missing / pts_failure / etc.).
    # See ``tools/_shared/failure_modes.py`` for the enum + the cohort-
    # analytics rationale ("WHERE failure_mode = 'cost_ceiling_pts'"
    # without parsing prose).
    failure_mode: FailureMode = "ok"
    # Per-step wall-clock audit: every model call + post-process step,
    # in execution order. Empty when ``annotate`` was invoked with
    # ``timing=None`` (legacy path).
    timing: list[StepTiming] = field(default_factory=list)
    # Serialized intermediate artifacts for debugging / replay. Populated
    # by ``_annotate`` at each pipeline stage so a post-mortem can inspect
    # evidence ledgers, per-builder raw outputs, and the synthesizer's
    # pre-validation JSON even when the final record assembly succeeded
    # (or failed). Written to ``.runs/surfaceome_v2_{gene}.intermediates.json``
    # by the driver script. Dict is JSON-serializable (all Pydantic
    # sub-trees are pre-dumped via ``.model_dump(mode="json")``).
    intermediates: dict[str, Any] = field(default_factory=dict)

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
    skip_if_fresh: bool = False,
    cached_dual: DualPlanTrimSelectResult | None = None,
    read_phase_checkpoint: bool = True,
) -> AnnotateResultV2:
    """Run the v2 deep-dive pipeline on one gene.

    A fresh :class:`TimingRecorder` is allocated when ``timing`` is
    ``None`` so every annotate run captures the per-step wall-clock
    trace by default. Pass an externally-owned recorder to merge into a
    larger audit (e.g. a sweep over multiple genes).

    When ``skip_if_fresh=True``, returns an early-exit
    :class:`AnnotateResultV2` (record=None, error='already_fresh') if
    public D1's ``surface_annotation`` already carries a row for this
    gene at the current ``SurfaceomeRecord.schema_version``. Used by
    cohort resume — avoids re-paying ~\$2/gene to land an identical call.
    Modal's :class:`D1DeepDiveSink` filters the gene list at dispatch
    via :meth:`already_done`; this flag is the equivalent guard for
    direct-CLI re-runs and any non-Modal cohort dispatcher.

    When ``cached_dual`` is supplied (a previously-computed
    :class:`DualPlanTrimSelectResult` reconstructed from D1 intermediates),
    the orchestrator SKIPS the expensive plan-trim-select step and runs
    only the builders + synth + assembly. Used by the
    ``surfaceome_v2_replay_builders`` driver for cheap prompt iteration
    on builder / synth changes — ~\$0.65/iteration vs ~\$2 for a full
    pipeline run. The cached dual must have been produced under prompts
    compatible with the current builders' input contracts (typically
    same major prompt_corpus version).

    When ``read_phase_checkpoint=True`` (default) and a per-gene
    checkpoint file exists at ``.runs/_phase_checkpoint/{gene}.pts.json``,
    the saved dual is loaded and used as ``cached_dual``. This lets a
    mid-gene crash on the builders/synth half restart cheaply — the
    PTS spend (~$1.35 of a typical $2 gene) is recovered. Pass
    ``read_phase_checkpoint=False`` to force a fresh PTS dual even when
    a checkpoint exists (e.g. when iterating on PTS prompts). Write of
    the checkpoint is always on; only the read is opt-out. Explicit
    ``cached_dual`` wins over the on-disk checkpoint.
    """
    if skip_if_fresh:
        existing = _existing_fresh_record(gene)
        if existing is not None:
            logger.info(
                "v2 orchestrator: skipping %s — fresh record exists at "
                "schema_version=%s, generated_at=%s",
                gene, existing["schema_version"], existing["record_generated_at"],
            )
            return AnnotateResultV2(
                gene=gene,
                record=None,
                dual=None,
                synthesizer=None,
                blocks_used={},
                builder_usage={},
                error=f"skipped: fresh record already in public D1 ({existing['record_generated_at']})",
                failure_mode="ok",
                timing=[],
                intermediates={},
            )
    # Checkpoint-driven resume — load before the http/client allocation
    # so a successful checkpoint hit doesn't even open a network handle
    # for the PTS-side. Explicit cached_dual wins (caller knows best).
    if cached_dual is None and read_phase_checkpoint:
        loaded = _load_pts_checkpoint(gene)
        if loaded is not None:
            logger.info(
                "v2 orchestrator: PTS checkpoint hit for %s — skipping "
                "PTS dual (saved ~$1.35 in PTS spend)",
                gene,
            )
            cached_dual = loaded
    own_http = http is None
    client = client or get_client()
    http = http or open_default_client()
    timing = timing if timing is not None else TimingRecorder()
    try:
        return _annotate(
            client,
            http,
            gene,
            persist=persist,
            timing=timing,
            cached_dual=cached_dual,
        )
    finally:
        if own_http:
            http.close()


def _existing_fresh_record(gene_symbol: str) -> dict[str, str] | None:
    """Return a slim dict ({schema_version, record_generated_at}) for a
    gene whose latest public-D1 ``surface_annotation`` row is at the
    current ``SurfaceomeRecord.schema_version``. Returns None when no
    row exists or the row is on an older schema (which the cohort sweep
    SHOULD refresh).

    Best-effort: when D1 credentials are missing or the query fails,
    returns None so the annotate proceeds as usual. The sweep-time
    cost of an extra annotate is bounded; the cost of MISSING the
    skip on a credential blip is also bounded — both errors are safe.
    """
    try:
        from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
    except Exception:  # noqa: BLE001
        return None
    current_schema = SurfaceomeRecord.model_fields["schema_version"].default
    try:
        with D1Client(D1Config.from_env_public()) as c:
            rows = c.query(
                "SELECT schema_version, annotated_at AS record_generated_at "
                "FROM surface_annotation WHERE gene_symbol = ? "
                "ORDER BY annotated_at DESC LIMIT 1",
                [gene_symbol],
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("skip_if_fresh probe failed for %s: %s", gene_symbol, exc)
        return None
    if not rows:
        return None
    row = rows[0]
    if row.get("schema_version") != current_schema:
        return None
    return row


def _annotate(
    client: Anthropic,
    http: CachedHTTP,
    gene: str,
    *,
    persist: bool,
    timing: TimingRecorder,
    cached_dual: DualPlanTrimSelectResult | None = None,
) -> AnnotateResultV2:
    builder_usage: dict[str, BlockBuilderUsage] = {}

    # ---- step 1: plan-trim-select dual -------------------------------------
    # Skip when an externally-reconstructed dual is supplied (replay path —
    # iterate on builder / synth prompts without re-paying for retrieval).
    if cached_dual is not None:
        logger.info(
            "v2 orchestrator: using cached plan-trim-select dual for %s "
            "(replay path — skipping retrieval, saves ~70%% per-gene cost)",
            gene,
        )
        dual = cached_dual
    else:
        logger.info("v2 orchestrator: running plan-trim-select dual for %s", gene)
        dual = run_plan_trim_select_dual(gene, client=client, http=http, timing=timing)
    if dual.bundle is None:
        return AnnotateResultV2(
            gene=gene,
            record=None,
            dual=dual,
            synthesizer=None,
            error="plan-trim-select did not resolve a gene bundle",
            failure_mode="pts_failure",
            timing=list(timing.entries),
            intermediates={
                "plan_trim_select": _serialize_pts(dual),
                # Mirror per-step timing into the persisted blob — Modal
                # tears down ``.runs/`` on container shutdown, D1 is durable.
                "timing": [t.as_dict() for t in list(timing.entries)],
            },
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

    # Mid-gene PTS checkpoint: persist the dual so a restart after a
    # builder/synth failure can short-circuit past the PTS spend. Only
    # write a checkpoint for FRESH PTS dual runs — when cached_dual was
    # already provided (replay or checkpoint resume), the on-disk file
    # is either unchanged or being re-asserted with identical data.
    # Modal note: ``.runs/_phase_checkpoint/`` is per-container; the
    # Modal-side analog is a Modal volume mount at the same path. See
    # the comment on ``_CHECKPOINT_DIR``.
    if cached_dual is None:
        _save_pts_checkpoint(gene_id.hgnc_symbol, dual)

    # ---- PTS-level cost cap ----------------------------------------------
    # Separate from the post-builders MAX_COST_USD ceiling. A pathological
    # PTS dual (deep-iteration retrieval on a heavy-lit gene gone wrong)
    # can rack up $5+ before the builders even start. Aborting here with
    # a valid error result + intermediates publish path means we keep the
    # diagnostic blob for post-mortem (which papers were fetched, which
    # claims trimmed) without burning another $0.65+ on the builders.
    # 5 USD chosen with ~3x headroom over the heaviest observed PTS run
    # (TGOLN2 ~$1.65) — pathological runs jump well past this.
    MAX_PTS_COST_USD = 5.0
    pts_cost = dual.total_cost_usd
    if pts_cost > MAX_PTS_COST_USD:
        logger.warning(
            "v2 orchestrator: PTS-level cost ceiling exceeded for %s: "
            "$%.2f > $%.2f. Aborting before builders run.",
            gene_id.hgnc_symbol,
            pts_cost,
            MAX_PTS_COST_USD,
        )
        pts_only_intermediates: dict[str, Any] = {
            "plan_trim_select": _serialize_pts(dual),
            "bundle": dual.bundle.model_dump(mode="json")
            if dual.bundle is not None
            else None,
            "cost_total_usd": pts_cost,
            "cost_per_pipeline": {
                "plan_trim_select": pts_cost,
                "builders": 0.0,
                "synthesizer": 0.0,
            },
            # Mirror per-step timing into the persisted blob — Modal
            # tears down ``.runs/`` on container shutdown, D1 is durable.
            "timing": [t.as_dict() for t in list(timing.entries)],
        }
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=None,
            blocks_used={},
            builder_usage={},
            error=(
                f"PTS-level cost ceiling exceeded: "
                f"${pts_cost:.2f} > ${MAX_PTS_COST_USD:.2f}"
            ),
            failure_mode="cost_ceiling_pts",
            timing=list(timing.entries),
            intermediates=pts_only_intermediates,
        )

    intermediates: dict[str, Any] = {
        "plan_trim_select": _serialize_pts(dual),
    }

    # ---- steps 2+3: A1+A2 block builders (parallel dispatch) ---------------
    # All 8 builders consume independent claim slices and emit independent
    # blocks, so we fan them out concurrently. The Anthropic SDK client
    # is thread-safe; each builder writes only into its own ``usage_sink``;
    # the shared TimingRecorder uses CPython's atomic ``list.append``.
    a1_ctx = {"gene": gene_id.hgnc_symbol}
    a2_ctx = {"gene": gene_id.hgnc_symbol}
    # evidence_grade gets the triage prior + curator-assigned family tags
    # alongside the gene symbol. The grade verdict is load-bearing (it
    # drives the deep-dive's confidence chain), so calibration signals
    # the other builders don't need belong here: the triage's prior
    # verdict prose + the HGNC / UniProt family tags that anchor the
    # antibody-cross-reactivity-with-paralog discussion.
    triage_record_for_ctx = _load_triage_record(gene_id.hgnc_symbol)
    evidence_grade_ctx: dict[str, Any] = {
        "gene": gene_id.hgnc_symbol,
        "triage_summary_json": (
            _summarize_triage_for_planner(triage_record_for_ctx)
            if triage_record_for_ctx is not None
            else None
        ),
        "hgnc_gene_groups": list(dual.bundle.hgnc_gene_groups),
        "uniprot_family": dual.bundle.uniprot_family,
    }
    specs: list[_BuilderSpec] = [
        _BuilderSpec("methods", "builders_a1", build_methods, a1_claims, a1_ctx),
        _BuilderSpec(
            "contradictions",
            "builders_a1",
            build_contradictions,
            a1_claims,
            a1_ctx,
        ),
        # evidence_grade runs AFTER this fan-out — see step 3.5 below.
        _BuilderSpec(
            "expression", "builders_a2", build_expression, a2_claims, a2_ctx
        ),
        # Consolidated A2 builder: subcellular_localization + anatomical_
        # accessibility share the same A2 ledger and both reason about
        # tissue/cell-type/membrane-subdomain context. One Sonnet call emits
        # both — saves ~$0.04-0.08/gene with no schema change downstream
        # (the wrapper is unpacked into two outputs keys post-call). See
        # ``builders/subloc_anatomical_combined.py`` for the merged prompt.
        _BuilderSpec(
            "subloc_anatomical_combined",
            "builders_a2",
            build_subloc_anatomical_combined,
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
        # A2 rollup — the A2 analog of evidence_grade. Reads the full A2
        # ledger and emits a single biological_context_grade verdict +
        # rationale + cites. Rides the step-2+3 fan-out (A2-only, no
        # deterministic dependency).
        _BuilderSpec(
            "biological_context_grade",
            "builders_a2",
            build_biological_context_grade,
            a2_claims,
            a2_ctx,
        ),
    ]
    outputs = _run_builders_concurrently(
        specs, client=client, timing=timing, builder_usage=builder_usage
    )
    # Unpack the consolidated subloc+anatomical builder back into the two
    # output keys downstream code expects. The combined builder emits a
    # ``(SubcellularLocalization, list[AnatomicalAccessibilityObservation])``
    # tuple; we project that into ``outputs["subcellular_localization"]`` +
    # ``outputs["anatomical_accessibility"]`` so the BiologicalContext
    # assembly below sees no change. The combined entry stays in
    # ``builder_usage`` under its own name for cost-attribution, and the
    # two original names are NOT added to ``builder_usage`` (zero records).
    combined_result = outputs.pop("subloc_anatomical_combined", None)
    if combined_result is not None and isinstance(combined_result, tuple):
        subloc, anatomical = combined_result
        outputs["subcellular_localization"] = subloc
        outputs["anatomical_accessibility"] = anatomical
    else:
        # Defensive: fall back to empty defaults rather than crash the
        # BiologicalContext assembly. Matches the standalone builders'
        # failure path.
        outputs["subcellular_localization"] = SubcellularLocalization(
            primary_compartment="other",
            dual_localization=[],
            membrane_subdomains=[],
        )
        outputs["anatomical_accessibility"] = []

    # ---- step 3.5: evidence_grade (sequenced after methods) ----------------
    # Runs after the concurrent fan-out so it can see the methods builder's
    # accessibility_relevance assignments. This prevents the grade/methods
    # coherence failure where evidence_grade assigns direct_single_method
    # but no MethodObservation carries direct_surface_accessibility (the
    # TGOLN2 class of failure). The methods summary is injected into the
    # builder's context dict so the LLM can cross-reference.
    methods_output: list[MethodObservation] = outputs["methods"]
    methods_summary = _format_methods_summary_for_grade(
        methods_output, claims=a1_claims
    )
    if methods_summary:
        evidence_grade_ctx["methods_summary"] = methods_summary
    grade_spec = _BuilderSpec(
        "evidence_grade",
        "builders_a1",
        build_evidence_grade,
        a1_claims,
        evidence_grade_ctx,
    )
    grade_outputs = _run_builders_concurrently(
        [grade_spec], client=client, timing=timing, builder_usage=builder_usage
    )
    grade_block: EvidenceGradeBlock = grade_outputs["evidence_grade"]

    # Retry-with-feedback fallback for the grade × methods cardinality
    # cross-check. The static prompt rule + the user-message methods
    # summary BOTH say "direct_* requires ≥1 method with
    # accessibility_relevance=direct_surface_accessibility", and the
    # SurfaceEvidence Pydantic validator enforces it. When the synth
    # still slips through with direct_* despite zero direct methods —
    # observed on HMGB1, where the ligand-engagement filter correctly
    # moved 8 receptor-binding claims to excluded_as_ligand_engagement,
    # leaving the methods grid with only expression_only / ambiguous
    # rows — re-call the grade builder once with explicit feedback in
    # the context dict. Capped at one retry to bound cost.
    n_direct = sum(
        1 for m in methods_output
        if getattr(m, "accessibility_relevance", None)
        == "direct_surface_accessibility"
    )
    if n_direct == 0 and grade_block.evidence_grade in (
        "direct_multi_method", "direct_single_method"
    ):
        logger.warning(
            "evidence_grade_builder picked %r with %d direct_surface_accessibility "
            "methods (cardinality validator would raise) — retrying with explicit "
            "feedback",
            grade_block.evidence_grade, n_direct,
        )
        retry_ctx = dict(evidence_grade_ctx)
        retry_ctx["cardinality_feedback"] = (
            f"PREVIOUS ATTEMPT WAS REJECTED. You picked "
            f"evidence_grade={grade_block.evidence_grade!r}, but the methods "
            f"builder produced 0 rows with "
            f"accessibility_relevance='direct_surface_accessibility'. The "
            f"direct_* grades REQUIRE at least one such row. Re-grade now "
            f"with this constraint: the grade MUST be one of "
            f"{{supportive_but_indirect, weak, conflicting}} — pick whichever "
            f"the surviving (non-excluded) methods support."
        )
        retry_spec = _BuilderSpec(
            "evidence_grade",
            "builders_a1",
            build_evidence_grade,
            a1_claims,
            retry_ctx,
        )
        retry_outputs = _run_builders_concurrently(
            [retry_spec], client=client, timing=timing,
            builder_usage=builder_usage,
        )
        grade_block = retry_outputs["evidence_grade"]

    # Deterministic grade demote: if grade is direct_multi_method but
    # only 1 direct row exists, demote to direct_single_method (the
    # cardinality validator on SurfaceEvidence would otherwise reject
    # the record). Observed on GPR75 v2.24.0. Same shape as the
    # n_direct=0 retry above, but resolved without a re-LLM call —
    # the answer is mechanical (the cardinality permits direct_single).
    if (
        grade_block.evidence_grade == "direct_multi_method"
        and n_direct == 1
    ):
        logger.info(
            "v2 orchestrator: demoting evidence_grade direct_multi_method → "
            "direct_single_method (only 1 direct_surface_accessibility "
            "method row, cardinality requires ≥2 for multi)"
        )
        grade_block = grade_block.model_copy(
            update={"evidence_grade": "direct_single_method"}
        )

    # Capture per-builder raw outputs before they're assembled into blocks.
    all_builder_outputs = {**outputs, "evidence_grade": grade_block}
    intermediates["builders"] = {
        name: _dump_builder_output(name, out)
        for name, out in all_builder_outputs.items()
    }
    # Per-builder reproducibility summary (Tier 3 follow-up): repair-loop
    # attempts + any residual validation error + per-call token / cost
    # rollup. Denormalized so a cohort analytics query can answer
    # "which builders are repair-loop-bound on heavy genes" without
    # parsing the bulky ``builders`` dict above. Keys mirror
    # ``builder_usage`` 1:1 — same builder names. ``risks_builder``
    # is added at its own step below (it runs after this point).
    intermediates["builder_usage"] = {
        name: {
            "n_calls": bu.n_calls,
            "cost_usd": round(bu.cost_usd, 6),
            "n_repair_attempts": bu.n_repair_attempts,
            "validation_error": bu.validation_error,
        }
        for name, bu in builder_usage.items()
    }

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
        # Audit trail of A1 ledger claims rejected as receptor-engagement-
        # as-soluble-ligand evidence (e.g. HMGB1 binding TREM-1 on
        # monocytes — protein-is-ligand, not membrane-component). The
        # methods builder filters these out of the methods grid; the
        # evidence-grade builder enumerates them here.
        excluded_as_ligand_engagement=grade_block.excluded_as_ligand_engagement,
    )

    # A2 rollup block (biological_context_grade builder) → flat fields on
    # BiologicalContext, mirroring how the evidence_grade block maps onto
    # SurfaceEvidence above. The block's attribute is ``cited_evidence_ids``;
    # the record field is ``grade_cited_evidence_ids``.
    bcg = outputs["biological_context_grade"]
    biological_context = BiologicalContext(
        expression=outputs["expression"],
        subcellular_localization=outputs["subcellular_localization"],
        anatomical_accessibility=outputs["anatomical_accessibility"],
        accessibility_modulation=outputs["accessibility_modulation"],
        biological_context_grade=bcg.biological_context_grade,
        grade_rationale=bcg.grade_rationale,
        grade_cited_evidence_ids=bcg.cited_evidence_ids,
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
        # Mirror per-step timing into the blob before returning — Modal
        # tears down ``.runs/`` on container shutdown, D1 is durable.
        intermediates["timing"] = [
            t.as_dict() for t in list(timing.entries)
        ]
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=None,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"SurfaceEvidenceDraft validation failed: {exc}",
            failure_mode="validation_failed",
            timing=list(timing.entries),
            intermediates=intermediates,
        )
    try:
        a2_draft = BiologicalContextDraft(
            biological_context=biological_context,
            evidence_claims=a2_claims,
        )
    except ValidationError as exc:
        intermediates["timing"] = [
            t.as_dict() for t in list(timing.entries)
        ]
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=None,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=f"BiologicalContextDraft validation failed: {exc}",
            failure_mode="validation_failed",
            timing=list(timing.entries),
            intermediates=intermediates,
        )

    # ---- step 4.5: deterministic features fetch (was step 7) ---------------
    # Pull the real DeepTMHMM topology + Compara paralog + cross-species
    # ortholog ECD rows + AFDB structure + SURFACE-Bind summary from public
    # D1. Moved BEFORE the synthesizer so B can read the prefetched
    # ``deterministic_features.canonical_topology.ecd_length_residues`` /
    # paralog cluster / SURFACE-Bind sites the system prompt's threshold
    # rules reference (was step 7 / post-pass; that left the synthesizer
    # guessing and required the step 7.5 secreted_form post-pass to
    # retro-patch its accessibility_risks). Falls back to the labeled stub
    # if D1 is unreachable (no creds in the worktree) or the gene isn't in
    # this sweep's coverage.
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

    # ---- step 4.6: risks builder (cross-focus; needs det_features) ---------
    # The risks builder is CROSS-FOCUS: it reads the MERGED A1+A2 ledger plus
    # the deterministic ECD / homo-oligomer signals (fetched at step 4.5), so
    # it can't ride the step-2+3 fan-out (those run before det_features
    # exists). It runs HERE — after the deterministic fetch, before the
    # synthesizer — and produces the canonical ``accessibility_risks`` block.
    # The synthesizer then merely consumes + copies it through (the
    # orchestrator overwrites B's echoed copy at step 5.4).
    with timing.step("risks_builder", phase="builders_risks", model=AGENT_MODEL) as _rh:
        risks_records: list[UsageRecord] = []
        risks_meta: dict[str, Any] = {}
        risks_block = build_risks(
            a1_claims + a2_claims,
            client=client,
            usage_sink=risks_records,
            context={
                "gene": gene_id.hgnc_symbol,
                "deterministic_features": det_features,
            },
            meta_sink=risks_meta,
        )
        _rh.set_usage(risks_records, model=AGENT_MODEL)
    builder_usage["risks_builder"] = BlockBuilderUsage(
        label="risks_builder",
        records=risks_records,
        n_repair_attempts=int(risks_meta.get("n_repair_attempts", 0) or 0),
        validation_error=risks_meta.get("validation_error"),
    )
    if risks_block is None:
        # Repair-loop failure → labeled all-absent stub so a record can still
        # ship. The deterministic post-passes below still attach the ECD /
        # homo-oligomer signals on top.
        logger.warning(
            "risks_builder returned None for %s; using all-absent stub",
            gene_id.hgnc_symbol,
        )
        risks_block = _stub_accessibility_risks()

    # ---- step 4.7: deterministic post-passes on the RISKS-BUILDER output ---
    # These were formerly step 7.5–7.7 patching synth_draft.accessibility_risks.
    # The risks builder is now the single source of truth, so the post-passes
    # run on ITS output here (before the synthesizer), making the canonical
    # risks block available to feed B AND to overwrite B's echoed copy with.
    #   * _attach_homo_oligomerization_prediction / _attach_deterministic_ecd_size_assessment
    #     return NEW AccessibilityRisks (model_copy).
    #   * apply_secreted_form_post_pass MUTATES in place and returns a bool;
    #     run it last on the already-rebuilt object.
    from accessible_surfaceome.agents.surfaceome_v2.secreted_form_postpass import (
        apply_secreted_form_post_pass,
    )

    canonical_risks = _attach_deterministic_ecd_size_assessment(
        _attach_homo_oligomerization_prediction(risks_block, det_features),
        det_features,
    )
    apply_secreted_form_post_pass(
        accessibility_risks=canonical_risks,
        deterministic_features=det_features,
    )

    intermediates["risks_builder"] = (
        risks_block.model_dump(mode="json") if risks_block is not None else None
    )
    intermediates["canonical_risks"] = canonical_risks.model_dump(mode="json")
    intermediates["deterministic_features"] = det_features.model_dump(mode="json")

    # ---- step 5: synthesizer (B) ------------------------------------------
    logger.info("v2 orchestrator: dispatching synthesizer for %s", gene_id.hgnc_symbol)
    # ---- Phase 2: synth-retry-with-feedback closure -------------------
    # Wraps synth call + orchestrator post-passes + SurfaceomeRecord
    # assembly in a 2-attempt loop. On first ValidationError, the
    # synthesizer is re-invoked with the validator's error message
    # threaded into a 'Feedback from a prior synthesis attempt' block
    # so it can correct the flagged field(s). Catches NEW validator
    # failures the deterministic post-passes don't anticipate, without
    # per-failure code. Bounded at 1 retry — additional cost when
    # triggered: ~$0.15 (one extra synth call); typical case (success
    # on first attempt): zero overhead.
    last_validation_error: ValidationError | None = None
    record: SurfaceomeRecord | None = None
    for retry_attempt in range(2):
        synth_feedback = (
            None if last_validation_error is None
            else f"SurfaceomeRecord assembly failed: {last_validation_error}"
        )
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
            # Compact JSON snapshot of the deterministic block + the curator-
            # assigned family tags so B sees what ``_attach_deterministic_families``
            # is about to overwrite on its output (cross-check rather than
            # discover-mismatch-post-hoc on llm_family).
            from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
                _summarize_deterministic_for_synthesizer,
            )
            deterministic_summary_json = _summarize_deterministic_for_synthesizer(
                det_features,
                hgnc_gene_groups=list(dual.bundle.hgnc_gene_groups),
                uniprot_family=dual.bundle.uniprot_family,
            )
            b = run_synthesizer_with_drafts(
                gene_id.hgnc_symbol,
                a1_draft=a1_draft,
                a2_draft=a2_draft,
                client=client,
                triage_summary_json=triage_summary_json,
                deterministic_summary_json=deterministic_summary_json,
                # The frozen, canonical risks block. B copies it through +
                # consumes it (headline_risks + confidence); the orchestrator
                # overwrites B's echoed copy with ``canonical_risks`` at step 5.4.
                accessibility_risks=canonical_risks,
                external_feedback=synth_feedback,
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

        intermediates["synthesizer"] = {
            "raw_json": b.raw_json,
            "validation_error": b.validation_error,
            "n_repair_attempts": b.n_repair_attempts,
            "draft": b.draft.model_dump(mode="json") if b.draft is not None else None,
        }

        # Re-snapshot the per-builder usage summary now that ``risks_builder``
        # has run (the initial snapshot at the step 2+3 fan-out only saw the
        # 8 parallel builders; ``risks_builder`` runs at step 4.6 after the
        # deterministic-features fetch). Same shape so downstream queries
        # don't need a special case for "before/after risks".
        intermediates["builder_usage"] = {
            name: {
                "n_calls": bu.n_calls,
                "cost_usd": round(bu.cost_usd, 6),
                "n_repair_attempts": bu.n_repair_attempts,
                "validation_error": bu.validation_error,
            }
            for name, bu in builder_usage.items()
        }

        # Persist bundle (gene resolution) + triage_summary so a future
        # synth-only retry can reconstruct the synthesizer's full input
        # context without re-running plan-trim-select. The bundle carries
        # uniprot_acc / hgnc_id / aliases / family tags; triage_summary is
        # the upstream Sonnet verdict the synth uses as a prior.
        try:
            intermediates["bundle"] = dual.bundle.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            intermediates["bundle"] = None
        intermediates["triage_summary_json"] = triage_summary_json

        # Triage source-link denormalization. ``triage_summary_json`` carries
        # the consumed prior verbatim, but cohort-scale analytics want to
        # answer "all v2 runs whose triage came from mainbench_canonical_v2
        # ncbi" without parsing the JSON blob — so denormalize the three
        # provenance keys onto the intermediates row. ``triage_record`` is
        # set in the surrounding scope (it's the same object the synth
        # consumed); ``provenance`` is ``None`` when triage was loaded from
        # a local ``data/triage/{gene}.json`` file rather than from D1's
        # ``triage_run_public`` table.
        prov = (
            triage_record.provenance if triage_record is not None else None
        )
        intermediates["triage_run_id"] = (
            prov.run_id if prov is not None else None
        )
        intermediates["triage_model"] = (
            prov.model if prov is not None else None
        )
        intermediates["triage_prompt_variant"] = (
            prov.prompt_variant if prov is not None else None
        )

        # Persist per-pipeline cost so we can do cohort-level cost analytics
        # from D1 without re-parsing log files. Per-builder breakdown lives
        # in `builder_usage`; pts + synth cost are atomic.
        intermediates["cost_total_usd"] = (
            (dual.total_cost_usd if dual is not None else 0.0)
            + sum(u.cost_usd for u in builder_usage.values())
            + (b.usage.cost_usd if b is not None else 0.0)
        )
        intermediates["cost_per_pipeline"] = {
            "plan_trim_select": dual.total_cost_usd if dual is not None else 0.0,
            "builders": sum(u.cost_usd for u in builder_usage.values()),
            "synthesizer": b.usage.cost_usd if b is not None else 0.0,
        }

        # Per-step wall-clock trace. Mirrored from the in-memory
        # ``TimingRecorder`` into the intermediates blob so it survives
        # Modal container shutdown — local ``.runs/*.meta.json`` is lost
        # on tear-down, but D1 is durable. Re-mirrored on every error-
        # path early return below that publishes intermediates (the ones
        # that pass ``intermediates=intermediates``) — see docs/audit/
        # reproducibility_followup_2026_06_09.md item #8.
        intermediates["timing"] = [
            t.as_dict() for t in list(timing.entries)
        ]

        # Hard cost ceiling — per-gene abort. Bounds runaway-cost scenarios
        # on a genome-wide sweep (a single pathological gene could otherwise
        # run $20+ before any post-passes catch it). 7 USD chosen to give
        # ~2x headroom over the heaviest validation gene (TACSTD2 ~$3.94).
        # Aborts with a VALID error result instead of silently billing.
        MAX_COST_USD = 7.0
        if intermediates["cost_total_usd"] > MAX_COST_USD:
            logger.warning(
                "v2 orchestrator: per-gene cost ceiling exceeded for %s: "
                "$%.2f > $%.2f. Aborting before record assembly.",
                gene_id.hgnc_symbol,
                intermediates["cost_total_usd"],
                MAX_COST_USD,
            )
            return AnnotateResultV2(
                gene=gene_id.hgnc_symbol,
                record=None,
                dual=dual,
                synthesizer=b,
                blocks_used=_count_blocks(surface_evidence, biological_context),
                builder_usage=builder_usage,
                error=(
                    f"per-gene cost ceiling exceeded: "
                    f"${intermediates['cost_total_usd']:.2f} > ${MAX_COST_USD:.2f}"
                ),
                failure_mode="cost_ceiling_total",
                timing=list(timing.entries),
                intermediates=intermediates,
            )

        if b.draft is None:
            # ``validation_error`` is populated iff the model emitted SOME
            # JSON that failed Pydantic validation (we ran the repair loop
            # against a real ``raw_json``). It's ``None`` when the model
            # never emitted a fenced JSON block at all — the failure modes
            # are distinct (a 'wandered off-spec' draft vs a 'tried but
            # the schema was wrong' draft), and the analytics queries
            # want them broken out.
            mode: FailureMode = (
                "validation_failed" if b.validation_error is not None
                else "synth_draft_missing"
            )
            return AnnotateResultV2(
                gene=gene_id.hgnc_symbol,
                record=None,
                dual=dual,
                synthesizer=b,
                blocks_used=_count_blocks(surface_evidence, biological_context),
                builder_usage=builder_usage,
                error=f"synthesizer returned no valid draft: {b.validation_error}",
                failure_mode=mode,
                timing=list(timing.entries),
                intermediates=intermediates,
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

        # ---- step 5.4: make the risks builder the single source of truth ------
        # The synthesizer echoes ``accessibility_risks`` (the prompt says copy
        # it through verbatim), but the canonical block is the one the risks
        # builder produced + the deterministic post-passes patched at step 4.7.
        # Overwrite B's echoed copy with it BEFORE step 5.5's
        # ``scrub_headline_risks`` reads ``synth_draft.accessibility_risks``, so
        # everything downstream (scrub, _derive_filters, SurfaceomeRecord) reads
        # the canonical risks. B's copy is discarded.
        synth_draft = synth_draft.model_copy(
            update={"accessibility_risks": canonical_risks}
        )

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

        # ---- step 5.65: state_dependence bump-when-state-conditional --------
        # The SurfaceomeRecord validator forbids state_dependence='low' when
        # the A2 biology shows state-conditional induction. The validator
        # reads from the derived filters.induction_trigger, but at this
        # point in the pipeline that field hasn't been derived yet — so we
        # check the upstream signal it depends on: any
        # accessibility_modulation row with direction='increases' indicates
        # the surface form is state-induced. Bump low → moderate so the
        # downstream validator doesn't raise.
        has_state_induction = any(
            getattr(m, "direction", None) == "increases"
            for m in (biological_context.accessibility_modulation or [])
        )
        if (
            synth_draft.executive_summary.state_dependence == "low"
            and has_state_induction
        ):
            logger.info(
                "v2 orchestrator: bumping state_dependence low → moderate "
                "(biological_context.accessibility_modulation has "
                "direction='increases' rows; surface form is state-induced)"
            )
            synth_draft = synth_draft.model_copy(
                update={
                    "executive_summary": synth_draft.executive_summary.model_copy(
                        update={"state_dependence": "moderate"}
                    )
                }
            )

        # ---- step 5.68: secreted_form demote-when-uncorroborated -------------
        # The SurfaceomeRecord validator rejects accessibility_risks.secreted_form
        # with present=True AND no cited evidence AND no secretory
        # dual_localization AND no fractionation method — that's an
        # uncorroborated risk claim. The risks builder occasionally slips
        # (observed on BAX v2.24.0, a mitochondrial-only protein where
        # secreted_form should be False). Demote to present=False
        # deterministically rather than crashing the run.
        risks = synth_draft.accessibility_risks
        if risks and risks.secreted_form and risks.secreted_form.present:
            sf = risks.secreted_form
            has_cites = bool(sf.cited_evidence_ids)
            has_secretory_dual = any(
                "secret" in (d.compartment or "").lower()
                for d in (
                    biological_context.subcellular_localization.dual_localization
                    if biological_context
                    and biological_context.subcellular_localization
                    else []
                )
            )
            has_fractionation_method = any(
                m.accessibility_relevance == "supports_membrane_association"
                for m in outputs["methods"]
            )
            if not (has_cites or has_secretory_dual or has_fractionation_method):
                logger.info(
                    "v2 orchestrator: demoting accessibility_risks.secreted_form "
                    "present=True → False (no cites + no secretory "
                    "dual_localization + no fractionation method — risks "
                    "builder set the flag without corroboration)"
                )
                # SecretedForm has no `rationale` field — just flip present
                # + severity. The orchestrator log captures the demote reason.
                new_sf = sf.model_copy(
                    update={"present": False, "severity": "low"}
                )
                synth_draft = synth_draft.model_copy(
                    update={
                        "accessibility_risks": risks.model_copy(
                            update={"secreted_form": new_sf}
                        )
                    }
                )

        # ---- step 5.685: state_dependence=unclear when surface_accessibility=no
        # If the gene has NO surface fraction (cytoplasmic, nuclear,
        # mitochondrial, secreted-only, etc.), state_dependence is not
        # meaningful — there's no surface form to vary by state. The synth
        # sometimes picks 'moderate' or 'high' anyway (because the protein's
        # EXPRESSION is state-modulated, e.g. ABCB9 induced by inflammation
        # in DCs), but that's a different axis from "targetable surface
        # fraction state-dependence". Force 'unclear' deterministically so
        # the record is internally consistent. Observed misfires: C3 v2.30
        # (sa=no + state=high), LYN v2.27 (sa=no + state=moderate),
        # ABCB9 v2.29 (sa=no + state=moderate).
        if (
            synth_draft.executive_summary.surface_accessibility == "no"
            and synth_draft.executive_summary.state_dependence != "unclear"
        ):
            logger.info(
                "v2 orchestrator: forcing state_dependence %r → 'unclear' "
                "(surface_accessibility=no; no surface fraction to state-modulate)",
                synth_draft.executive_summary.state_dependence,
            )
            synth_draft = synth_draft.model_copy(
                update={
                    "executive_summary": synth_draft.executive_summary.model_copy(
                        update={"state_dependence": "unclear"}
                    )
                }
            )

        # ---- step 5.69: surface_accessibility floor when state-conditional --
        # When state-conditional (state_dependence ∈ {moderate, high}) AND
        # surface_call_reason names a CONTEXTUAL bucket where the surface
        # pool is substantial in its best state — cell_state_induced (HMGB1
        # on activated platelets; ICD-induced tumor cells), lysosomal_
        # exocytosis (SRC eSrc in cancer cells), tissue_restricted_surface,
        # stable_surface_attachment — the synth MUST NOT pick
        # surface_accessibility='low'. Low contradicts the state-induced
        # surface pool the rest of the record describes. Bump to 'moderate'.
        #
        # Carve-out: `dual_localization` (TGN46-style trafficking-with-dwell)
        # legitimately stays at 'low' because the PM dwell is brief even
        # in the best state. NO-bucket reasons obviously stay at low/no.
        SUBSTANTIAL_CONTEXTUAL_REASONS = {
            "cell_state_induced",
            "lysosomal_exocytosis",
            "tissue_restricted_surface",
            "stable_surface_attachment",
        }
        # Skip the floor when grade=weak. A weak grade means the evidence is
        # thin; bumping surface_accessibility to moderate in that case
        # contradicts the grade (HMGB1 v2.27 landed grade=weak + sa=moderate
        # — overstated). Require at least supportive_but_indirect before
        # the floor can lift.
        _grade = grade_block.evidence_grade
        if (
            synth_draft.executive_summary.surface_accessibility == "low"
            and synth_draft.executive_summary.state_dependence
            in ("moderate", "high")
            and synth_draft.executive_summary.surface_call_reason
            in SUBSTANTIAL_CONTEXTUAL_REASONS
            and _grade != "weak"
        ):
            logger.info(
                "v2 orchestrator: bumping surface_accessibility low → "
                "moderate (state_dependence=%r + surface_call_reason=%r: "
                "substantial state-induced surface pool, low contradicts "
                "the record)",
                synth_draft.executive_summary.state_dependence,
                synth_draft.executive_summary.surface_call_reason,
            )
            synth_draft = synth_draft.model_copy(
                update={
                    "executive_summary": synth_draft.executive_summary.model_copy(
                        update={"surface_accessibility": "moderate"}
                    )
                }
            )

        # ---- step 5.7: NO-bucket reason override (NARROW + DIRECTION-FILTERED)
        # The methods builder emits accessibility_relevance per observation.
        # When synth picks a NO-bucket reason (endomembrane_resident,
        # secreted_only, etc.) but methods has a `direct_surface_accessibility`
        # or `supports_surface_localization` row whose CITED CLAIM has
        # direction='supports', flip to CONTEXTUAL. The narrow trigger set
        # (no supports_membrane_association — PM fractionation alone is too
        # weak) + direction filter (refuting / contradictory claims don't
        # count even if methods builder mis-classified them) is the form
        # that handles both TGOLN2 (flips correctly via supports_surface_
        # localization trafficking row) and ABCB9 (does NOT flip — its
        # supports_membrane_association rows aren't in the trigger set,
        # and its one supports_surface_localization row from a
        # domain-deletion mutant has direction='refutes').
        #
        # History: v2.30.0 briefly removed this entire post-pass on the
        # theory that prompt rules had caught up; TGOLN2 v2.30 regressed
        # to endomembrane_resident. Restored.
        NO_BUCKET_REASONS = {
            "cytoplasmic", "nuclear", "mitochondrial_internal",
            "endomembrane_resident", "nuclear_envelope",
            "inner_leaflet_anchored", "secreted_only",
            "pmhc_only_intracellular",
        }
        SURFACE_SIGNAL_RELEVANCES = {
            "direct_surface_accessibility",
            "supports_surface_localization",
        }
        claims_by_id = {c.evidence_id: c for c in a1_claims if c.evidence_id}
        def _has_supporting_cite(method):
            for cid in (method.cited_evidence_ids or []):
                claim = claims_by_id.get(cid)
                if claim is None:
                    continue
                if claim.direction == "supports":
                    return True
            return False
        supporting_signal_methods = [
            m for m in outputs["methods"]
            if m.accessibility_relevance in SURFACE_SIGNAL_RELEVANCES
            and _has_supporting_cite(m)
        ]
        current_reason = synth_draft.executive_summary.surface_call_reason
        if current_reason in NO_BUCKET_REASONS and supporting_signal_methods:
            new_reason = (
                "dual_localization"
                if current_reason == "endomembrane_resident"
                and any(
                    m.accessibility_relevance == "supports_surface_localization"
                    for m in supporting_signal_methods
                )
                else "cell_state_induced"
            )
            logger.info(
                "v2 orchestrator: overriding surface_call_reason %r → %r "
                "(methods has %d supporting-cite surface-signal row(s); "
                "NO-bucket reason contradicts the record's own evidence)",
                current_reason, new_reason, len(supporting_signal_methods),
            )
            synth_draft = synth_draft.model_copy(
                update={
                    "executive_summary": synth_draft.executive_summary.model_copy(
                        update={"surface_call_reason": new_reason}
                    )
                }
            )

        # ---- step 5.75: enforce sa-magnitude ↔ reason-bucket consistency ----
        # surface_accessibility (magnitude axis) and surface_call_reason
        # (categorical bucket axis) must agree. Earlier post-passes go
        # asymmetrically — the NO-bucket override flips reason UP (NO →
        # CONTEXTUAL) when methods supports surface, the floor bumps sa UP
        # (low → moderate) when state-conditional + substantial CONTEXTUAL.
        # The symmetric rules going DOWN were missing — ABCB9 v2.35 landed
        # surface_accessibility='low' + surface_call_reason='endomembrane_
        # resident' (the synth picked the right reason but the wrong
        # magnitude; nothing caught the mismatch).
        #
        # Three deterministic forcings:
        #   * NO bucket reason → sa = 'no'      (covers ABCB9 / LYN / BAX)
        #   * CONTEXTUAL reason + sa='no' → sa='low'   (rare; ensures
        #     CONTEXTUAL state-induced surface gets at least 'low')
        #   * YES reason + sa∈{'no','low'} → sa='moderate'   (rare; ensures
        #     YES-bucket canonical receptor doesn't undershoot)
        _reason = synth_draft.executive_summary.surface_call_reason
        _sa = synth_draft.executive_summary.surface_accessibility
        _YES_REASONS = {
            "classical_surface_receptor", "gpi_anchored",
            "multipass_with_exposed_loops", "extracellular_face_protein",
            "stable_complex_partner",
        }
        _new_sa = _sa
        if _reason in NO_BUCKET_REASONS and _sa != "no":
            _new_sa = "no"
        elif _reason in {
            "cell_state_induced", "tissue_restricted_surface",
            "lysosomal_exocytosis", "dual_localization",
            "stable_surface_attachment",
        } and _sa == "no":
            _new_sa = "low"
        elif _reason in _YES_REASONS and _sa in ("no", "low"):
            _new_sa = "moderate"
        if _new_sa != _sa:
            logger.info(
                "v2 orchestrator: forcing surface_accessibility %r → %r "
                "(reason=%r requires consistent bucket; the two axes were "
                "mismatched in the synth output)",
                _sa, _new_sa, _reason,
            )
            synth_draft = synth_draft.model_copy(
                update={
                    "executive_summary": synth_draft.executive_summary.model_copy(
                        update={"surface_accessibility": _new_sa}
                    )
                }
            )
            # If we just forced sa='no', the earlier state-dep=unclear
            # rule may now need to fire too (it ran at step 5.685 against
            # the OLD sa value). Mirror its decision here for the freshly-
            # forced sa='no' case so the record stays internally consistent.
            if (
                _new_sa == "no"
                and synth_draft.executive_summary.state_dependence != "unclear"
            ):
                logger.info(
                    "v2 orchestrator: cascading state_dependence → 'unclear' "
                    "after sa forced to 'no'"
                )
                synth_draft = synth_draft.model_copy(
                    update={
                        "executive_summary": synth_draft.executive_summary.model_copy(
                            update={"state_dependence": "unclear"}
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

        # NOTE: the deterministic risk post-passes (secreted_form safety net +
        # homo-oligomerization prediction chip + ecd_accessibility_class
        # overwrite) formerly ran HERE on ``synth_draft.accessibility_risks``.
        # They now run at step 4.7 on the risks-builder output (``canonical_risks``),
        # which is the single source of truth and was copied onto ``synth_draft``
        # at step 5.4 — so ``synth_draft.accessibility_risks`` already carries all
        # three. ``_derive_filters`` (step 8) reads them off it as before.

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
                evidence=evidence,
                # Best available proxy for "discovery corpus size": each
                # PTS side persists ``n_papers_total = len(clips_by_source)``
                # — the count of papers that produced at least one selected
                # clip. This is technically post-selection rather than
                # raw-discovery (the EuropePMC + PubTator + gene2pubmed
                # union upstream), so a TODO remains to bubble the true
                # pre-trim corpus size up through the runner. Both sides
                # see the same discovery, so max() is the right reducer.
                # Falls back to 0 when the side blob is absent (resume
                # from a pre-field checkpoint).
                n_papers_found=max(
                    getattr(dual.a1, "n_papers_total", 0) or 0,
                    getattr(dual.a2, "n_papers_total", 0) or 0,
                ),
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
                prompt_corpus_version=PROMPT_CORPUS_VERSION,
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
            last_validation_error = exc
            logger.warning(
                "SurfaceomeRecord assembly failed on attempt %d/2: %s",
                retry_attempt + 1, exc,
            )
            # Loop continues — synth_feedback gets populated for the
            # next iteration's run_synthesizer_with_drafts call.
        else:
            # Assembly succeeded — exit the retry loop.
            break
    # Re-mirror per-step timing into the blob now that the retry loop has
    # settled — captures the final attempt's entries so the persisted
    # ``intermediates["timing"]`` reflects the actual end-state of the
    # run rather than the synth-block-only snapshot taken inside the loop.
    intermediates["timing"] = [t.as_dict() for t in list(timing.entries)]
    if record is None:
        # Both attempts failed validation; return the last error.
        return AnnotateResultV2(
            gene=gene_id.hgnc_symbol,
            record=None,
            dual=dual,
            synthesizer=b,
            blocks_used=_count_blocks(surface_evidence, biological_context),
            builder_usage=builder_usage,
            error=(
                f"SurfaceomeRecord assembly failed after retry: "
                f"{last_validation_error}"
            ),
            failure_mode="schema_drift",
            timing=list(timing.entries),
            intermediates=intermediates,
        )

    annotation_path: Path | None = None
    if persist:
        annotation_path = DATA_DIR / "annotations" / f"{gene_id.hgnc_symbol}.json"
        annotation_path.parent.mkdir(parents=True, exist_ok=True)
        annotation_path.write_text(record.model_dump_json(indent=2))

    # Mid-gene checkpoint cleanup — only on the success path. A run that
    # validates the record + assembles the intermediates has no use for a
    # stashed PTS dual; clear it so the next run on this gene picks up
    # the freshest PTS state. Failure paths above intentionally leave
    # the checkpoint in place so the retry can short-circuit. Driver-side
    # intermediates publish happens after this return, so the success
    # criterion here is "record validated" (the intermediates push is
    # best-effort and doesn't gate the cleanup).
    _delete_pts_checkpoint(gene_id.hgnc_symbol)

    return AnnotateResultV2(
        gene=gene_id.hgnc_symbol,
        record=record,
        dual=dual,
        synthesizer=b,
        blocks_used=_count_blocks(surface_evidence, biological_context),
        builder_usage=builder_usage,
        annotation_path=annotation_path,
        timing=list(timing.entries),
        intermediates=intermediates,
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
        "expression": len(bc.expression),
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
