# 1-of-5-DB trim rescue + optimized-cutoff orphans

Two `pubmed_ncbi` second-stage lanes closing the last gaps in the rule
"every Sonnet-`no` gene the universe gate can drop gets a literature-augmented
second look".

## Why this ran

`build_candidate_universe_v3.py` drops a gene when it is Sonnet-`no` at **high**
confidence with exactly **1 of 5** gating DB votes (optimized cutoffs). That
removed 1,457 genes. Meanwhile the two earlier rescue lanes covered the
**zero-DB** population exhaustively — so a gene with *strictly less* DB evidence
got two looks and a 1-DB gene got one. 1,417 of the 1,457 (97%) had never been
re-examined.

Chasing it surfaced three more defects in the same call site, all of the same
shape — **the trim and the gate read different evidence than the rescue lanes
wrote**:

| # | Defect | Effect |
|---|---|---|
| 1 | trim set had no second stage | 1,417 genes judged on one pass |
| 2 | `is_trim()` never read `pubmed_verdict` | RNF144A / TMEM127 / WLS rescued to `contextual`, trimmed anyway |
| 3 | `RUN_PM` bound 1 of 2 rescue lanes | **all 148 intracellular rescues absent from the universe** despite live deep-dive records |
| 4 | lanes scoped on *initial* votes, gate runs on *optimized* | 74 genes moved 1-DB → 0-DB by the CSPA tightening, fell through both lanes |

