# surface_triage agent — design spec

## Context

The deep-dive `surface_annotator` agent produces fully reconciled, evidence-anchored
`SurfaceomeRecord`s using Opus 4.7. It's thorough but expensive (~minutes of
wall-clock + several dollars per protein on Opus). Running it across the
5,680-protein M1 candidate universe is impractical.

We need a **lightweight triage layer** that decides, per protein, whether a
deep-dive annotation is warranted. The triage agent runs across the full
candidate universe at ~$200 / corpus run, leaving the deep dive to focus on
proteins that genuinely benefit from full reconciliation.

## Output schema

A new `TriageRecordDraft` (agent-emitted) → `TriageRecord` (orchestrator-persisted)
pair, mirroring the `SurfaceomeRecordDraft` → `SurfaceomeRecord` pattern but much
slimmer:

```python
class TriageRecordDraft(BaseModel):
    schema_version: str = "v0.1.0"
    gene: GeneIdentifier
    verdict: Literal["yes", "maybe", "no"]
    verdict_reasoning: str = Field(..., max_length=600)
    accessibility_signal: Literal[
        "likely_accessible",
        "possibly_accessible",
        "unlikely",
        "unknown",
    ]
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list)
    model_path: Literal["sonnet_only"] = "sonnet_only"
```

`TriageRecord` mirrors this with `evidence: list[Evidence]` (orchestrator-promoted
from `evidence_claims` via the existing substring-check pipeline) plus a
`search_log: list[SearchEntry]` (orchestrator-built from `events.jsonl`).

Persisted at `data/triage/{gene}.json`.

### Verdict semantics

- `yes` — accessibility looks plausible AND there's signal worth the deep dive's
  cost. Examples: novel candidates with surface evidence, conditional/induced
  presentation hints, edge cases (MHC-presented peptides, polytopic proteins
  with ambiguous exposure), proteins where M1 sources disagree.
- `maybe` — borderline. The deep dive could go either way; flag for human
  triage before committing the spend.
- `no` — confidently not worth a deep dive. Examples: clearly intracellular
  with no induced-surfacing signal, clearly already-validated targets with
  thorough public characterization (deep dive would just rehash known
  literature), or clearly non-accessible by structural inspection.

### `accessibility_signal` semantics

Independent axis from `verdict`. Captures the agent's call on whether the
protein looks like it has a binder-targetable extracellular face.

- `likely_accessible` — clear surface call from M1 + UniProt; topology + ECD
  size suggest a real extracellular face.
- `possibly_accessible` — some signal but not unambiguous (low-confidence
  surface vote, multi-pass with unclear ECDs, conditional presentation hint).
- `unlikely` — clear evidence the protein is not on the outer leaflet, or is
  embedded with no protrusion.
- `unknown` — insufficient signal to call.

A `verdict=no` with `accessibility_signal=likely_accessible` is valid — that's
"already-validated, thoroughly characterized; deep dive adds little".

## Agent definition

- **Path**: `src/accessible_surfaceome/agents/surface_triage/`
- **Model**: `claude-sonnet-4-6`
- **Display name**: "Surface Accessibility Triage"
- **Builtins**: `read`, `grep`, `glob`, `web_fetch`, `web_search` (same as deep dive)
- **Custom tools**: `gene_lookup`, `patent_lookup`, `gene_literature` (same three; the
  *prompt* enforces the lightweight budget rather than tool restriction)

## Tool-use budget (enforced by prompt)

Target ≤3 tool calls per protein on the median path:

1. `gene_lookup(mode="resolve")` — always.
2. `gene_lookup(mode="db_panel")` — always.
3. `gene_lookup(mode="uniprot_summary")` — almost always (cheap, cached).

Escalate selectively:

- `patent_lookup` — only when `patent_handle` vote is `true` AND the verdict
  hinges on whether there's real translational precedent.
- `gene_literature(mode="gene2pubmed")` — only when M1 votes are
  contradictory or sparse and the verdict needs another anchor.
- `gene_literature(mode="topic_search" / "fetch_abstract" / "fetch_fulltext")` —
  *avoid*. Save those for the deep dive.

The prompt makes this explicit and provides example flows for the common
cases (clear-yes, clear-no, edge case).

## Evidence rigor

Same `EvidenceClaim` machinery as the deep dive: verbatim ≤200-char quotes,
substring-checked against the source registry built from this session's tool
returns. Promoted to `Evidence` records by the orchestrator with
`entailment_verified` flagging.

Typical evidence count per triage record:

