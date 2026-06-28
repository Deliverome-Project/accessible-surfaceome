"""Runner for the kickoff → discover → triage → trim → select loop.

End-to-end driver:

1. Resolve the gene (gene_lookup) so we have a UniProt acc + DB-vote
   panel for the selector's context.
2. Build a deterministic ``SearchPlan`` from a fixed per-focus kickoff
   template (``kickoff_templates.build_kickoff``) — no LLM planner.
3. Dispatch each ``SearchRequest`` via the existing tool entry points
   (``evidence_retrieval`` in discover-only mode, ``gene_literature``).
   These are discovery calls — they return paper metadata, not bodies.
4. Triage each newly-discovered paper's abstract with a Haiku call
   (``abstract_triage``): discard / keep_abstract / worth_fetching.
   keep_abstract adds abstract preview clip(s); worth_fetching fetches
   the body and extracts body clips. Both land in the pool.
5. Group pool clips by source paper; per-paper, ask Haiku to ``keep``
   the load-bearing ones (one call per paper).
6. Build the trimmed menu, ask Sonnet selector to pick clip_ids with
   classifications (no ``quote`` field).
7. Look up each picked clip in the pool, construct ``EvidenceClaim``
   records with ``quote`` = ``Clip.quote`` (verbatim by construction).
8. Return the claim list + audit traces + usage summary.

Single-pass: body-fetching is front-loaded into the triage step, so the
selector picks its rows from the menu in front of it and does not request
follow-up searches. (The legacy selector-driven iterate path was retired
once triage took over body acquisition.)
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import BaseModel, ValidationError

from accessible_surfaceome.agents._support.api_retry import (
    messages_create_with_backoff,
)
from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    UsageSummary,
    record_from_response,
    summarize_usage,
)
from accessible_surfaceome.agents._support.timing import StepTiming, TimingRecorder
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageAction,
    apply_triage_outcomes,
    paper_source_id,
    triage_abstracts,
)
from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import build_kickoff
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    SearchPlan,
    SelectionResponse,
    TrimResponse,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    EvidenceClaim,
    EvidenceClaimDraft,
    IdentifierBundle,
    LiteraturePack,
    OrthologEntry,
    Paper,
    TriageRecord,
)
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    RetractionIndex,
    empty as _empty_retraction_index,
)
from accessible_surfaceome.tools.evidence_retrieval import evidence_retrieval
from accessible_surfaceome.tools.gene_literature import gene_literature
from accessible_surfaceome.tools.gene_lookup import (
    db_panel,
    looks_like_uniprot_acc,
    resolve,
    resolve_by_hgnc_id,
    uniprot_summary,
)


logger = logging.getLogger(__name__)


PROMPTS_DIR = Path(__file__).parent / "prompts"

# Per-agent trim + select prompt variants. ``agent_focus="a1"`` uses the
# surface-evidence-focused prompts and the ``a1_evi_`` claim-id prefix
# that A1 block-builders downstream expect; ``"a2"`` likewise for the
# biological-context ledger. The legacy single-pass ``trim_system.md`` /
# ``select_system.md`` and their ``pts_evi_`` prefix were retired with
# the unified-ledger MVP path — production always runs the dual A1+A2
# driver, so both legs are mandatory.
A1_TRIM_PROMPT_PATH = PROMPTS_DIR / "a1_trim_system.md"
A1_SELECT_PROMPT_PATH = PROMPTS_DIR / "a1_select_system.md"
A2_TRIM_PROMPT_PATH = PROMPTS_DIR / "a2_trim_system.md"
A2_SELECT_PROMPT_PATH = PROMPTS_DIR / "a2_select_system.md"


# Trim-prompt cached-system + per-paper user split.
#
# The trim prompts mix gene-agnostic RULES (what A1/A2 cares about, what to
# drop, how to calibrate) with per-paper DATA (paper_id + clip list). For
# Anthropic prompt caching, the rules must be byte-identical across calls —
# so we split each template at the `## Output` header, swap any `{gene}`
# placeholders in the rules block for a fixed gene-agnostic phrase ("the
# target gene"), and substitute the JSON schema once. The result is a cached
# system prompt that's reused across every paper trimmed for a given gene
# (and across genes, when the 5-min TTL lets the cache survive between
# them).
#
# The per-paper user message carries the actual gene name explicitly
# ("Target gene: SLC7A5") in a preamble, then the legacy `## Output` block
# with paper_id + clips. Haiku sees the same content as before; the change
# is purely transport-level (where each part of the prompt lives).
#
# Haiku 4.5 prompt-cache floor: 4,096 tokens. Below that the API silently
# processes the request without caching — no error, no cache_read, no
# refund of the 1.25× write premium (per Anthropic docs as of 2026-06-08).
# The a1 / a2 trim prefixes were measured at 2,654 / 2,083 tokens by the
# 2026-06-08 cache-engagement probe (``scripts/probes/probe_cache_engagement.py``),
# i.e. both fell silently below the floor. ``_TRIM_CACHE_PAD`` is the
# fixed, byte-identical, semantically-neutral block we append to the
# cached rules to push the prefix above the floor (a1 lands at ~4,770
# tokens, a2 at ~4,263 — comfortably above 4,096 with margin for future
# minor prompt edits). The pad content is a gene-agnostic notes section
# about cache mechanics + trim discipline — content the model will read
# as additional context rather than as instructions that change its
# behaviour. The padded probe (Config 5) confirmed that crossing 4,096
# immediately engages caching: cwrite=4,583 on the write call,
# cread=4,583 on the read call. Cohort savings at 6,500 genes × ~80 trim
# calls/gene: ~$1,800 vs $0 today.
_TRIM_CACHE_PAD = """
## Cache-mechanics appendix (gene-agnostic; do not act on this section)

The Anthropic Messages API caches the ``system`` block when the cached
prefix crosses a documented per-model token floor (Haiku 4.5: 4,096).
Below the floor, the request is processed without caching. This trim
pipeline cares because the same set of rules above is replayed across
many per-paper trim calls within a single gene's deep-dive (often 30 to
100 calls per gene), and across genes within the cache's 5-minute
ephemeral TTL. A cached prefix is billed at 0.10x the cold-input rate
on every read after the first, and at 1.25x the cold-input rate on the
first write. The math is favourable as soon as a second call lands
within the TTL: even one cache read pays for the 0.25x write premium.

This appendix exists for two reasons. First, to push the cached prefix
above the 4,096-token floor so the cache actually engages — the rules
above are intentionally terse (faster to parse, less load on Haiku's
attention budget) and on their own come in under 3,000 tokens for
either focus. Second, to document the cache contract here, attached to
the prompt, so a future edit to the rules section can be reasoned
about with the cache constraint visible. If you are editing the rules
above and the cached prefix shrinks substantially, the cache may fall
silently below the floor again; the probe script
``scripts/probes/probe_cache_engagement.py`` is the way to verify this.

### What stays byte-identical across calls

The cache key for a system block is the verbatim text — a single
whitespace change invalidates the entry. The cached prefix must
therefore not contain any per-call variation. Concretely: no gene
symbol, no paper identifier, no schema serialization (the schema is
deterministic but its formatting can drift), no clip pool, no
threshold value that varies by run. All of those belong in the user
message, where they are billed at the cold-input rate per call but
do not invalidate the cache.