Defect 3 is the one CLAUDE.md already warned about ("missing the second lane
silently reverts 148 genes to their pre-rescue `no`") — the warning was
written, the call site was not fixed.

## Lanes

| run_id | cells | cost | rescues |
|---|---:|---:|---:|
| `genome_1db_trim_pubmed_ncbi_v1` | 1,417 | $10.80 | **53** (3.7%) |
| `genome_optcut_zerodb_pubmed_ncbi_v1` | 74 | $0.58 | **2** (2.7%) |

```bash
uv run python scripts/triage_runner.py \
    --gene-list data/processed/onedb_trim_rescue_v1/gene_list.tsv \
    --model claude-sonnet-4-6 --variants pubmed_ncbi --replicates 1 \
    --d1 --run-id genome_1db_trim_pubmed_ncbi_v1 --concurrency 16
```

New `yes` calls: CCDC8, EXTL3, HSH2D, TMX1. Rescue reasons skew
`dual_localization` (24) and `cell_state_induced` (15). Both lanes are 100%
valid-verdict and synced to public D1.

A handful of cells fall back to the `naive` variant when the PubMed evidence
fetch fails (4 of 74 here). **Do not filter these lanes on
`prompt_variant='pubmed_ncbi'`** — they are still that gene's second look, and
excluding them reports the gene as never re-examined.

## Universe delta

```
5,128 → 5,332   (+204 added, 0 removed)
sonnet_only  961 → 1,108
```

| Contribution | n |
|---|---:|
| intracellular lane, unbound until now (defect 3) | 147 |
| 1-DB trim lane rescues | 53 |
| `is_trim` now defers to the second stage (defect 2) | 2 |
| optcut-zerodb lane rescues | 2 |

**The `sonnet_only 961` figure is now stale** — it was previously agreed across
v3 / catalog / Fig 3. Regenerate the catalog and Fig 3 before citing it.

## Deep-dive cohort — run, and the trim is vindicated

150 of the 204 new entrants already had records (the intracellular cohort);
TPO / TMEM127 / WLS were filled separately. The remaining **52** ran under
`--cohort-run-id universe_gapfill_2026_09` (reusing the existing gapfill run
rather than minting a fourth run_id):

| | |
|---|---|
| genes | 52/52 VALID, 0 INVALID, 0 ERROR |
| cost | $70.61 + $1.23 (one re-run, below) |
| wall clock | 19.4 min at concurrency 28 |
| topology guard | 0 trips — every gene had measured DeepTMHMM topology |

`deep_dive_run` now holds **5,333** distinct genes across 3 run_ids, and
**every gene in the 5,332-row v3 universe has a record**. (The 5,333rd is
BRI3BP, annotated but trimmed out of the universe.)

**Result: 0 of 52 reached `likely` or better** — 37 `no`, 9 `low`, 6
`moderate`. Against the prior batch's 8/147 (5.4%) this is a clean negative,
and it is the strongest available evidence that **the 1-of-5-DB trim rule is
sound**: the genes it drops really are low-yield. What was wrong was never the
rule, only that it fired on a single unreviewed pass. Now that every trimmed
gene has had a literature-augmented second look, the rule can be trusted
rather than merely assumed.

497 paralog entries were baked across the 52 records — the fix from the
release-shadow section below, reaching records rather than sitting in D1.

### One gene reported VALID with no run row

BCHE finished, published its record and intermediates, and logged `VALID` —
but wrote no `deep_dive_run` row, so the sweep summary read 52/52 while the
cohort was one short. `D1DeepDiveSink.insert` documents that it "never raises
so the worker pool keeps going": it swallows a transient D1 500 and returns
`False`. [`run_deep_dive_sweep.py`](../../../scripts/run_deep_dive_sweep.py)
discarded that bool, so a dropped write was indistinguishable from success —
the same failed-lookup-as-real-result shape as the placeholder topology and
the shadowed paralog release, this time on the write path.

The driver now checks the return value and reports a distinct `NO_RUN_ROW`
status, counted apart from both VALID and ERROR because the annotate itself
succeeded. BCHE was re-run ($1.23) and the gap is closed.

### Deterministic-feature readiness — verified through the accessor

**Verify with `fetch_deterministic_features()`, not with table queries.** The
first pass here reported paralogs at 45/54 by querying
`paralog_topo_2026_05_16` directly, on the assumption it was authoritative.
It was not: `_latest_paralog_version()` was returning a 123-gene shadow
release at the time and none of this cohort is in it, so the annotator would
have seen **0**. A raw-table count answers "what is in the release I chose";
only the accessor answers "what will the agent actually read".

Numbers below are from the accessor, after the shadow was fixed and merged:

| Fact | 52-cohort | notes |
|---|---:|---|
| canonical topology (MEASURED) | **52/52** | none will trip `require_measured_topology` |
| orthologs | 52/52 | |
| structure | 52/52 | AlphaFold, baked at annotate time |
| paralogs | 45/52 | |
| isoform topologies | 34/52 | absent = single-isoform gene |
| homo-oligomerization | 8/52 | `is_homo_oligomer` true; absent = not a predicted homomer |
| surface_bind | 2/52 | genuine absence — SURFACE-Bind carries 2,708 accessions total |

`paralogs_checked` and `isoform_topologies_checked` are **true for all 52**, so
a zero is a measured zero rather than a skipped lookup. The 7 genes with no
paralogs (BRK1, CEND1, ERP29, METTL9, MINPP1, PLAA, TMX2) therefore render as
"no paralogs" without fabricating a negative — the distinction that the
`checked` flags exist to preserve.

Topology is not what limits paralog ECD identity: **9,896 of 10,103** distinct
paralog partner accessions (98.0%) carry `human_canonical` topology.
`ecd_pct_identity` is NULL on 20.7% of pairs because the protein has no ECD to
align (the SRC pattern), not because a measurement is missing.

## The paralog release shadow (resolved)

Investigating readiness surfaced a live regression on the paralog axis,
identical to the topology one this repo already fixed:

```
paralog_topo_2026_05_16     91,103 pairs / 5,790 human genes   <- global
paralog_2026_09_20_rescue    1,066 pairs /   123 human genes   <- cohort backfill, NEWER
```

`_latest_paralog_version()` selected on `fetched_at DESC LIMIT 1`, so the
123-gene release shadowed the global one. An empty paralog list renders as
"this protein has no paralogs" — a fabricated negative, the same class as the
placeholder-topology zeros.

**Blast radius: 4 records**, not the whole corpus. The shadow began
2026-09-21 01:38:24 and the 5,130-gene sweep and 148-gene rescue cohort both
predate it. Of the four:

| Gene | carried | should have | |
|---|---:|---:|---|
| NPM1 | 2 | 2 | inside the 123, unaffected |
| **TPO** | **0** | **5** | lost 5 paralogs; re-annotated ($1.53), now correct |
| TMEM127 | 0 | 0 | no loss |
| WLS | 0 | 0 | no loss |

Fixes, all landed:

1. **Picker** — [`d1_deterministic.py`](../../../src/accessible_surfaceome/agents/surfaceome_v1/d1_deterministic.py)
   now selects on distinct-gene coverage with a recency tie-break, matching
   `_latest_ortholog_ecd_version`. Pinned by
   `test_paralog_version_prefers_coverage_over_recency`.
2. **Merge** — coverage-based selection stops a small release shadowing a
   large one but makes it *unreachable*, so its rows still had to be folded
   in. [`merge_paralog_release.py`](../../../scripts/cloud/merge_paralog_release.py)
   did that against both D1s: **92,122 pairs / 5,909 genes**, all 123 rescue
   genes reachable, idempotent on re-run.
3. **Schema drift** — the merge's two-way column reconciliation caught that
   private `compara_paralog` lacked `ecd_pct_similarity` although
   `cloudflare/d1_schema.sql` declares it. Repaired by
   [`backfill_private_paralog_similarity.py`](../../../scripts/cloud/backfill_private_paralog_similarity.py)
   (ALTER + 683/683 values copied from public). This never gated a run — the
   deterministic loader reads the PUBLIC mirror — but private is the restore
   source, so a recovery from the R2 dumps would have reintroduced it.

**The rule, restated:** a backfill is appended to the live release, never
uploaded beside it. Both pickers punish a parallel cohort-scoped release, in
opposite directions, so there is no upload strategy that is safe under both.

`topo_2026_09_rescue` still holds 571 orphan rows in `topology_public` with no
`topology_release` row. Harmless — the topology picker intersects against that
table, so an unlisted version can never be selected — but it is dead weight.
