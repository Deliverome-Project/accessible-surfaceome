# Fill ortholog / paralog / isoform / topology gaps for genome-wide v2 yes/contextual genes

**Date:** 2026-06-01
**Branch:** new work stacked on PR #47 (`claude/pedantic-mendel-d0be83`); PR base = #47.
**Status:** design — pending review.

## Problem

The `genome_full_sonnet_ncbi_v2` triage sweep classified 19,324 genes:
**2,528 `yes` + 1,721 `contextual` = 4,249** surface candidates (4,237 distinct
UniProt accessions). The v2 **deep-dive** records for these don't exist yet
(`deep_dive_run` / `surface_annotation` hold only smoke rows). When the v2
deep-dive runs, the orchestrator calls `fetch_deterministic_features(uniprot_acc)`,
which reads the deterministic-feature D1 tables (`topology_public`,
`compara_paralog`, `compara_ortholog_ecd`). **Those tables are incomplete for the
v2 candidate set**, so records would render with blank ortholog / paralog /
isoform / topology blocks.

### Root cause: the sweeps were scoped to v1, not v2

`scripts/build_topology_candidate_set.py` (which scopes every topology / ortholog /
paralog sweep) defaults to `DEFAULT_TRIAGE_RUN_ID = "genome_full_sonnet_ncbi_v1"`
unioned with candidate-universe `in_db_union = 1`. The **v2** triage surfaced
LLM-positive genes outside that scope (LLM-positive but DB-negative, plus
v1→v2 verdict changes). Those genes were never swept.

### Scope and measured gap (the candidate-set union, not just triage)

The sweep scope is the **union** `build_topology_candidate_set.py` already
defines: candidate-universe `in_db_union = 1` (DB-positive in any source) **OR**
v2 triage `yes`/`contextual`. For the v2 run that's **6,431 candidate rows →
6,418 distinct accessions** (`db_only` 2,182 + `triage_only` 858 + `both`
3,391). The earlier "v2 triage only" framing (4,249) under-scoped it.

**Empirically-measured backfill (D1 presence + UniProt/Ensembl sampling, 2026-06-01):**

