# UniProt accession reconciliation for the M1 candidate-universe merge

**Date:** 2026-04-17
**Scope:** M1 candidate-universe (`data/processed/candidate_universe/candidate_universe.tsv`)
**Status:** Implemented. Audit shows zero merge-level collisions after fix.
**Update (2026-04-17, PR #17):** GO evidence-tier gating and CSPA
unspecific exclusion applied after Codex adversarial review — see
"Post-review fixes" below.

## Purpose

The M1 merge joins five surface-annotation sources (UniProt query, GO GAF,
SURFY 2018, CSPA 2015, DeepTMHMM) on base UniProt primary accession. The
older sources (SURFY 2018, CSPA 2015) contain accessions that UniProt has
since merged into other entries (now *secondary* accessions) or deleted.
Without reconciliation the outer-merge silently produces **two rows for
the same protein under two different accessions** — e.g., the HLA-A gene
was represented ~15 separate times, once under the current canonical
primary `P04439` and once per per-allele accession carried by
SURFY/CSPA.

The fix normalizes every source's accessions to the current UniProt
primary before the merge, so there is exactly one row per current primary
accession.

## What the audit found (before fix)

Against UniProt release **2026_01** (28-Jan-2026; `sec_ac.txt`
1,415,097 pairs; `delac_sp.txt` 1,890 deleted):

| Source | secondary (old AC) | deleted SP | split demergers |
|---|---:|---:|---:|
| uniprot | 0 | 0 | 0 |
| go | 0 | 2 | 0 |
| surfy | 83 | 3 | 4 |
| cspa | 46 | 2 | 1 |
| deeptmhmm | 0 | 0 | 0 |

**88 merge-level collision pairs** — 80 HLA (HLA-A/B/C/DRB1/DQA1),
8 others (IGHM, ADORA3, LYNX1, VSIG8, TMIGD3, OR8G2P, OR8G3). In each
case the old allele accession and the current primary were both present
in the merged output under separate rows, creating duplicate records of
the same protein.

## What was implemented (fix #1)

Before the outer-merge, `build_candidate_universe.py` now:

1. Loads `sec_ac.txt` and `delac_sp.txt` from
   `data/external/uniprot_accession_history/`.
2. Drops rows whose accession is in `delac_sp.txt` (deleted
   Swiss-Prot entry).
3. Rewrites rows whose accession is listed in `sec_ac.txt` to the
   current primary. Split entries (one old accession → multiple current
   primaries) are duplicated once per primary; both derived entries
   inherit the old annotation.
4. Groups by `uniprot_accession` within each source and aggregates
   (max for numeric, first for string) so each source contributes at
   most one row per primary.

Normalization summary (written to `candidate_universe_summary.json`):

```
uniprot    4,817 -> 4,817   (no-op)
go         3,614 -> 3,612   (-2 deleted)
surfy      2,886 -> 2,808   (83 rewritten, 3 deleted, 4 split-duplications)
cspa       1,500 -> 1,454   (46 rewritten, 2 deleted, 1 split-duplication)
deeptmhmm  2,360 -> 2,360   (no-op)
```

## Verification

- Re-ran `src/accessible_surfaceome/audit/audit.py` against the
  new merge output. Result: **merge_level_collisions.tsv → 0 pairs**.
- Spot-checks: HLA-A, HLA-B, HLA-C, HLA-DRB1 now each resolve to a
  single row under their current canonical primary with
  `uniprot,go,surfy,cspa` all flagged.
- Agreement buckets 4/5 and 5/5 unchanged (586 and 1,174) — those were
  already anchored by the canonical primaries. Lower-k buckets
  shrank by 89 rows total, matching the expected number of stale
  allele + deleted rows eliminated.

## Files to review

**Collection (new)**
- [`download_uniprot_accession_history.py`](../../src/accessible_surfaceome/sources/_support/accession_history.py)
  — fetches `sec_ac.txt` and `delac_sp.txt` (and optionally
  `delac_tr.txt.gz`) with SHA256 traceability. Outputs to
  `data/external/uniprot_accession_history/`.

**Processing (new shared util + edits)**
- [`uniprot_accession_history.py`](../../src/accessible_surfaceome/sources/_support/accession_history.py)
  — parsers for `sec_ac.txt` and `delac_sp.txt`, plus
  `load_accession_history()` convenience loader. Used by both the
  audit script and the merge script.
- [`merge.py`](../../src/accessible_surfaceome/merge/__init__.py)
  — adds `_normalize_accessions()` helper; `main()` now loads the
  accession history, normalizes each source before the merge, and
  records the normalization stats in `candidate_universe_summary.json`
  and accession-history files in `candidate_universe_traceability.json`.
  Docstring updated to describe the new behavior.

**Analysis (new)**
- [`audit.py`](../../src/accessible_surfaceome/audit/audit.py)
  — classifies every source accession (`primary_current` /
  `primary_not_queried` / `secondary` / `deleted_swissprot` /
  `unknown`) and computes merge-level collision pairs from
  `candidate_universe.tsv`.

**Outputs (regenerated)**
- `data/processed/candidate_universe/candidate_universe.tsv`
  (6,177 → 6,088 rows)
- `data/processed/candidate_universe/candidate_universe_summary.json`
  (now includes `accession_normalization` per-source stats)
- `data/processed/candidate_universe/candidate_universe_traceability.json`
  (now lists `sec_ac.txt` and `delac_sp.txt` as merge inputs)
- `data/analysis/candidate_universe_agreement/*.{pdf,jpeg}` —
  agreement bar, UpSet, pairwise Jaccard (regenerated off the new
  merge)
- `data/analysis/cross_source_uniprot_audit/{audit_summary.json,
  per_source_classification.tsv, merge_level_collisions.tsv}`

## Reproduce

```bash
# 1. Fetch UniProt accession-history reference (first-time only; ~60 MB)
uv run python -m accessible_surfaceome.sources._support.accession_history

# 2. Rebuild the candidate universe with normalization applied
uv run python -m accessible_surfaceome.merge

# 3. Regenerate agreement figures
uv run python -m accessible_surfaceome.audit.blog_figures

# 4. Re-audit (should show 0 merge-level collisions)
uv run python -m accessible_surfaceome.audit.audit
```

## Post-review fixes (Codex adversarial review, 2026-04-17)

Two correctness issues flagged by the adversarial reviewer were addressed
before merge because they changed the headline agreement counts this PR
regenerates:

1. **GO IEA-only gating** (`_load_go` in `build_candidate_universe.py`).
   The per-gene-product input already carries `has_experimental`,
   `has_curated`, `has_sequence`, `has_electronic` tier flags. Previously
   only `has_experimental` was propagated and `go_surface_flag` was set to
   1 for every retained accession, so pure-IEA (electronic-only) rows
   counted identically to curator-reviewed evidence. The loader now
   propagates all four tier columns, derives a new
   `go_low_confidence_only = (has_electronic ≥ 1 AND has_experimental = 0
   AND has_curated = 0 AND has_sequence = 0)` column, and gates
   `go_surface_flag = (go_low_confidence_only = 0)`. Effect: 473
   electronic-only GO rows no longer contribute to `n_sources_surface`.
2. **CSPA surface flag gated on explicit positive categories** (`_load_cspa`).
   CSPA Table_B classifies each entry as `high confidence`, `putative`, or
   `unspecific`; 8 rows in the 2015 snapshot are detected via Table_A but
   never classified in Table_B (blank category). The loader now sets
   ```
   cspa_surface_flag = cspa_is_high_confidence == 1 OR cspa_is_putative == 1
   ```
   and carries `cspa_is_putative`, `cspa_is_unspecific`, and a new
   `cspa_category_missing` flag forward as provenance. Unspecific and
   blank-category rows stay in the merge with `cspa_surface_flag = 0` so
   the candidate universe remains the union of all observed source
   accessions — downstream can distinguish "absent from CSPA" from
   "seen only as unspecific" from "detected but not classified". Two
   earlier iterations of this fix were less correct: the first filtered
   unspecific rows out entirely (silently dropped 172 accessions; second
   Codex pass caught it), and the second gated on `not unspecific`
   (still counted 8 blank-category rows as positive; third pass caught
   that). This iteration uses explicit positive categories.

### Collapse-conflict audit + semantics-preserving reducers (Codex finding #3)

`src/accessible_surfaceome/audit/accession_collapse.py` replays the
`_normalize_accessions` explode step without the final `groupby().agg()`
and records every column whose values differ across rows that collapse
onto the same primary. `_normalize_accessions` now accepts an
`agg_override` dict so each source can replace the default `first`/`max`
reducers where they would silently drop meaningful detail.

Per-source overrides (defined in `build_candidate_universe.main()`):

| Source | Column | Reducer | Rationale |
|---|---|---|---|
| cspa | cspa_category | `_best_cspa_category` | Priority: high > putative > unspecific > blank; keeps category consistent with the boolean flags |
| cspa | cspa_gene_symbol | `_first_nonempty_symbol` | Skips `""` and `"0"` placeholder values before picking |
| cspa | cspa_is_unspecific | `min` | `1` iff *every* pre-collapse row was unspecific (boolean AND) |

`max` remains the default for `cspa_surface_flag` (boolean OR) and for
`surfy_ml_score` (best per-allele ML score — open question #1). CSPA
ships two parallel views of categorical evidence so the priority-pick
doesn't hide mixed pre-collapse states:

- `cspa_category` + `cspa_is_*` (headline, mutually exclusive): the
  `cspa_category` string is picked by priority (high > putative >
  unspecific > blank), and the four category booleans
  (`cspa_is_high_confidence`, `cspa_is_putative`, `cspa_is_unspecific`,
  `cspa_category_missing`) are **re-derived from that single category**
  after collapse so they always agree with the headline label.
- `cspa_any_*_precollapse` (boolean OR across pre-collapse rows):
  faithful pre-collapse evidence. These are the values the `max`
  reducer would produce on the raw per-row booleans and are emitted
  verbatim from the `_normalize_accessions` step.
- `cspa_mixed_category_conflict = 1` iff 2+ distinct categories were
  observed before collapse. Lets downstream explicitly filter or
  exclude ambiguous primaries.

Effect on the three affected primaries: P01871 (IGHM) emits headline
`high confidence` with `any_unspecific_precollapse = 1`; P01909
(HLA-DQA1) and P01911 (HLA-DRB1) emit headline `high confidence` with
`any_putative_precollapse = 1`. All three carry
`cspa_mixed_category_conflict = 1`.

The pre-publish drift assertion now checks `cspa_surface_flag` against
`cspa_any_high_confidence_precollapse OR cspa_any_putative_precollapse`
(the pre-collapse-OR semantics), which is the actual rule the loader +
max-reducer produce. If either the loader filter or the reducer choice
changes, the assertion trips before anything is written.

Post-fix conflicts (from `collapse_conflicts.tsv`):

| Source | Column | Reducer | N primaries with conflict |
|---|---|---|---:|
| surfy | surfy_ml_score | max | 4 (all HLA: P01889, P01911, P04439, P10321) |
| cspa | cspa_is_high_confidence | max | 3 (P01871, P01909, P01911) |
| cspa | cspa_category | _best_cspa_category | 3 |
| cspa | cspa_gene_symbol | _first_nonempty_symbol | 3 |
| cspa | cspa_is_unspecific | min | 1 |
| cspa | cspa_surface_flag | max | 1 |

Spot-check after the fix: P01909 (HLA-DQA1), P01911 (HLA-DRB1), and
P01871 (IGHM) each resolve to `cspa_category = "1 - high confidence"`
consistent with `cspa_is_high_confidence = 1`, and carry the correct
gene symbol (not `"0"`).

### Updated output statistics (post-fix)

```
per-source surface counts:    uniprot=4,817  go=3,139  surfy=2,808  cspa=1,241  deeptmhmm=2,219
agreement (k/5):              0/5=307  1/5=2,206  2/5=944  3/5=943  4/5=1,139  5/5=549
total candidate rows:         6,088  (unchanged — CSPA unspecific/blank, GO IEA-only, and
                              other non-positive rows stay in the universe with their
                              respective surface flags set to 0)
merge-level collision pairs:  0  (preserved)
```

A pre-publish assertion in `build_candidate_universe.main()` re-derives
`go_surface_flag` and `cspa_surface_flag` from the raw evidence columns
+ split-ambiguity gating in the merged table and raises if they
disagree with the emitted flag counts — so the `flag_rules` block in
`candidate_universe_traceability.json` cannot silently drift from the
loader logic. The TSV, summary, and manifest are staged into a unique
per-run directory `<out>/.staging/<timestamp>-<hex>/` and only swapped
into place via hardlink + `Path.replace` after the full bundle passes
validation — so an interrupt mid-publish leaves the previously
published bundle intact, and concurrent runs cannot race on shared
`.tmp` paths.

The `0/5` bucket (303) captures proteins that appear in at least one
source's snapshot but are not currently flagged as surface-positive by
any source (CSPA unspecific only, GO IEA-only, SURFY / DeepTMHMM
annotation metadata without a surface call, etc.). Keeping them in the
universe preserves the provenance distinction between "absent from the
source" and "present but not surface-positive".

### Split-history mappings are quarantined

When one historical accession split into multiple current primaries, the
loader still duplicates the row onto every derived primary (the old
annotation applies to at most one of them — UniProt doesn't tell us
which). Each duplicated row carries `<source>_split_mapping_ambiguous =
1`, and the merge explicitly zeroes the corresponding
`<source>_surface_flag` so ambiguous rows do not contribute to
`n_sources_surface` or pairwise overlap. `split_mapping_ambiguous_any_source`
is set on 10 primaries in the current output (8 SURFY, 2 CSPA),
covering 4 SURFY split-remaps and 1 CSPA split-remap. Downstream can
either exclude these rows entirely or manually curate the correct
descendant and set the flag to 0.

### Deferred to a follow-up PR

- **Organelle-lumen exclusion** (plan step 7 / Codex HIGH-3). Needs
  re-exporting UniProt subcellular-location/evidence fields upstream and
  an explicit exclusion pass. Tracked as its own branch.

## Open questions for the reviewer

1. **Aggregation rule for collapsed rows.** When multiple SURFY
   rows (different allele accessions) collapse onto the same primary,
   the helper takes `max` of numeric columns (e.g., `surfy_ml_score`)
   and `first` of string columns (e.g., `surfy_label`, gene symbol
   carryovers). Is `max` the right choice for `surfy_ml_score` (we want
   the most favorable surface-ML evidence for the gene), or should it
   be `mean` / representative-only? Similarly for
   `cspa_max_protein_probability` and `cspa_max_unique_peps`.
2. **Split-entry duplication.** ~~Open.~~ Resolved: derived rows carry
   `<source>_split_mapping_ambiguous = 1` and are excluded from the
   per-source surface flag. See "Split-history mappings are
   quarantined" above.
3. **TrEMBL deletions not checked.** `delac_tr.txt.gz` (~631 MB) is
   skipped by default. `audit_cross_source_uniprot_ids.py` therefore
   classifies genuine deleted-TrEMBL accessions as `unknown`. For a
   Swiss-Prot–heavy pipeline this is almost never an issue, but worth
   enabling (`--include-trembl`) if a reviewer wants the last ~0.1%
   of coverage.
4. **`primary_not_queried` accessions (1,605).** Valid-looking current
   UniProt accessions that were flagged by GO/SURFY/CSPA/DeepTMHMM but
   are not in our UniProt surface-candidate query output. Unaffected
   by this fix; independent question of whether our UniProt query is
   tight enough (most likely reviewed entries the keyword/topology
   filter didn't catch, plus some current TrEMBL). Recommend triaging
   separately.
5. **Deferred Codex findings.** HIGH-3 (organelle-lumen exclusion
   filter, plan step 7) remains open and is tracked as a follow-up
   PR. HIGH-2 leftover (`go_low_confidence_only` column) was addressed
   in-scope; see "Post-review fixes" above.