The split helper that produces this cached prefix substitutes every
``{gene}`` placeholder in the rules block above with the fixed phrase
"the target gene" before the prompt is hashed for the cache key. The
output section (everything after the ``## Output`` heading) is moved
into the per-call user message, where the actual gene symbol and the
paper-specific clip pool are spliced in. The clean split is what
allows a cohort-wide sweep to read from the same cached prefix; if a
future change accidentally moves a gene-specific token back into the
cached block, the cache key fragments per-gene and the read rate
collapses to zero across the entire cohort.

### What the trim call must NOT do

The trim call is a precision filter, not a re-reading. It receives a
clip pool that has already passed surface-evidence triage at the
abstract level; the question is which clips in the pool are
load-bearing for downstream block-builders versus which are noise.
The call MUST NOT: fabricate a clip that was not in the pool;
paraphrase a clip away from its verbatim form; reclassify a clip
into a different surface-evidence bucket than the trim schema
allows; or emit a clip without its source identifier. These are
hard contract violations, not stylistic preferences. The downstream
selector validates each emitted clip's source identifier against the
in-memory clip pool, so a fabricated identifier surfaces as an
immediate validation failure, not a silent data quality regression.

### What the trim call SHOULD prefer

For surface-evidence trim, the preferred clips are: explicit
surface-method language with a named cell line; co-mention of the
target gene with a surface-method assay in the same paragraph;
antibody-clone or reagent-RRID identifiers that can carry forward to
the methods builder. For biological-context trim, the preferred
clips are: explicit cell-type or tissue assignments with a primary
data source (single-cell atlas, IHC panel); pathway-level or
mechanism-level claims with a cited experimental basis; and
ligand-receptor or interaction claims with a reciprocal validation
(co-IP, proximity ligation, BioID). In both cases, REVIEW assertions
that merely restate a primary claim should be dropped in favour of
the primary clip itself when both are in the pool. When two clips
make the same claim with comparable specificity, prefer the one that
carries a reagent identifier, an experimental cell context, or a
quantitative readout — those are the clips that survive into the
downstream methods or accessibility blocks unchanged.

### Calibration discipline

The trim call's kept-rate per paper should reflect the paper's
actual signal density, not a target percentage. A methods-heavy
paper with a single qualifying assay panel for the target gene may
have 1 of 60 clips that are load-bearing; a review of the target
gene's surface biology may have 8 of 12 clips that are load-bearing.
Resist the pull toward a fixed mid-range kept-rate; the downstream
selector will deduplicate redundant kept-clips across papers, so
over-keeping at this stage is more expensive than under-keeping. An
under-kept clip can be re-surfaced by a later paper that quotes the
same finding; an over-kept clip imposes selector cost on every
subsequent gene without adding signal.

### A note on confidence scoring

Trim does not emit confidence scores — that is the selector's job
once the cross-paper view is assembled. If you find yourself
reasoning about how confident you are that a clip belongs in the
output, you are doing the selector's job; emit the clip and let the
selector triangulate. The trim call's job is binary per clip: load-
bearing for at least one downstream block-builder, or noise. The
selector has the cross-paper context that the trim call lacks —
confidence emerges from corroboration across independent papers, not
from in-clip prose; the trim call cannot see that signal.

### A note on terse output

The output schema is small by design. Emit only what the schema
demands. Do not add prose around the fenced JSON block. Do not
explain a kept-clip's reasoning unless the schema field for that
reasoning exists. Verbose output increases output-token cost
without improving downstream behaviour; the next stage reads the
JSON, not the prose. The JSON-extraction regex used downstream takes
the last fenced block; surrounding prose is silently ignored, which
is forgiving but wastes Haiku output tokens. Aim for a clean fenced
block with the schema-required fields and nothing else.

### Why the gene-agnostic phrasing matters

The cached rules block above has been carefully rewritten to never
mention the target gene symbol directly; every occurrence of the
template ``{gene}`` placeholder is substituted with "the target
gene" before the prompt enters the cache. This keeps the cache key
identical across all genes in the cohort, so the cache survives
gene-to-gene transitions within its 5-minute TTL. A future edit
that re-introduces a gene placeholder into the rules block will
fragment the cache key per-gene and silently collapse the cache
hit rate to zero across the cohort; the probe script will catch
this if you run it post-edit. The probe is also the way to verify
that a deliberate prompt edit hasn't pushed the cached prefix back
below the Haiku 4.5 floor — running it after a prompt change costs
about ten cents and prevents a silent regression in cohort-wide
cost behaviour.

### Source-identifier discipline

Every clip in the pool carries a source identifier that anchors it
back to a single paper and section. The identifier shape encodes
the paper's primary identifier (PMC, PMID, or DOI in that
preference order), the section of the paper the clip was extracted
from (methods, results, discussion, figure caption, table caption),
and a within-paper sequence number. The trim call must emit each
kept-clip's identifier verbatim from the pool — no shortening, no
normalization, no re-derivation from the paper-level metadata. The
downstream code that looks each kept-clip back up in the in-memory
pool requires byte-identical match on the identifier; any
normalization will silently drop the kept clip from the assembled
ledger.

### Section-weighting hints

Clips from a paper's methods or results sections generally carry
higher per-token signal than clips from a paper's introduction or
discussion. The introduction tends to restate prior work; the
discussion tends to speculate about mechanism. Neither shape is
disqualifying — a discussion paragraph that summarises a co-IP
result with a cited figure reference may be the only quoteable
form of that result in the corpus — but in the absence of a
specific reason to prefer the framing of an introduction or
discussion clip over a methods or results clip making the same
claim, prefer the methods or results clip. The downstream blocks
treat methods-section identifiers as a weak corroboration signal
for surface-evidence triage; the rule above is gene-agnostic but
the downstream weighting is not.