| Feature | D1 source | Genes w/ no row | **Real new DeepTMHMM seqs** | Genuine-absence (flag only) |
|---|---|---|---|---|
| Canonical ("main") | `topology_public` `human_canonical` | 66 | **66** (exact) | 0 |
| Isoforms | `topology_public` `human_isoforms` | 3,014 | **~141** (only 3% sampled have an alt isoform) | ~2,934 single-isoform |
| Orthologs (mouse/cyno) | `compara_ortholog_ecd` | 1,360 | **~1,190** mouse+cyno (~50% sampled have a one2one) | ~674 no one2one |
| Paralogs | `compara_paralog` | 953 | **0** (ECD reuses each paralog's already-swept canonical row) | — |

**Total ≈ ~1,400 new DeepTMHMM sequences**, dominated by orthologs. The
"genes w/ no row" column is a misleading upper bound — most missing-isoform
genes are genuinely single-isoform and most no-row genes overall just need the
"checked, none" sentinel, not a sequence run. The empirical alt-isoform rate
(3%) and ortholog one2one rate (~50%) come from deterministic samples of the
missing sets; the audit (§A) produces the exact per-gene truth.

**Ortholog decision (locked):** **DeepTMHMM each one2one ortholog**, consistent
with how the existing 11k ortholog rows were produced — no code change to the
ECD path. (The human→ortholog topology *projection* still applies at
record-assembly for display, as on #47; it is not used to skip the ECD-identity
DeepTMHMM run.)

### Code is mostly in place on #47; the gap is data

Rebasing onto #47 revealed the schema/loader work is **already done there**
(it was only ever reverted on `main`):

- `OrthologEntry` and `IsoformTopology` already carry `per_residue_topology`
  (+ `deeptmhmm_label`, `tm_helix_count`, `ecd_length_residues`, projection
  provenance). **Orthologs and isoforms already have per-residue topology in
  records.**
- `ParalogEntry` already carries `per_residue_topology`, `ecd_pct_similarity`,
  `tm_helix_count`, terminal orientations, `sequence`, etc., **gated on the
  `CLOSE_PARALOG_THRESHOLD = 80.0`** full-length-identity cutoff —
  i.e. close paralogs (≥80%) get a full topology row, distant paralogs stay
  lean chip-only. This is exactly the "show topology for the high paralogs per
  our ~80% cutoff" behavior requested.
- `_fetch_paralogs` already LEFT-JOINs `topology_public` and populates those
  fields.

**But the D1 data layer is behind the #47 schema:** `compara_paralog` has **no
`ecd_pct_similarity` column** yet (the loader SELECTs `cp.ecd_pct_similarity`,
which would error against today's table), and the close-paralog topology data
isn't computed. So "paralog topology" is a **data + D1-migration** task, not a
schema change.

## Goals

1. Produce a coverage **manifest** that classifies each v2 yes/contextual gene ×
   feature as `present` / `genuinely-absent` / `needs-backfill`. (The
   "take a look at that" deliverable.)
2. **Backfill D1** (`topology_public` canonical+isoforms, `compara_ortholog_ecd`,
   `compara_paralog` incl. the new `ecd_pct_similarity` + close-pair topology)
   for the `needs-backfill` genes, scoped to the v2 triage run.
3. Add an explicit **"checked, none found"** marker to orthologs / paralogs /
   isoform-topology so genuine absence is distinguishable from not-computed
   (extending the existing `SurfaceBindFeatures.has_data` convention).
4. PR stacked on #47 with an **explanatory note**.

## Non-goals

- Running the v2 deep-dive annotation itself. This only completes the upstream
  deterministic data so a later deep-dive run produces complete records.
- Re-sweeping genes that already have data (idempotent; skip the present set).
- Changing the ≥80% close-paralog cutoff or the ortholog projection logic
  (already on #47).

## Workstreams

### A. Coverage audit + manifest (net-new)

New `scripts/audit_v2_deterministic_coverage.py`:

- Pull the v2 yes/contextual genes (COALESCE the `__resolver_v3_fix` rerun per
  CLAUDE.md run_id conventions, same as `build_topology_candidate_set.py`).
- For each gene, probe D1 presence in: `topology_public` (`human_canonical`,
  `human_isoforms`), `compara_paralog`, `compara_ortholog_ecd`.
- Classify each feature `present` / `genuinely-absent` / `needs-backfill`.
  Genuine-absence needs the upstream truth:
  - **isoforms:** UniProt isoform count (a single-isoform gene is genuinely
    absent). Source: the canonical UniProt record / existing isoform enumeration
    used by the isoform sweep.
  - **orthologs:** whether Ensembl Compara has any one2one mouse/cyno ortholog
    (BioMart). No ortholog → genuine-absence.
  - **paralogs:** whether Compara lists any paralog pair. None → singleton →
    genuine-absence.
  - Pragmatic two-pass option: rows with no D1 presence are flagged
    `needs-backfill`; whatever still has no row after the backfill completes is
    reclassified genuine-absence and stamped via the §C sentinel.
- Output a manifest TSV under `data/analysis/v2_deterministic_coverage/` with
  per-gene per-feature status + `selection_reason` + stable IDs (hgnc_id,
  uniprot_acc, ensembl_gene). **This sizes the real backfill before any heavy
  compute.**

### B. Targeted data backfill (existing tools, re-pointed at v2)

1. **Candidate set:** `build_topology_candidate_set.py
   --triage-run-id genome_full_sonnet_ncbi_v2`, restricted to the
   `needs-backfill` genes from the manifest.
2. **BioMart:** `python -m accessible_surfaceome.sources.ensembl_compara download`
   for the missing genes (mouse/cyno orthologs) + the paralog-pair source for the
   missing paralog genes.
3. **Topology sweep:** `scripts/run_topology_sweep.py` with
   `DEEPTMHMM_ROOT=/Users/rebeccacarlson/Git/deliverome-internal/analyses/surface-proteome`
   and **`--max-workers 1`**, over the targeted set →
   `topology_public` (canonical + isoforms), `compara_ortholog_ecd` (+ ortholog
   topology projection from human canonical), `compara_paralog`
   (+ `ecd_pct_similarity` for close pairs). Uploads to D1 (private + public
   mirror) incrementally; idempotent on the sweep keys so a restart skips
   completed cells.
4. **D1 migration:** add the `ecd_pct_similarity` column to `compara_paralog`
   (private + public schema + the `.sql` schema files) so #47's loader stops
   erroring; compute + populate it for close pairs.

**Compute scale: ~1,400 new DeepTMHMM sequences** (66 canonical + ~141
alt-isoforms + ~1,190 mouse/cyno orthologs; paralogs add 0 new runs), per the
empirical table above. Orthologs dominate. Runs **single-worker** in the
background, publishing to D1 as it goes; the PR lands the tooling + manifest +
the fast canonical proof-run, and the ortholog/isoform sweep completes after.
The manifest (§A) produces the exact per-gene truth before the heavy run starts.

### C. "Checked, none found" sentinels (net-new schema)

Extend the existing `SurfaceBindFeatures.has_data` pattern so a checked-but-empty
feature is distinguishable from not-yet-computed:

- `Orthologs`: add `checked: bool = False` on the container.
- `DeterministicFeatures`: add `paralogs_checked: bool = False` and
  `isoform_topologies_checked: bool = False` (the lists stay bare; sibling flags
  avoid a container-wrapping refactor across all consumers — container-wrapping
  is the alternative if preferred).
- The loader/sweep stamps these `True` once the gene has been processed against
  the upstream source, even when the result is empty.
- Viewer renders "none found (checked)" instead of a blank/placeholder for the
  genuine-absence case.

**Discipline (mandatory for any schema change):** `SurfaceomeRecord` /
`DeterministicFeatures` use `extra="forbid"`, and the live site reads D1 — so
this change must (a) update the TS mirror types + viewer, (b) re-sync D1 in the
**same** change (`scripts/upload_viewer_snapshots_to_d1.py --execute` or a
re-publish), and (c) be checked against the v2 synthesizer prompt for any
schema reference. This sentinel touches every record, so it is sequenced **last**
and is the one cleanly-deferrable piece if we want the data backfill to land
first.

### D. PR note

A note on the PR (and a short `docs/` entry) explaining: the v1→v2 triage-scope
gap, the measured coverage table, the manifest, the single-worker background
backfill, that orthologs/isoforms already carry per-residue topology and
paralogs get it for ≥80% close pairs, and the `ecd_pct_similarity` D1 migration.

## Sequence

1. A (audit/manifest) → get exact per-cohort counts.
2. B4 (D1 `ecd_pct_similarity` migration) — unblocks #47's loader immediately.
3. B1–B3 proof-run: 71 canonical-topology genes end-to-end; verify a record
   renders. Land the PR with tooling + manifest + proof-run + note.
4. B full background sweep (1 worker) for the remaining needs-backfill genes →
   D1, publishing incrementally.
5. C sentinels (after backfill, or deferred to a follow-up).

## Verification

- `bash scripts/check-py.sh` (ruff + ty + compile + pytest) green.
- TS ↔ Pydantic schema sync check + `npx tsc --noEmit` (if §C touches the schema).
- Manifest row counts reconcile with the §"Measured gap" table.
- Spot-check: one backfilled gene's `fetch_deterministic_features` returns a
  populated `orthologs` / `paralogs` (with close-paralog topology) / isoform
  topology; the loader no longer errors on `ecd_pct_similarity`.
- Idempotency: re-running the sweep on an already-present gene is a no-op.

## Risks

- **D1 ↔ snapshot drift** (CLAUDE.md): any record-shape change must re-sync D1 in
  the same change; never hand-edit a JSON snapshot alone.
- **Managed-agent prompt drift:** v2 prompts don't auto-sync; if §C changes the
  schema the synthesizer references, update its prompt in the same PR.
- **Compute time:** single-worker DeepTMHMM is slow; mitigated by the small
  proof-run gating the PR and the background full run. Exact count from §A keeps
  it bounded.
- **`genuinely-absent` precision:** depends on upstream-source probes (UniProt
  isoform count, Compara ortholog/paralog presence); the two-pass fallback keeps
  it correct even if a probe is unavailable.