- `verdict=yes` for a clear novel candidate: 1–2 claims (one db-anchor, one
  UniProt-anchor).
- `verdict=no` for an already-validated target: 0 claims (the call rests on
  trained knowledge of the approved drug).
- Edge case: 1–3 claims, including the mechanism paper if `gene_literature`
  was needed.

If a verdict can't be supported by a verbatim quote (which is fine for
`verdict=no` cases anchored on trained knowledge), `evidence_claims` is empty
and `verdict_reasoning` carries the rationale.

## Reuse strategy

The deep-dive directory contains substantial agent-agnostic infrastructure:

- `evidence_promotion.py` — pure substring-check + promotion logic
- `source_registration.py` — registers tool returns into a `SourceTextStore`
- `environment.py` — env-var loading + `.env` discovery
- `tool_registry.py` — tool descriptions + handler factories (mostly agnostic)
- Most of `orchestrator.py` — run loop, event handling, search-log building

**Strategy: extract shared infra to `src/accessible_surfaceome/agents/_shared/`
as part of this work**, then build triage against that layer. The deep-dive
agent is migrated onto the same shared layer in the same change. This is a
larger upfront refactor but avoids drift between two near-duplicates and
gives a clean foundation for any future agent.

What stays per-agent:

- `prompts/system.md` — the prompt itself
- A small per-agent `agent.py` (name, model, description, system-prompt path)
- The agent-specific schema (`TriageRecordDraft` vs `SurfaceomeRecordDraft`)
- A thin per-agent orchestrator that knows which schema to validate against
  and where to persist (`data/triage/` vs `data/annotations/`)

## CLI / batch driver

New CLI subcommand. Two modes:

```
uv run accessible-surfaceome triage --gene HER2          # one-off
uv run accessible-surfaceome triage --batch              # full candidate universe
uv run accessible-surfaceome triage --batch --input X.tsv  # custom input
```

Batch mode:

- Default input: `data/processed/candidate_universe/candidate_universe.tsv`.
- Skips proteins already triaged (idempotent re-runs unless `--force`).
- Emits a per-run summary `data/triage/_runs/{run_id}.json` with verdict
  counts, error counts, total cost estimate.
- Concurrency: 4 in-flight requests by default; `--concurrency N` to override.
- Output sortable: a flat `data/triage/_index.tsv` summarizing
  `(gene, verdict, accessibility_signal, n_evidence)` for downstream
  filtering.

## Schema additions to `models.py`

In addition to the new `TriageRecordDraft` / `TriageRecord`:

```python
TriageVerdict = Literal["yes", "maybe", "no"]
AccessibilitySignal = Literal[
    "likely_accessible",
    "possibly_accessible",
    "unlikely",
    "unknown",
]
```

Both reuse existing `GeneIdentifier`, `EvidenceClaim`, `Evidence`,
`SearchEntry` from the deep-dive's schema layer.

## Verification

After implementation:

1. `bash scripts/check-py.sh` — ruff + ty + compile + pytest.
2. New test suite for triage: at minimum `tests/test_triage_orchestrator.py`
   covering the verdict + signal + Evidence persistence path. Mirrors
   `test_evidence_promotion.py`'s structure.
3. End-to-end smoke: triage a known validated target (HER2; expect
   `verdict=no, accessibility_signal=likely_accessible`), a clear novel
   candidate from the M1 panel, and an edge case (KAAG1; expect
   `verdict=yes, accessibility_signal=possibly_accessible` with the
   mechanism paper cited).
4. Batch dry-run on a 50-protein subset; confirm tool-budget compliance
   (median ≤3 tool calls per protein).

## Critical files (new + touched)

New:
- `src/accessible_surfaceome/agents/_shared/` (extracted infra)
- `src/accessible_surfaceome/agents/surface_triage/` (mirrors deep-dive layout)
- `src/accessible_surfaceome/agents/surface_triage/prompts/system.md`
- `tests/test_triage_orchestrator.py`
- `data/triage/` (output dir, .gitkeep'd)

Touched:
- `src/accessible_surfaceome/agents/surface_annotator/` — migrated to use
  `_shared/` for common infra.
- `src/accessible_surfaceome/tools/_shared/models.py` — adds
  `TriageRecordDraft`, `TriageRecord`, `TriageVerdict`,
  `AccessibilitySignal` and exports.
- `src/accessible_surfaceome/cli.py` (or wherever `accessible-surfaceome`
  subcommands are registered) — adds `triage` subcommand.
