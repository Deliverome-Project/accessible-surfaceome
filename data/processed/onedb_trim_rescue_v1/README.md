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

## Deep-dive cohort

150 of the 204 new entrants already have records (the intracellular cohort).
`deep_dive_cohort.tsv` holds the remaining **54**, all `m1_and_sonnet`.

### Deterministic-feature readiness — the 54 are ready

Canonical topology is **54/54**, so the `require_measured_topology` guard will
not fire. Coverage meets or beats the genome base rate on every fact:

| Fact | 54-cohort | genome rate | verdict |
|---|---:|---:|---|
| canonical topology | 54/54 (100%) | — | complete |
| isoform topology | 35/54 (65%) | 35% | above rate |
| paralogs | 45/54 (83%) | 51% | above rate |
| ortholog ECD | 50/54 (93%) | 53% | above rate |
| schweke homomer | 8/54 (15%) | 11% | above rate |
| surface_bind | 2/54 (4%) | 24% | genuine absence — SURFACE-Bind carries 2,708 accessions and these are mostly non-classical surface proteins |

`deterministic_gaps.tsv` lists the **11** genes with an ortholog or paralog
gap. TMEM127 and WLS appear there because they were never in the universe
before defect 2 was fixed, so no sweep has ever covered them; the other 9 are
likely true absences (a gene with no paralogs legitimately has no rows), but a
BioMart re-pull is free and settles it either way.

## Blocked: the paralog release shadow

Investigating the above surfaced a **live production regression** on the
paralog axis, identical to the topology one this repo already fixed:

```
paralog_topo_2026_05_16     91,103 pairs / 5,790 human genes   <- global
paralog_2026_09_20_rescue    1,066 pairs /   123 human genes   <- cohort backfill, NEWER
```

`_latest_paralog_version()` selected on `fetched_at DESC LIMIT 1`, so the
123-gene release shadowed the global one — **every deep dive since 2026-09-21
01:38 saw paralogs for 2% of the cohort**, and an empty paralog list renders as
"this protein has no paralogs": a fabricated negative, the same failure class
as the placeholder-topology zeros.

Fixed in [`d1_deterministic.py`](../../../src/accessible_surfaceome/agents/surfaceome_v1/d1_deterministic.py)
— the picker now selects by distinct-gene coverage, tie-breaking on recency,
matching `_latest_ortholog_ecd_version`. Pinned by
`test_paralog_version_prefers_coverage_over_recency`. All four pickers now
resolve to the dominant releases.

**Outstanding.** The picker fix makes the 123 rescue-cohort genes' paralog rows
unreachable, since they exist only under the shadowed version. They must be
merged into the dominant release — the additive half of the same
"merge into the dominant release, never a parallel one" rule:

```bash
uv run python scripts/cloud/merge_paralog_release.py --execute   # not yet written
```

Until that merge runs, those 123 genes read as having no paralogs. The merge is
`INSERT OR IGNORE` on `(paralog_version, human_ensembl_gene,
paralog_ensembl_gene)` against both D1s; only 4 of the 123 genes already exist
in the dominant release, so ~119 genes / ~1,000 pairs move.

Separately, `topo_2026_09_rescue` still holds 571 orphan rows in
`topology_public` with no `topology_release` row. Harmless — the topology
picker intersects against `topology_release`, so an unlisted version can never
be selected — but it is dead weight.