End of cache-mechanics appendix. The output section follows.
""".strip()


def _split_trim_template(template_text: str, schema_str: str) -> tuple[str, str]:
    """Return ``(cached_system_text, user_template)``.

    Splits at the first ``## Output`` heading. The rules block (everything
    before) gets ``{gene}`` → ``the target gene`` substitution so it's
    byte-identical across genes — required for the cache key. The user
    template (everything from ``## Output`` onward) keeps the original
    placeholders, to be filled per-call with the actual paper data.

    The schema is substituted into the user template too (it's only
    referenced in the output section). The cached system never carries
    `{schema}` so we don't have to worry about JSON-dump whitespace drift
    invalidating the cache key.

    A fixed ``_TRIM_CACHE_PAD`` block is appended to the cached rules so
    the cached prefix exceeds Haiku 4.5's 4,096-token cache minimum.
    Without it the cache silently fails to engage (see the 2026-06-08
    cache-engagement probe + audit in ``docs/audit/``).
    """
    parts = template_text.split("## Output", 1)
    if len(parts) != 2:
        # Defensive: prompt structure changed; fall back to the whole template
        # as the user message and an empty system (no caching). Loud log so
        # the prompt-corpus version test catches it.
        logger.warning(
            "trim template missing '## Output' header — caching disabled"
        )
        return "", template_text
    rules_block, output_section = parts[0], "## Output" + parts[1]
    cached_rules = rules_block.replace("{gene}", "the target gene")
    # Append the gene-agnostic cache-mechanics pad so the cached prefix
    # crosses Haiku 4.5's 4,096-token floor. The pad is byte-identical
    # across all calls and all genes — required for the cache key.
    cached_rules = cached_rules.rstrip() + "\n\n" + _TRIM_CACHE_PAD + "\n"
    return cached_rules, output_section


# Module-level cache: parsed trim template per path. Each entry is
# ``(cached_system_text, user_template_with_schema_substituted)``. Populated
# lazily on first use of each prompt path so test overrides still work
# (legacy tests sometimes pass a custom template string in directly).
_TRIM_TEMPLATE_CACHE: dict[Path, tuple[str, str]] = {}

AgentFocus = Literal["a1", "a2"]

# evidence_id prefix per focus. Per-agent prefixes are what
# ``SurfaceEvidenceDraft._check_claim_id_prefix`` / the matching A2
# validator expect when Phase 2's block builders run.
_EVIDENCE_ID_PREFIX: dict[str, str] = {
    "a1": "a1_evi_",
    "a2": "a2_evi_",
}

SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_PRICING_KEY = "claude-haiku-4-5"

MAX_TOKENS_TRIM = 4_000
# Headroom against the repair-loop cliff: a selector output that overruns
# this ceiling truncates mid-JSON, fails schema validation, and re-runs
# (up to MAX_REPAIRS), multiplying cost ~3x. The dedup discipline in the
# select prompts keeps a typical ledger to ~20-30 claims (~9k tokens), but
# 20k lets a legitimately evidence-rich gene's ~40-claim output land in one
# call instead of a repair cascade. Lower only if you confirm outputs stay
# small; raising further just delays the same cliff.
MAX_TOKENS_SELECT = 20_000
MAX_REPAIRS = 2
TRIM_PREVIEW_CHARS = 700

# Cap per-paper clip pool size sent to Haiku trim. Above this, sort by score
# (evidence_retrieval drafts carry a score; paper_level drafts default to ~1).
MAX_CLIPS_PER_TRIM_CALL = 60

# Maximum concurrent Haiku trim calls. Per-paper trims are independent
# (each is one ``messages.create`` against an independent prompt), so we
# fan them out across this many threads. ``10`` was chosen as the
# conservative ceiling that (a) keeps us well under the per-org request
# rate limit even for a 60-paper gene and (b) saturates the typical
# Haiku tail latency (~3-8s/call) without piling up requests behind
# slow ones. Raise if you confirm rate-limit headroom; lower if you
# observe 429s.
TRIM_CONCURRENCY = 10

# Single-pass: the deterministic kickoff runs once, triage front-loads all
# body-fetching, and the selector commits its picks without iterating. The
# selector-driven follow-up-search path was retired (it spent a full extra
# Sonnet call retrying fetches triage had already attempted). Kept as a
# named constant of 1 so the surrounding loop structure (cumulative pool,
# per-iteration audit) stays intact and iteration could be reintroduced if
# a future need is demonstrated.
MAX_PLAN_ITERATIONS = 1

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Result + log records
# ---------------------------------------------------------------------------


@dataclass
class SearchLogEntry:
    """One executed search with its outcome (for audit + cost attribution)."""

    tool: str
    params: dict[str, Any]
    intent: str
    n_drafts: int
    n_papers: int
    elapsed_s: float
    error: str | None = None


@dataclass
class IterationLogEntry:
    """One kickoff→execute→triage→trim→select cycle's headline stats.

    Retained as a list-of-one for audit-shape stability (the flow is now
    single-pass)."""

    iteration: int
    new_searches: int
    new_drafts: int
    n_papers_after: int
    n_drafts_after: int
    n_kept_after_trim: int
    n_selections: int


@dataclass
class PlanTrimSelectResult:
    """Output of one end-to-end run."""

    gene: str
    bundle: IdentifierBundle | None
    plan: SearchPlan | None
    selection_response: SelectionResponse | None
    # ``"a1"`` = surface-evidence focus, ``"a2"`` = biological-context
    # focus. Threaded through so the audit JSON makes the focus
    # explicit. The legacy single-pass (unified-ledger) path was
    # retired — every run must declare a focus.
    agent_focus: AgentFocus = "a1"
    claims: list[EvidenceClaim] = field(default_factory=list)
    search_log: list[SearchLogEntry] = field(default_factory=list)
    iteration_log: list[IterationLogEntry] = field(default_factory=list)
    # Per-paper abstract-triage decisions (discard / keep_abstract /
    # worth_fetching) + body-fetch outcomes. Audit trail for what entered
    # the pool and why.
    triage_actions: list[TriageAction] = field(default_factory=list)
    # Anchored-rate audit. Should be 100% by construction since we never
    # paraphrase, but verify so any regressions surface.
    n_claims: int = 0
    n_anchored: int = 0
    # Cost + token accounting per stage. ``plan_usage`` is retained for
    # backward-compatible audit shape but is always zero now that the LLM
    # planner is replaced by a deterministic kickoff template.
    plan_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=SONNET_MODEL)
    )
    triage_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=HAIKU_PRICING_KEY)
    )
    trim_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=HAIKU_PRICING_KEY)
    )
    select_usage: UsageSummary = field(
        default_factory=lambda: UsageSummary(model=SONNET_MODEL)
    )
    # Pool stats (final, after all iterations).
    n_drafts_total: int = 0
    n_papers_total: int = 0
    n_kept_after_trim: int = 0
    n_iterations_run: int = 0
    # Free-text errors that didn't abort the run.
    warnings: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    # Per-step wall-clock audit, populated when a TimingRecorder is
    # threaded through the run (orchestrator does this by default).
    timing: list[StepTiming] = field(default_factory=list)
    # Pre-trim filter decisions per iteration. Populated whether or not
    # the filter is enabled; shadow-mode runs collect the audit for
    # validation without actually dropping papers. Default empty.
    pretrim_audits: list[Any] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return (
            self.plan_usage.cost_usd
            + self.triage_usage.cost_usd
            + self.trim_usage.cost_usd
            + self.select_usage.cost_usd
        )

    @property
    def pct_anchored(self) -> float | None:
        if not self.n_claims:
            return None
        return 100.0 * self.n_anchored / self.n_claims


# ---------------------------------------------------------------------------
# Step 0 — gene context
# ---------------------------------------------------------------------------


@dataclass
class GeneContext:
    """Bundled gene context the planner + selector both read.

    HPA evidence is rolled into ``db_panel_json`` (the DBVotePanel carries
    HPA's main location + reliability flag alongside the SURFY/CSPA votes).

    ``deterministic_summary_json`` is a compact JSON snapshot of the
    DeepTMHMM topology + Compara paralog + cross-species ortholog ECD
    identity rows fetched from public D1 — see
    :func:`_summarize_deterministic_for_planner`. Falls back to ``None``
    when D1 is unreachable; planner prompts treat the missing block as
    "no deterministic data available" and omit it from the user prompt.

    ``triage_summary_json`` is a compact JSON snapshot of the persisted
    ``TriageRecord`` for this gene (verdict + verdict_reasoning + reason
    taxonomy + key_uncertainty + confidence). The planner reads it as a
    prior to confirm or refute. Falls back to ``None`` when no triage
    record exists; planner prompts treat the missing block the same way
    they do for the deterministic block. See
    :func:`_summarize_triage_for_planner`. Implements PR #23 design doc
    §1110-1116's "common preamble — triage_record".
    """

    gene: str
    bundle: IdentifierBundle
    uniprot_summary_json: str
    db_panel_json: str
    deterministic_summary_json: str | None = None
    triage_summary_json: str | None = None
    # Canonical topology counts threaded into the deterministic kickoff to
    # gate the membrane-specific standing axes. ``None`` means "topology
    # unknown" (D1 miss / placeholder) — the kickoff fires those axes
    # recall-biased rather than suppressing them on a coverage gap.
    n_tmh: int | None = None
    ecd_aa: int | None = None


def _summarize_deterministic_for_planner(features: DeterministicFeatures) -> str:
    """Compact JSON summary handed to the A1/A2 planners.

    Keeps the field set small enough that planners can scan it inline,
    while exposing the four signals A1/A2 prompts reference to weight
    their search plans: TM count + ECD length + signal peptide
    (methodology choice), top paralogs by ECD identity (paralog-class
    search opportunity), and mouse / cyno ortholog ECD identity
    (cross-species literature confidence). The canonical ortholog
    isoform is preferred when multiple isoforms are returned per
    species.
    """

    canon = features.canonical_topology
    # Sort: numeric identity first (high → low), then NULL-identity
    # paralogs (ECD-less proteins like SRC-family kinases). Sentinel -1
    # is below any valid 0-100 identity so Nones land at the end.
    top = sorted(
        features.paralogs,
        key=lambda p: (
            p.ecd_pct_identity if p.ecd_pct_identity is not None else -1.0
        ),
        reverse=True,
    )[:5]

    def _canonical(entries: list[OrthologEntry]) -> OrthologEntry | None:
        for entry in entries:
            if entry.is_canonical:
                return entry
        return entries[0] if entries else None

    mouse = _canonical(list(features.orthologs.mouse))
    cyno = _canonical(list(features.orthologs.cynomolgus))
    payload: dict[str, Any] = {
        "tm_helix_count": canon.tm_helix_count,
        "n_terminal_orientation": canon.n_terminal_orientation,
        "c_terminal_orientation": canon.c_terminal_orientation,
        "ecd_length_residues": canon.ecd_length_residues,
        "icd_length_residues": canon.icd_length_residues,
        "signal_peptide_length": canon.signal_peptide_length,
        "paralog_count": len(features.paralogs),
        "top_paralogs": [
            {"symbol": p.paralog_symbol, "ecd_pct_identity": p.ecd_pct_identity}
            for p in top
        ],
        # Aggregate ortholog counts — Compara can return one-to-many per
        # species; canonical symbol + identity below cover the headline
        # cross-species translatability, the count surfaces multi-isoform
        # / multi-paralog mappings the planner may want to flag.
        "mouse_ortholog_count": len(features.orthologs.mouse),
        "cyno_ortholog_count": len(features.orthologs.cynomolgus),
        "mouse_ortholog_symbol": mouse.ortholog_symbol if mouse else None,
        "mouse_ortholog_ecd_pct_identity": (
            mouse.ecd_pct_identity_to_human_canonical if mouse else None
        ),
        "cyno_ortholog_symbol": cyno.ortholog_symbol if cyno else None,
        "cyno_ortholog_ecd_pct_identity": (
            cyno.ecd_pct_identity_to_human_canonical if cyno else None
        ),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _summarize_triage_for_planner(record: TriageRecord) -> str:
    """Compact JSON summary of the triage prior handed to A1/A2
    planners + the synthesizer.

    Carries exactly the five fields the design specifies (PR #23
    §1110-1116): verdict + reason taxonomy + verdict_reasoning prose
    + key_uncertainty + confidence. The LLM weights the prior on
    confidence + reasoning, not on model identity.

    ``record.provenance`` (the D1 row's model + prompt_variant +
    run_id + replicate) is intentionally NOT emitted — it stays on
    the TriageRecord for audit / logging / future ensemble work but
    is withheld from the prompt to keep the LLM's calibration
    grounded in the prose, not in heuristics about which model ran it.
    """

    payload: dict[str, Any] = {
        "verdict": record.verdict,
        "reason": record.reason,
        "verdict_reasoning": record.verdict_reasoning,
        "key_uncertainty": record.key_uncertainty,
        "confidence": record.confidence,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _build_gene_context(
    gene: str, *, http: CachedHTTP, retraction_index: RetractionIndex
) -> GeneContext:
    """Resolve gene + pull UniProt + DB-vote context for the planner.

    Accepts three input shapes (mirrors ``surfaceome_v1.orchestrator``'s
    canonical dispatch, post-resolver-v3): a UniProt accession routes
    through ``resolve``; an ``HGNC:N`` ID goes straight to
    ``resolve_by_hgnc_id``; a bare gene symbol is looked up in D1's
    ``gene_identifier`` table and then resolved by HGNC ID. The legacy
    symbol-through-``resolve`` path was removed in resolver v3 because it
    silently returned wrong-protein context for ~0.2% of human genes
    (COX1 / WAS class). See CLAUDE.md 'Gene identifier resolution'.
    """

    raw = gene.strip()
    if looks_like_uniprot_acc(raw):
        bundle = resolve(symbol_or_acc=raw, http=http)
    elif raw.upper().startswith("HGNC:"):
        bundle = resolve_by_hgnc_id(raw, http=http)
    else:
        hgnc_id = _hgnc_id_for_symbol(raw)
        if hgnc_id is None:
            raise LookupError(
                f"unknown gene symbol {raw!r}: not found in D1 "
                "gene_identifier.hgnc_symbol or cohort_symbol. If this is "
                "a recently-added gene, rerun "
                "scripts/build/build_gene_identifier_table.py to refresh the "
                "cache; if it's a typo or non-human gene, pass a UniProt "
                "accession or HGNC ID directly."
            )
        bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    if not bundle.uniprot_acc:
        raise LookupError(f"could not resolve {gene} to a UniProt accession")

    uniprot = uniprot_summary(uniprot_acc=bundle.uniprot_acc, http=http)
    db = db_panel(uniprot_acc=bundle.uniprot_acc, http=http)

    # DeepTMHMM topology + Compara paralog + cross-species ortholog ECD
    # identity from public D1 (uploaded by PR #29's
    # ``scripts/build/run_topology_sweep.py``). Folded into a compact summary
    # the A1/A2 planners can scan inline. Failures here are non-fatal —
    # log a warning and continue with UniProt-only planning (the
    # planner prompts treat the missing block as "no deterministic data
    # available"). Local import keeps the D1 dependency out of import
    # time for code paths that don't run the planner.
    deterministic_summary: str | None
    n_tmh: int | None = None
    ecd_aa: int | None = None
    try:
        from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
            fetch_deterministic_features,
        )

        features = fetch_deterministic_features(bundle.uniprot_acc)
        deterministic_summary = _summarize_deterministic_for_planner(features)
        # Real topology only — the D1-miss placeholder (tool_version
        # "placeholder-no-d1-row", which carries a synthetic tm_helix_count=0)
        # must read as "topology unknown" so the kickoff fires its
        # membrane-gated axes recall-biased instead of treating the
        # placeholder as a real TM=0 (non-membrane) negative.
        canon = features.canonical_topology
        if canon.tool_version != "placeholder-no-d1-row":
            n_tmh = canon.tm_helix_count
            ecd_aa = canon.ecd_length_residues
    except Exception as exc:  # noqa: BLE001 — keep planning even if D1 is down
        logger.warning(
            "deterministic-features D1 fetch failed for %s (%s); "
            "planner will run without the deterministic block",
            bundle.uniprot_acc,
            exc,
        )
        deterministic_summary = None

    # Persisted ``TriageRecord`` for this gene (verdict + verdict_reasoning
    # + reason taxonomy + key_uncertainty + confidence). Folded into a
    # compact JSON the planner reads as a prior. Missing record (no
    # triage was ever run for this gene) → ``None`` and the planner
    # prompt omits the block. Implements PR #23 design doc §1110-1116.
    triage_summary: str | None
    try:
        from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
            _load_triage_record,
        )

        triage_record = _load_triage_record(bundle.hgnc_symbol)
        triage_summary = (
            _summarize_triage_for_planner(triage_record)
            if triage_record is not None
            else None
        )
    except Exception as exc:  # noqa: BLE001 — keep planning even if triage load fails
        logger.warning(
            "triage record load failed for %s (%s); "
            "planner will run without the triage prior",
            bundle.hgnc_symbol,
            exc,
        )
        triage_summary = None

    return GeneContext(
        gene=gene,
        bundle=bundle,
        uniprot_summary_json=uniprot.model_dump_json(indent=2),
        db_panel_json=db.model_dump_json(indent=2),
        deterministic_summary_json=deterministic_summary,
        triage_summary_json=triage_summary,
        n_tmh=n_tmh,
        ecd_aa=ecd_aa,
    )


def _hgnc_id_for_symbol(symbol: str) -> str | None:
    """Look up the HGNC ID for a gene symbol from D1 ``gene_identifier``.

    Tries ``hgnc_symbol`` first (HGNC's official symbol) then
    ``cohort_symbol`` (the symbol the M1 cohort row used). Returns
    ``None`` for an unknown symbol so the caller can raise a
    domain-flavored ``LookupError``.
    """

    # Local import keeps the D1 dependency out of import time for code
    # paths that never need symbol lookup.
    from accessible_surfaceome.cloud.d1_client import D1Client, D1Error

    try:
        d1 = D1Client()
    except D1Error:
        raise LookupError(
            f"cannot resolve symbol {symbol!r} without D1 credentials. "
            "Either set CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN + "
            "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID, or pass a UniProt "
            "accession (e.g. Q9UBP8) / HGNC ID (e.g. HGNC:4526) directly."
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
# Step 1 — planner
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any] | None:
    matches = _FENCED_JSON_RE.findall(text)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def _call_with_repair(
    client: Anthropic,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    max_tokens: int,
    usage_sink: list[UsageRecord],
    label: str,
) -> tuple[BaseModel | None, dict[str, Any] | None, str]:
    """Repair-looped messages.create until the emitted JSON validates
    against ``schema``, capped at ``MAX_REPAIRS`` retries. Returns the
    parsed model (or None), the raw JSON (or None), and the final text.
    """

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    validation_error: str | None = None
    parsed: BaseModel | None = None
    raw_json: dict[str, Any] | None = None
    final_text = ""
    # Cache the (static, focus-specific) selector system prompt — mirrors the
    # synthesizer's cached_system pattern. Cuts cost on repair-loop retries and
    # across genes in a sweep; byte-identical output (cache_control is a
    # transport/billing directive, not a generation change).
    cached_sys = cached_system(system_prompt)

    for attempt in range(MAX_REPAIRS + 1):
        resp = messages_create_with_backoff(
            client,
            model=model,
            max_tokens=max_tokens,
            system=cast("Any", cached_sys),
            messages=cast("Any", messages),
        )
        usage_sink.append(record_from_response(resp.usage, model, response=resp))
        final_text = "\n".join(
            b.text for b in resp.content if isinstance(b, TextBlock)
        ).strip()
        raw_json = _extract_json(final_text)
        if raw_json is None:
            validation_error = "no fenced JSON block in model output"
        else:
            try:
                parsed = schema.model_validate(raw_json)
                return parsed, raw_json, final_text
            except ValidationError as exc:
                validation_error = str(exc)
        logger.info(
            "%s repair %d/%d — %s", label, attempt + 1, MAX_REPAIRS, validation_error[:200]
        )
        messages.append({"role": "assistant", "content": final_text})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your JSON failed schema validation:\n\n{validation_error[:1500]}\n\n"
                    "Emit a corrected JSON object as one fenced ```json block. "
                    "Respect the schema exactly — no extra fields."
                ),
            }
        )
    logger.warning("%s validation failed after %d repairs", label, MAX_REPAIRS)
    return None, raw_json, final_text


# ---------------------------------------------------------------------------
# Step 2 — execute the search plan
# ---------------------------------------------------------------------------


def _execute_plan(
    plan: SearchPlan,
    *,
    context: GeneContext,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    timing: TimingRecorder | None = None,
    timing_phase: str = "plan_trim_select",
) -> tuple[
    dict[str, EvidenceClaimDraft],
    list[SearchLogEntry],
    dict[str, list[EvidenceClaimDraft]],
    dict[int, Paper],
]:
    """Dispatch each search; collect drafts into a global pool keyed by
    ``clip_id``. Returns (pool, search_log, clips_by_source, discovered_papers).

    ``discovered_papers`` is a {pmid: Paper} dict populated from
    ``gene2pubmed`` and ``topic_search`` results — papers the planner
    surfaced but didn't fetch the body of. The selector reads this list
    to decide whether to iterate with ``fetch_abstract`` /
    ``fetch_fulltext`` calls for the most promising PMIDs.
    """

    pool: dict[str, EvidenceClaimDraft] = {}
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    discovered_papers: dict[int, Paper] = {}
    search_log: list[SearchLogEntry] = []
    bundle = context.bundle
    acc = bundle.uniprot_acc

    for req in plan.searches:
        t0 = time.time()
        started_at = datetime.now(UTC)
        n_drafts = 0
        n_papers = 0
        err: str | None = None
        params: dict[str, Any] = {}
        _search_step_name = (
            f"search:{req.tool}"
            if req.tool == "evidence_retrieval"
            else f"search:{req.tool}:{getattr(req, 'mode', '?')}"
        )
        try:
            if req.tool == "evidence_retrieval":
                params = {"category": req.category, "uniprot_acc": acc}
                if req.category is None:
                    raise ValueError("evidence_retrieval requires category")
                pack = evidence_retrieval(
                    uniprot_acc=acc,
                    category=req.category,
                    http=http,
                    retraction_index=retraction_index,
                    discover_only=True,
                )
                # discover_only=True: bodies aren't fetched here. Any
                # drafts the pack carries are from the hpa_ihc path
                # (synthetic curated data, not paper bodies) and still
                # belong in the pool.
                for draft in pack.evidence_claim_drafts:
                    _add_to_pool(draft, pool, clips_by_source)
                    n_drafts += 1
                # Merge category-discovery papers into the candidate
                # inventory so triage sees them alongside gene_literature
                # discovery results.
                for paper in pack.papers:
                    if paper.pmid:
                        discovered_papers.setdefault(paper.pmid, paper)
                n_papers = len(pack.papers)
            elif req.tool == "gene_literature":
                params = {"mode": req.mode}
                if req.mode == "gene2pubmed":
                    res = gene_literature(
                        mode="gene2pubmed",
                        uniprot_acc=acc,
                        hgnc_symbol=bundle.hgnc_symbol,
                        ncbi_gene_id=bundle.ncbi_gene_id,
                        aliases=bundle.aliases,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    # gene2pubmed returns LiteraturePack (no drafts; just paper list).
                    # Each Paper carries title + abstract pre-populated from the
                    # EuropePMC search hits — surface them as discovered_papers
                    # so the selector can request fetch_abstract on iteration.
                    assert isinstance(res, LiteraturePack)
                    for paper in res.papers:
                        discovered_papers.setdefault(paper.pmid, paper)
                    n_papers = len(res.papers)
                elif req.mode == "topic_search":
                    if not req.anchors:
                        raise ValueError("topic_search requires anchors")
                    params["anchors"] = list(req.anchors)
                    res = gene_literature(
                        mode="topic_search",
                        uniprot_acc=acc,
                        hgnc_symbol=bundle.hgnc_symbol,
                        ncbi_gene_id=bundle.ncbi_gene_id,
                        aliases=bundle.aliases,
                        previous_symbols=bundle.previous_symbols,
                        topic_anchors=list(req.anchors),
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(res, LiteraturePack)
                    for paper in res.papers:
                        discovered_papers.setdefault(paper.pmid, paper)
                    n_papers = len(res.papers)
                elif req.mode == "recent_corpus":
                    res = gene_literature(
                        mode="recent_corpus",
                        uniprot_acc=acc,
                        hgnc_symbol=bundle.hgnc_symbol,
                        ncbi_gene_id=bundle.ncbi_gene_id,
                        aliases=bundle.aliases,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(res, LiteraturePack)
                    for paper in res.papers:
                        discovered_papers.setdefault(paper.pmid, paper)
                    n_papers = len(res.papers)
                elif req.mode == "fetch_abstract":
                    if not req.pmid:
                        raise ValueError("fetch_abstract requires pmid")
                    params["pmid"] = req.pmid
                    paper = gene_literature(
                        mode="fetch_abstract",
                        pmid=req.pmid,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(paper, Paper)
                    for draft in paper.evidence_claim_drafts:
                        _add_to_pool(draft, pool, clips_by_source)
                        n_drafts += 1
                    n_papers = 1
                elif req.mode == "fetch_fulltext":
                    if not req.pmcid:
                        raise ValueError("fetch_fulltext requires pmcid")
                    params["pmcid"] = req.pmcid
                    paper = gene_literature(
                        mode="fetch_fulltext",
                        pmcid=req.pmcid,
                        http=http,
                        retraction_index=retraction_index,
                    )
                    assert isinstance(paper, Paper)
                    for draft in paper.evidence_claim_drafts:
                        _add_to_pool(draft, pool, clips_by_source)
                        n_drafts += 1
                    n_papers = 1
                else:
                    raise ValueError(f"unknown gene_literature mode: {req.mode!r}")
            else:
                raise ValueError(f"unknown tool: {req.tool!r}")
        except Exception as exc:  # noqa: BLE001 — search-level robustness
            err = f"{type(exc).__name__}: {exc}"
            logger.warning("search failed: %s %s → %s", req.tool, params, err)
        elapsed = time.time() - t0
        search_log.append(
            SearchLogEntry(
                tool=req.tool,
                params=params,
                intent=req.intent,
                n_drafts=n_drafts,
                n_papers=n_papers,
                elapsed_s=round(elapsed, 2),
                error=err,
            )
        )
        if timing is not None:
            timing.add(
                StepTiming(
                    step_name=_search_step_name,
                    phase=timing_phase,
                    started_at=started_at.isoformat().replace("+00:00", "Z"),
                    elapsed_s=round(elapsed, 3),
                    n_items=n_drafts if n_drafts else n_papers,
                )
            )

    return pool, search_log, dict(clips_by_source), discovered_papers


def _add_to_pool(
    draft: EvidenceClaimDraft,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
) -> None:
    """Insert draft into the pool with a globally-unique clip_id.

    Content-dedup within source: when the same paper is extracted by
    multiple evidence_retrieval categories (e.g., surface_biotinylation +
    mass_spec_surfaceome both pull a LUX-MS paper), each call's ``seq``
    counter restarts, so identical sentences get different clip_ids on
    the second call. Without a content check, those duplicates inflate
    the Haiku trim prompt with redundant text. Compare against existing
    quotes for the same source_id before assigning a clip_id.
    """

    normalized = normalize_for_quote_matching(draft.quote)
    for existing in by_source.get(draft.source_id, []):
        if normalize_for_quote_matching(existing.quote) == normalized:
            return

    clip_id = draft.suggested_evidence_id
    if clip_id in pool:
        # Same id but different content — suffix and keep both.
        k = 2
        while f"{clip_id}_{k}" in pool:
            k += 1
        clip_id = f"{clip_id}_{k}"
    redrafted = draft.model_copy(update={"suggested_evidence_id": clip_id})
    pool[clip_id] = redrafted
    by_source[redrafted.source_id].append(redrafted)


# ---------------------------------------------------------------------------
# Step 3 — Haiku trim per paper
# ---------------------------------------------------------------------------


def _format_clips_for_trim(clips: list[EvidenceClaimDraft]) -> str:
    lines: list[str] = []
    for c in clips:
        preview = c.quote if len(c.quote) <= TRIM_PREVIEW_CHARS else c.quote[:TRIM_PREVIEW_CHARS] + " […]"
        meta = f"section={c.section}, score={c.score:.1f}, hallmark={c.hallmark_phrase}"
        lines.append(f"--- {c.suggested_evidence_id} ({meta}) ---\n{preview}")
    return "\n\n".join(lines)


@dataclass
class _TrimOutcome:
    """One paper's trim result + token usage + timing row, returned by
    the per-paper worker so the orchestrator merges them on the main
    thread (avoids shared mutation inside the worker)."""

    source_id: str
    response: TrimResponse
    usage_record: UsageRecord | None
    timing_row: StepTiming | None


def _trim_one_paper(
    client: Anthropic,
    *,
    source_id: str,
    clips: list[EvidenceClaimDraft],
    gene: str,
    schema_str: str,
    trim_prompt_template: str,
    timing_phase: str,
    timing_iteration: int,
    emit_timing: bool,
) -> _TrimOutcome:
    """Worker: trim one paper's clip pool via a single Haiku call.

    Pure: reads no shared mutable state, writes only to the returned
    ``_TrimOutcome``. The orchestrator merges the outcome into the
    shared ``usage_sink`` / ``TimingRecorder`` / results dict on the
    main thread.
    """
    bounded = sorted(clips, key=lambda c: c.score, reverse=True)[
        :MAX_CLIPS_PER_TRIM_CALL
    ]
    # Caching path: split the trim template into a gene-agnostic cached
    # system block + a per-paper user template. Each unique template gets
    # split once (cached in _TRIM_TEMPLATE_CACHE). Per-call we only format
    # the small user template (paper_id + clips); the rules block is
    # served from Anthropic's prompt cache. ~88% savings on the prefix
    # cost for the 30-100 trim calls per gene.
    cached_system_text, user_template = _split_trim_template(
        trim_prompt_template, schema_str
    )
    user_msg = (
        f"Target gene: {gene}\n\n"
        + user_template.format(
            gene=gene,
            paper_id=source_id,
            n_clips=len(bounded),
            numbered_clips=_format_clips_for_trim(bounded),
            schema=schema_str,
        )
    )
    started_at = datetime.now(UTC)
    t0 = time.perf_counter()
    try:
        if cached_system_text:
            resp = messages_create_with_backoff(
                client,
                model=HAIKU_MODEL,
                max_tokens=MAX_TOKENS_TRIM,
                system=cast("Any", cached_system(cached_system_text)),
                messages=cast("Any", [{"role": "user", "content": user_msg}]),
            )
        else:
            # Fallback (no '## Output' header found — old prompt shape).
            legacy_prompt = trim_prompt_template.format(
                gene=gene,
                paper_id=source_id,
                n_clips=len(bounded),
                numbered_clips=_format_clips_for_trim(bounded),
                schema=schema_str,
            )
            resp = messages_create_with_backoff(
                client,
                model=HAIKU_MODEL,
                max_tokens=MAX_TOKENS_TRIM,
                messages=cast(
                    "Any", [{"role": "user", "content": legacy_prompt}]
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("trim call failed for %s: %s", source_id, exc)
        timing_row = (
            StepTiming(
                step_name=f"trim:iter{timing_iteration}:{source_id}",
                phase=timing_phase,
                started_at=started_at.isoformat().replace("+00:00", "Z"),
                elapsed_s=round(time.perf_counter() - t0, 3),
                n_items=len(bounded),
                model=HAIKU_PRICING_KEY,
            )
            if emit_timing
            else None
        )
        return _TrimOutcome(
            source_id=source_id,
            response=TrimResponse(paper_id=source_id, kept=[]),
            usage_record=None,
            timing_row=timing_row,
        )

    rec = record_from_response(resp.usage, HAIKU_PRICING_KEY, response=resp)
    elapsed = round(time.perf_counter() - t0, 3)
    timing_row = (
        StepTiming(
            step_name=f"trim:iter{timing_iteration}:{source_id}",
            phase=timing_phase,
            started_at=started_at.isoformat().replace("+00:00", "Z"),
            elapsed_s=elapsed,
            n_items=len(bounded),
            model=HAIKU_PRICING_KEY,
            input_tokens=rec.input_tokens,
            output_tokens=rec.output_tokens,
            cache_creation_input_tokens=rec.cache_creation_input_tokens,
            cache_read_input_tokens=rec.cache_read_input_tokens,
            cost_usd=round(rec.cost_usd, 6),
        )
        if emit_timing
        else None
    )

    text = "\n".join(
        b.text for b in resp.content if isinstance(b, TextBlock)
    ).strip()
    raw = _extract_json(text)
    if raw is None:
        logger.warning(
            "trim for %s emitted no JSON; treating as no keeps", source_id
        )
        response = TrimResponse(paper_id=source_id, kept=[])
    else:
        try:
            tr = TrimResponse.model_validate(raw)
            # The model sometimes echoes the paper_id; normalize it.
            tr = tr.model_copy(update={"paper_id": source_id})
            # Filter out kept ids that aren't in our submitted clip set —
            # the model occasionally hallucinates ids.
            known_ids = {c.suggested_evidence_id for c in bounded}
            tr = tr.model_copy(
                update={"kept": [k for k in tr.kept if k.clip_id in known_ids]}
            )
            response = tr
        except ValidationError as exc:
            logger.warning("trim validation failed for %s: %s", source_id, exc)
            response = TrimResponse(paper_id=source_id, kept=[])

    return _TrimOutcome(
        source_id=source_id,
        response=response,
        usage_record=rec,
        timing_row=timing_row,
    )


def _run_trim(
    client: Anthropic,
    *,
    clips_by_source: dict[str, list[EvidenceClaimDraft]],
    gene: str,
    usage_sink: list[UsageRecord],
    trim_prompt_path: Path,
    timing: TimingRecorder | None = None,
    timing_phase: str = "plan_trim_select",
    timing_iteration: int = 0,
) -> dict[str, TrimResponse]:
    """One Haiku call per paper, fanned out across a thread pool.

    Each paper's trim is independent (its own prompt, its own response,
    its own validation slot in the result dict). Concurrency is capped
    at :data:`TRIM_CONCURRENCY` to stay well under per-org Anthropic
    rate limits even when a gene pulls 60+ papers; raising the cap
    further mostly trades rate-limit headroom for marginal latency.

    ``trim_prompt_path`` loads the trim system prompt template (must
    contain the placeholders ``{gene}`` ``{paper_id}`` ``{n_clips}``
    ``{numbered_clips}`` ``{schema}``). Defaults to the generic A1+A2
    template; per-agent paths narrow the trim focus.
    """

    schema_str = json.dumps(TrimResponse.model_json_schema(), indent=2, sort_keys=True)
    trim_prompt_template = trim_prompt_path.read_text()
    results: dict[str, TrimResponse] = {}
    non_empty = [(sid, clips) for sid, clips in clips_by_source.items() if clips]
    if not non_empty:
        return results

    emit_timing = timing is not None

    with ThreadPoolExecutor(max_workers=TRIM_CONCURRENCY) as executor:
        futures = [
            executor.submit(
                _trim_one_paper,
                client,
                source_id=sid,
                clips=clips,
                gene=gene,
                schema_str=schema_str,
                trim_prompt_template=trim_prompt_template,
                timing_phase=timing_phase,
                timing_iteration=timing_iteration,
                emit_timing=emit_timing,
            )
            for sid, clips in non_empty
        ]
        for fut in futures:
            outcome = fut.result()
            if outcome.usage_record is not None:
                usage_sink.append(outcome.usage_record)
            if outcome.timing_row is not None and timing is not None:
                timing.add(outcome.timing_row)
            results[outcome.source_id] = outcome.response

    return results


# ---------------------------------------------------------------------------
# Step 4 — Sonnet selector
# ---------------------------------------------------------------------------


def _format_menu_for_selector(
    pool: dict[str, EvidenceClaimDraft], trim_results: dict[str, TrimResponse]
) -> str:
    """Render kept clips as a single markdown menu the selector reads."""

    blocks: list[str] = []
    for source_id, tr in sorted(trim_results.items()):
        if not tr.kept:
            continue
        blocks.append(f"## {source_id}\n")
        for kept in tr.kept:
            draft = pool.get(kept.clip_id)
            if draft is None:
                continue
            reason = f"  _Haiku reason:_ {kept.reason}" if kept.reason else ""
            blocks.append(
                f"### clip_id: `{kept.clip_id}`\n"
                f"_section:_ {draft.section} · _hallmark:_ {draft.hallmark_phrase}\n"
                f"{reason}\n\n"
                f"> {draft.quote}\n"
            )
    return "\n".join(blocks)


def _run_selector(
    client: Anthropic,
    *,
    context: GeneContext,
    menu_markdown: str,
    n_kept: int,
    usage_sink: list[UsageRecord],
    select_prompt_path: Path,
    timing: TimingRecorder | None = None,
    timing_phase: str = "plan_trim_select",
) -> SelectionResponse | None:
    system_prompt = select_prompt_path.read_text()
    schema_str = json.dumps(SelectionResponse.model_json_schema(), indent=2, sort_keys=True)
    deterministic_block = ""
    if context.deterministic_summary_json:
        deterministic_block = (
            "Deterministic inputs (DeepTMHMM topology + Compara paralogs + "
            "cross-species ortholog ECD identity, for context):\n"
            f"```json\n{context.deterministic_summary_json}\n```\n\n"
        )
    triage_block = ""
    if context.triage_summary_json:
        triage_block = (
            "Triage prior (from the genome-wide Haiku surface_triage agent, "
            "treat as a prior to confirm or refute):\n"
            f"```json\n{context.triage_summary_json}\n```\n\n"
        )
    user_prompt = (
        f"# Gene: {context.gene}\n\n"
        f"UniProt summary (for context):\n```json\n{context.uniprot_summary_json}\n```\n\n"
        f"DB vote panel (5-database surface vote, for context):\n"
        f"```json\n{context.db_panel_json}\n```\n\n"
        f"{deterministic_block}"
        f"{triage_block}"
        f"## Trimmed clip menu ({n_kept} clips across multiple sources)\n\n"
        f"{menu_markdown}\n\n"
        "Pick the clips that should become evidence rows. Use the clip_id as it "
        "appears above. Emit one fenced ```json block matching this "
        "SelectionResponse schema:\n\n"
        f"```json\n{schema_str}\n```\n"
    )
    if timing is None:
        parsed, _, _ = _call_with_repair(
            client,
            model=SONNET_MODEL,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=SelectionResponse,
            max_tokens=MAX_TOKENS_SELECT,
            usage_sink=usage_sink,
            label="selector",
        )
    else:
        call_sink: list[UsageRecord] = []
        with timing.step(
            "selector",
            phase=timing_phase,
            n_items=n_kept,
            model=SONNET_MODEL,
        ) as h:
            parsed, _, _ = _call_with_repair(
                client,
                model=SONNET_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=SelectionResponse,
                max_tokens=MAX_TOKENS_SELECT,
                usage_sink=call_sink,
                label="selector",
            )
            h.set_usage(call_sink, model=SONNET_MODEL)
        usage_sink.extend(call_sink)
    return parsed if isinstance(parsed, SelectionResponse) else None


# ---------------------------------------------------------------------------
# Step 5 — promote selections → EvidenceClaim records
# ---------------------------------------------------------------------------


def _normalize_clip_id(clip_id: str) -> str:
    """Normalize a clip_id for tolerant matching.

    Lowercases, drops non-alphanumerics, and strips ``pmid`` / ``pmc``
    type tokens. This collapses the one mangling the selector reliably
    introduces: the menu renders a source header ``PMID:21444918`` above
    a clip ``draft_21444918_abstract_02`` (bare digits, no type token,
    because the pool keys PMID sources by number), and the model
    "regularizes" the clip by re-inserting the prefix it saw in the
    header → ``draft_PMID21444918_abstract_02``. Both normalize to
    ``draft21444918abstract02``. PMC clips already carry ``PMC`` in the
    bare id so they round-trip without this, but stripping the token is
    harmless there too.
    """

    s = re.sub(r"[^a-z0-9]", "", clip_id.lower())
    return re.sub(r"pmid|pmc", "", s)


def _promote_selections(
    selection_response: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    evidence_id_prefix: str = "pts_evi_",
) -> tuple[list[EvidenceClaim], list[str]]:
    """Build EvidenceClaim records from selections. Quote auto-filled from
    the pool's verbatim text — agent never typed it. Returns (claims, warnings).

    ``evidence_id_prefix`` stamps the generated ``evidence_id`` values
    (``{prefix}NN``). The default ``pts_evi_`` preserves the single-agent
    MVP path; per-agent paths use ``a1_evi_`` / ``a2_evi_`` so downstream
    block builders' ``_check_claim_id_prefix`` validators pass.

    On an exact clip_id miss, falls back to a normalized lookup that
    tolerates the selector's PMID/PMC prefix-regularization, accepting
    the recovery only when it resolves to a *single* pool clip (an
    ambiguous normalized key keeps the drop + warning).
    """

    # Build the normalized index lazily; only consulted on exact miss.
    norm_index: dict[str, list[str]] = defaultdict(list)
    for cid in pool:
        norm_index[_normalize_clip_id(cid)].append(cid)

    claims: list[EvidenceClaim] = []
    warnings: list[str] = []
    seq = 1
    for sel in selection_response.selections:
        draft = pool.get(sel.clip_id)
        if draft is None:
            candidates = norm_index.get(_normalize_clip_id(sel.clip_id), [])
            if len(candidates) == 1:
                draft = pool[candidates[0]]
            else:
                detail = (
                    f"{len(candidates)} normalized matches"
                    if candidates
                    else "no match"
                )
                warnings.append(
                    f"selector picked unknown clip_id={sel.clip_id!r} "
                    f"({detail}); skipping"
                )
                continue
        claim = EvidenceClaim(
            evidence_id=f"{evidence_id_prefix}{seq:02d}",
            claim=sel.claim,
            claim_type=sel.claim_type,
            direction=sel.direction,
            evidence_type=sel.evidence_type,
            evidence_tier=sel.evidence_tier,
            confidence=sel.confidence,
            assay_context=sel.assay_context,
            source_id=draft.source_id,
            quote=draft.quote,  # verbatim, copied from the pool
            section=draft.section,
            figure_or_table_id=draft.figure_or_table_id,
        )
        claims.append(claim)
        seq += 1
    return claims, warnings


# ---------------------------------------------------------------------------
# End-to-end driver
# ---------------------------------------------------------------------------


def _resolve_focus_prompts(
    agent_focus: AgentFocus,
) -> tuple[Path, Path, str]:
    """Map agent_focus → (trim_prompt_path, select_prompt_path, evi_prefix).

    Centralized so an unknown focus fails fast with a clear error before
    any model call. The legacy unified-ledger (``agent_focus=None``)
    path was retired with the ``trim_system.md`` / ``select_system.md``
    prompts — production runs both A1 and A2 via the dual driver.
    """

    if agent_focus == "a1":
        return (
            A1_TRIM_PROMPT_PATH,
            A1_SELECT_PROMPT_PATH,
            _EVIDENCE_ID_PREFIX["a1"],
        )
    if agent_focus == "a2":
        return (
            A2_TRIM_PROMPT_PATH,
            A2_SELECT_PROMPT_PATH,
            _EVIDENCE_ID_PREFIX["a2"],
        )
    raise ValueError(
        f"unknown agent_focus={agent_focus!r}; expected 'a1' or 'a2'"
    )


def run_plan_trim_select(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    retraction_index: RetractionIndex | None = None,
    agent_focus: AgentFocus,
    timing: TimingRecorder | None = None,
    enable_pretrim_filter: bool = True,
    triage_cache: dict[str, Any] | None = None,
) -> PlanTrimSelectResult:
    """Run plan → trim → select for one gene. Returns the full audit result.

    ``agent_focus`` selects the trim + select prompt pair and the
    ``evidence_id`` prefix:

    * ``"a1"`` — surface-evidence focus (``a1_trim_system.md`` +
      ``a1_select_system.md``, ``a1_evi_`` prefix). Selects clips that
      feed `surface_evidence` block builders downstream.
    * ``"a2"`` — biological-context focus (``a2_trim_system.md`` +
      ``a2_select_system.md``, ``a2_evi_`` prefix). Selects clips that
      feed `biological_context` block builders downstream.

    The legacy unified-ledger (``agent_focus=None``) path was retired
    along with the ``trim_system.md`` / ``select_system.md`` prompts.
    Every caller must declare a focus.

    The kickoff stage is *not* per-focus in its *search set* — both A1
    and A2 discover into the same shared candidate inventory. The
    per-focus split happens at trim + select (and at the ``evidence_id``
    prefix). Phase 1's sequential-dual driver
    (``run_plan_trim_select_dual``) calls this entry point twice (once
    with ``agent_focus="a1"``, once with ``"a2"``) over the same warmed
    http cache so the discovery + triage fetches cache-hit on the second
    pass and only the trim+select diverges per agent.
    """

    t0 = time.time()
    client = client or get_client()
    own_http = http is None
    http = http or open_default_client()
    retraction = retraction_index or _empty_retraction_index()

    # Resolve the per-focus prompt pair + evidence-id prefix up front so a
    # typo or missing-prompt-file failure aborts before any model call.
    (
        trim_prompt_path,
        select_prompt_path,
        evidence_id_prefix,
    ) = _resolve_focus_prompts(agent_focus)
    timing_phase = f"plan_trim_select_{agent_focus}"
    # Track the per-run timing slice so the result's ``timing`` field
    # contains *only* this run's rows (the recorder may carry rows from
    # the sibling A1/A2 run when called via the dual driver).
    timing_start_index = len(timing.entries) if timing is not None else 0

    triage_usage: list[UsageRecord] = []
    trim_usage: list[UsageRecord] = []
    select_usage: list[UsageRecord] = []

    result = PlanTrimSelectResult(
        gene=gene,
        bundle=None,
        plan=None,
        selection_response=None,
        agent_focus=agent_focus,
    )

    # Cumulative state across plan iterations.
    pool: dict[str, EvidenceClaimDraft] = {}
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    cumulative_search_log: list[SearchLogEntry] = []
    cumulative_discovered: dict[int, Paper] = {}
    sel_resp: SelectionResponse | None = None
    # Paper source_ids already routed through triage, so later iterations
    # triage only newly-discovered papers (each paper triaged exactly once).
    triaged_ids: set[str] = set()
    # Per-iteration pre-trim filter audits. Captured whether or not the
    # filter is enabled; under shadow mode (default), the audit records what
    # WOULD be dropped without actually dropping. Routed onto the final
    # result so callers can persist + validate before flipping the default.
    _pretrim_audits: list[Any] = []

    try:
        # Step 0 — gene context (once per run)
        context = _build_gene_context(gene, http=http, retraction_index=retraction)
        result.bundle = context.bundle
        logger.info("gene context built: %s → %s", gene, context.bundle.uniprot_acc)

        # Step 1 — deterministic kickoff plan (no LLM planner). The fixed
        # per-focus search set reproduces the retired planner's average
        # coverage; canonical topology counts gate the membrane-specific
        # standing axes (tox panel always; surface-reachability when
        # membrane+ECD or topology unknown).
        initial_plan = build_kickoff(agent_focus, context.n_tmh, context.ecd_aa)
        result.plan = initial_plan
        logger.info("kickoff emitted %d searches", len(initial_plan.searches))

        # Single-pass execute→triage→trim→select. The loop runs once
        # (MAX_PLAN_ITERATIONS=1); the structure is retained so iteration
        # could be reintroduced behind the constant without a rewrite.
        current_plan: SearchPlan | None = initial_plan
        for iteration in range(MAX_PLAN_ITERATIONS):
            if current_plan is None or not current_plan.searches:
                break

            # Step 2 — execute the kickoff searches, merge into the pool.
            # _execute_plan returns its own fresh pool; we merge new drafts
            # via _add_to_pool for content-dedup.
            iter_pool, iter_log, iter_by_source, iter_discovered = _execute_plan(
                current_plan,
                context=context,
                http=http,
                retraction_index=retraction,
                timing=timing,
                timing_phase=timing_phase,
            )
            n_new_drafts = 0
            for draft in iter_pool.values():
                if draft.suggested_evidence_id in pool:
                    continue
                pool[draft.suggested_evidence_id] = draft
                clips_by_source[draft.source_id].append(draft)
                n_new_drafts += 1
            cumulative_search_log.extend(iter_log)
            for pmid, paper in iter_discovered.items():
                cumulative_discovered.setdefault(pmid, paper)
            logger.info(
                "iteration %d: executed %d searches → %d new drafts (pool now %d across %d papers)",
                iteration,
                len(current_plan.searches),
                n_new_drafts,
                len(pool),
                len(clips_by_source),
            )

            # Step 2b — triage newly-discovered papers (incremental). Each
            # discovered paper is routed through one Haiku abstract-triage
            # call exactly once across all iterations. keep_abstract adds
            # abstract preview clip(s); worth_fetching fetches the body and
            # adds body clips; discard drops it. Papers already in the body
            # pool (evidence_retrieval / a prior fetch) or lacking an
            # abstract are marked seen and skipped.
            new_papers: list[Paper] = []
            papers_by_id: dict[str, Paper] = {}
            for paper in cumulative_discovered.values():
                sid = paper_source_id(paper)
                if sid in triaged_ids:
                    continue
                if sid in clips_by_source:
                    triaged_ids.add(sid)  # body already in pool
                    continue
                if not (paper.abstract or "").strip():
                    triaged_ids.add(sid)  # nothing to triage
                    continue
                new_papers.append(paper)
                papers_by_id[sid] = paper

            if new_papers:
                # Pre-trim filter: drop high-waste papers (reviews in low-quality
                # venues, drug-discovery summaries, broad atlases) BEFORE the
                # Haiku abstract triage runs. Activates only for heavy-literature
                # candidate pools (>=50 papers); thin-lit genes pass through
                # unchanged. The audit is collected regardless of activation so
                # the operator can validate filter behaviour offline.
                from accessible_surfaceome.agents.plan_trim_select.pretrim_filter import (
                    pretrim_filter,
                )

                filtered_papers, pretrim_audit = pretrim_filter(
                    new_papers, enable=enable_pretrim_filter
                )
                if (
                    enable_pretrim_filter
                    and pretrim_audit.activated
                    and len(filtered_papers) < len(new_papers)
                ):
                    # Mark the dropped papers as triaged so they aren't
                    # re-considered on a later iteration. The audit decisions
                    # carry the filter's reason for skipping each one.
                    dropped_pmids = {
                        d.paper_pmid
                        for d in pretrim_audit.decisions
                        if not d.kept
                    }
                    for paper in new_papers:
                        if paper.pmid in dropped_pmids:
                            sid = paper_source_id(paper)
                            triaged_ids.add(sid)
                    new_papers = filtered_papers
                _pretrim_audits.append(pretrim_audit)

                # Tier 4: A1↔A2 triage dedup. When run_plan_trim_select_dual
                # runs both A1 and A2 sequentially, every paper gets Haiku-
                # triaged twice today — once in A1's pipeline, once in A2's —
                # even though the abstract-triage question ("is this paper
                # relevant to the gene's surface biology?") is identical
                # across both agents (they only diverge at trim+select). The
                # ``triage_cache`` (dict keyed on paper source_id) lets A2
                # reuse A1's outcomes: papers in the cache skip the Haiku
                # call entirely. ~$0.30-0.50/gene saved on heavy-lit genes
                # where the cross-A1-A2 paper overlap is largest.
                cached_outcomes: list[Any] = []
                papers_needing_triage: list[Paper] = []
                if triage_cache is not None:
                    for paper in new_papers:
                        sid = paper_source_id(paper)
                        if sid in triage_cache:
                            cached_outcomes.append(triage_cache[sid])
                        else:
                            papers_needing_triage.append(paper)
                else:
                    papers_needing_triage = list(new_papers)

                logger.info(
                    "iteration %d: triaging %d newly-discovered papers"
                    " (pretrim_filter: activated=%s, dropped=%d, "
                    "triage_cache_hits=%d, fresh=%d)",
                    iteration,
                    len(new_papers),
                    pretrim_audit.activated,
                    pretrim_audit.n_input - pretrim_audit.n_kept,
                    len(cached_outcomes),
                    len(papers_needing_triage),
                )
                fresh_outcomes = triage_abstracts(
                    client,
                    papers=papers_needing_triage,
                    gene=gene,
                    bundle=context.bundle,
                ) if papers_needing_triage else []
                # Populate the cross-agent cache with the fresh decisions so
                # the next agent (A2) reuses them.
                if triage_cache is not None:
                    for o in fresh_outcomes:
                        triage_cache[o.paper_id] = o
                triage_outcomes = cached_outcomes + fresh_outcomes
                for o in triage_outcomes:
                    if o.usage is not None:
                        triage_usage.append(o.usage)
                    triaged_ids.add(o.paper_id)
                actions = apply_triage_outcomes(
                    triage_outcomes,
                    papers_by_id,
                    pool=pool,
                    by_source=clips_by_source,
                    http=http,
                    retraction_index=retraction,
                    add_to_pool_fn=_add_to_pool,
                )
                result.triage_actions.extend(actions)
                n_kept_abstract = sum(
                    1 for a in actions if a.decision == "keep_abstract"
                )
                n_fetched = sum(1 for a in actions if a.fetched_body)
                n_discard = sum(1 for a in actions if a.decision == "discard")
                logger.info(
                    "iteration %d: triage → %d discard / %d keep_abstract / "
                    "%d fetched-body (pool now %d across %d papers)",
                    iteration, n_discard, n_kept_abstract, n_fetched,
                    len(pool), len(clips_by_source),
                )

            if not pool:
                result.warnings.append(
                    f"iteration {iteration} returned no drafts; nothing to trim or select"
                )
                break

            # Step 3 — re-trim ALL papers in the cumulative pool. Re-trim
            # rather than caching per-paper because new clips for an existing
            # paper would otherwise stay invisible; Haiku is cheap enough
            # ($~0.01/paper) that re-trim per iteration is fine.
            trim_results = _run_trim(
                client,
                clips_by_source=dict(clips_by_source),
                gene=gene,
                usage_sink=trim_usage,
                trim_prompt_path=trim_prompt_path,
                timing=timing,
                timing_phase=timing_phase,
                timing_iteration=iteration,
            )
            n_kept = sum(len(t.kept) for t in trim_results.values())
            logger.info(
                "iteration %d: trim kept %d/%d clips across %d papers",
                iteration, n_kept, len(pool), len(trim_results),
            )

            if n_kept == 0:
                result.warnings.append(
                    f"iteration {iteration}: trim kept zero clips; selector skipped"
                )
                break

            # Step 4 — selector picks the final evidence rows from the
            # trimmed menu. Single-pass: triage already fetched every
            # worth-fetching body upstream, so there is no unfetched
            # inventory to act on and no follow-up-search path.
            menu = _format_menu_for_selector(pool, trim_results)
            sel_resp = _run_selector(
                client,
                context=context,
                menu_markdown=menu,
                n_kept=n_kept,
                usage_sink=select_usage,
                select_prompt_path=select_prompt_path,
                timing=timing,
                timing_phase=timing_phase,
            )
            if sel_resp is None:
                result.warnings.append(
                    f"iteration {iteration}: selector returned no valid SelectionResponse"
                )
                break

            result.iteration_log.append(
                IterationLogEntry(
                    iteration=iteration,
                    new_searches=len(current_plan.searches),
                    new_drafts=n_new_drafts,
                    n_papers_after=len(clips_by_source),
                    n_drafts_after=len(pool),
                    n_kept_after_trim=n_kept,
                    n_selections=len(sel_resp.selections),
                )
            )
            logger.info(
                "iteration %d: selector finalized %d selections",
                iteration, len(sel_resp.selections),
            )
            # Single-pass: the loop is capped at MAX_PLAN_ITERATIONS=1, so
            # there is no follow-up round. (Loop kept for audit-shape and
            # to leave iteration reintroducible behind the constant.)

        # End of plan iteration loop. Wrap up.
        result.search_log = cumulative_search_log
        result.n_drafts_total = len(pool)
        result.n_papers_total = len(clips_by_source)
        if result.iteration_log:
            result.n_kept_after_trim = result.iteration_log[-1].n_kept_after_trim
        result.n_iterations_run = len(result.iteration_log)
        result.selection_response = sel_resp

        if sel_resp is None:
            return result

        # Step 5 — promote final selections
        claims, promote_warnings = _promote_selections(
            sel_resp, pool=pool, evidence_id_prefix=evidence_id_prefix
        )
        result.claims = claims
        result.warnings.extend(promote_warnings)
        result.n_claims = len(claims)
        result.n_anchored = sum(1 for c in claims if _is_anchored(c, pool))

        logger.info(
            "FINAL: %d iterations → %d claims (%d anchored, %.1f%%)",
            result.n_iterations_run,
            result.n_claims,
            result.n_anchored,
            100.0 * result.n_anchored / max(1, result.n_claims),
        )

    finally:
        result.triage_usage = summarize_usage(triage_usage, HAIKU_PRICING_KEY)
        result.trim_usage = summarize_usage(trim_usage, HAIKU_PRICING_KEY)
        result.select_usage = summarize_usage(select_usage, SONNET_MODEL)
        result.elapsed_s = round(time.time() - t0, 1)
        result.pretrim_audits = _pretrim_audits
        if timing is not None:
            result.timing = list(timing.entries[timing_start_index:])
        if own_http:
            http.close()

    return result


@dataclass
class DualPlanTrimSelectResult:
    """Output of one sequential dual run: A1 first, then A2 over the same
    warmed HTTP cache.

    The two sub-results carry their own claim ledgers and audit logs (the
    A1 ledger keys ``a1_evi_NN``, the A2 ledger keys ``a2_evi_NN``); this
    wrapper just stitches them together with shared identity + combined
    spend so a single record can be rendered side-by-side for QC.

    A2 sees every paper A1 fetched (via the cache + the joint planner
    re-running cheaply on cache-hit). This is the "shared document
    repository" the Phase 1 design calls for: one execution surface, two
    per-agent trim+select passes over the resulting pool.
    """

    gene: str
    bundle: IdentifierBundle | None
    a1: PlanTrimSelectResult
    a2: PlanTrimSelectResult
    elapsed_s: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.a1.total_cost_usd + self.a2.total_cost_usd

    @property
    def total_claims(self) -> int:
        return self.a1.n_claims + self.a2.n_claims

    @property
    def total_anchored(self) -> int:
        return self.a1.n_anchored + self.a2.n_anchored

    @property
    def pct_anchored(self) -> float | None:
        if not self.total_claims:
            return None
        return 100.0 * self.total_anchored / self.total_claims


def run_plan_trim_select_dual(
    gene: str,
    *,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    retraction_index: RetractionIndex | None = None,
    timing: TimingRecorder | None = None,
    enable_pretrim_filter: bool = True,
) -> DualPlanTrimSelectResult:
    """Phase 1's sequential-dual driver: A1 then A2, shared HTTP cache.

    Runs ``agent_focus="a1"`` to completion, then ``"a2"`` over the same
    ``CachedHTTP`` instance. The second pass re-runs the planner +
    executor, but every HTTP call hits the disk cache, so the marginal
    cost is the A2-specialized trim + select (Sonnet selector dominates).

    Sequential rather than interleaved or parallel: A2 sees every paper
    A1 pulled, which matters for biological-context recall in papers A1
    fetched for surface methodology. Cost ceiling for the dual is the
    sum of two single-focus runs — no double execution of the search
    layer.

    **Tier 4 — A1↔A2 abstract-triage dedup.** A shared
    ``triage_cache`` (paper source_id → TriageOutcome) is created here
    and passed to both A1 and A2. A1 populates it; A2 reuses every
    decision. The abstract-triage question is identical across agents
    (only the trim+select stages diverge), so this is a pure no-loss
    win — ~$0.30-0.50/gene saved on heavy-lit genes where the cross-
    agent paper overlap is largest.
    """

    t0 = time.time()
    client = client or get_client()
    own_http = http is None
    http = http or open_default_client()
    retraction = retraction_index or _empty_retraction_index()

    # Shared cache so A2 reuses A1's abstract-triage outcomes (Tier 4).
    shared_triage_cache: dict[str, Any] = {}

    try:
        logger.info("=== dual run %s: starting A1 ===", gene)
        a1 = run_plan_trim_select(
            gene,
            client=client,
            http=http,
            retraction_index=retraction,
            agent_focus="a1",
            timing=timing,
            enable_pretrim_filter=enable_pretrim_filter,
            triage_cache=shared_triage_cache,
        )
        logger.info(
            "=== dual run %s: A1 done (%d claims, %s anchored) — starting A2 ===",
            gene,
            a1.n_claims,
            f"{a1.pct_anchored:.1f}%" if a1.pct_anchored is not None else "n/a",
        )
        a2 = run_plan_trim_select(
            gene,
            client=client,
            http=http,
            retraction_index=retraction,
            agent_focus="a2",
            timing=timing,
            enable_pretrim_filter=enable_pretrim_filter,
            triage_cache=shared_triage_cache,
        )
        logger.info(
            "=== dual run %s: A2 done (%d claims, %s anchored) ===",
            gene,
            a2.n_claims,
            f"{a2.pct_anchored:.1f}%" if a2.pct_anchored is not None else "n/a",
        )
    finally:
        if own_http:
            http.close()

    return DualPlanTrimSelectResult(
        gene=gene,
        bundle=a1.bundle,  # same gene, same bundle either side
        a1=a1,
        a2=a2,
        elapsed_s=round(time.time() - t0, 1),
    )


def _is_anchored(claim: EvidenceClaim, pool: dict[str, EvidenceClaimDraft]) -> bool:
    """Confirm the claim's quote is a verbatim substring of its source body.

    Since the quote is copied from a pool draft (which was extracted as a
    substring of the source body in the first place), this should always
    pass — but verify explicitly so any drift surfaces.
    """

    # The pool's draft.quote is verbatim from the source body by construction
    # in evidence_retrieval._extract_snippets and gene_literature's
    # extract_paper_drafts. The promote step copies that quote into the
    # claim. So substring identity is the right local check.
    for draft in pool.values():
        if draft.source_id == claim.source_id and draft.quote == claim.quote:
            return True
    # Fall back to a normalized substring check against any pool draft
    # from the same source (in case the model rewrote the quote field
    # we didn't expect — defensive only).
    nq = normalize_for_quote_matching(claim.quote)
    for draft in pool.values():
        if draft.source_id != claim.source_id:
            continue
        nb = normalize_for_quote_matching(draft.quote)
        if find_quote_in_normalized(nq, nb) is not None:
            return True
    return False
