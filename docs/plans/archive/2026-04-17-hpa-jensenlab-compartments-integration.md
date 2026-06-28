# Add HPA + JensenLab COMPARTMENTS to the M1 candidate-universe merge

**Date:** 2026-04-17
**Scope:** Extend `data/processed/candidate_universe/candidate_universe.tsv` from 5 → 7 sources.
**Status:** Proposed. No code written yet — review before implementation.

## Motivation

M1 currently merges five sources (UniProt query, GO GAF, SURFY, CSPA, DeepTMHMM). Adding two more gives the candidate universe independent evidence that's underweighted today:

- **Human Protein Atlas (HPA)** — antibody-based immunofluorescence (IF) subcellular localization across ~13.6k human genes, with explicit `Extracellular location` and `Plasma membrane` categories plus a curator-reviewed reliability tier. HPA is also the only source whose evidence is experimental, orthogonal to sequence/topology signals (SURFY, DeepTMHMM) and mass-spec surfaceome capture (CSPA).
- **JensenLab COMPARTMENTS** — a unified subcellular-localization database that integrates four evidence channels (knowledge / experiments / text-mining / predictions) into a per-term `0–5` star confidence score, keyed on GO cellular-component terms. Adds textmining breadth and prediction-tool triangulation we don't otherwise ingest.

These sources have known redundancy with each other and with existing sources; the design below handles that explicitly so we don't silently double-count evidence.

## Data sources — discovered by direct inspection (`curl -sI`, head -5)

### HPA

| File | URL | Version | Size | Last-Modified |
|---|---|---|---|---|
| `subcellular_location.tsv.zip` | https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip | v25.0 | ~250 KB zipped | 2025-11-06 |
| `proteinatlas.tsv.zip` (optional) | https://www.proteinatlas.org/download/proteinatlas.tsv.zip | v25.0 | much larger | — |

Schema of `subcellular_location.tsv` (14 columns, 13,603 data rows):

```
Gene                          Ensembl gene ID (ENSG...)
Gene name                     HGNC symbol
Reliability                   {Enhanced, Supported, Approved, Uncertain}
Main location                 semicolon-separated location list
Additional location           semicolon-separated location list
Extracellular location        semicolon-separated (key column for surface)
Enhanced                      locations at "Enhanced" reliability
Supported                     locations at "Supported" reliability
Approved                      locations at "Approved" reliability
Uncertain                     locations at "Uncertain" reliability
Single-cell variation intensity
Single-cell variation spatial
Cell cycle dependency
GO id                         "Cell Junctions (GO:0030054);Cytosol (GO:0005829);..."
```

Identifier is **ENSG**, not UniProt — requires mapping.
License: **CC-BY-SA-3.0** (already tracked in plan's licensing table).

### JensenLab COMPARTMENTS

All files are plain TSV with no header row. Identifier is **ENSP (Ensembl protein)** with the HGNC symbol carried alongside. Schemas confirmed by direct `head -5`:

| File | URL | Size | Columns |
|---|---|---|---|
| `human_compartment_integrated_full.tsv` | https://download.jensenlab.org/human_compartment_integrated_full.tsv | 302 MB | `ensp, symbol, go_id, go_name, integrated_stars` (float 0–5) |
| `human_compartment_knowledge_full.tsv` | https://download.jensenlab.org/human_compartment_knowledge_full.tsv | 66 MB | `ensp, symbol, go_id, go_name, source, evidence_code, stars` |
| `human_compartment_experiments_full.tsv` | https://download.jensenlab.org/human_compartment_experiments_full.tsv | 8.6 MB | `ensp, symbol, go_id, go_name, source, evidence_desc, stars` (**human-only channel; includes HPA rows**) |
| `human_compartment_textmining_full.tsv` | https://download.jensenlab.org/human_compartment_textmining_full.tsv | **850 MB** | `ensp, symbol, go_id, go_name, zscore, stars, url` |
| `human_compartment_predictions_full.tsv` | https://download.jensenlab.org/human_compartment_predictions_full.tsv | 26 MB | `ensp, symbol, go_id, go_name, method, raw, stars` |

License: **CC-BY-4.0**. Updated weekly. Primary citation: Binder et al., *Database* (Oxford), 2014, DOI `10.1093/database/bau012`.

Confidence scale: `★★★★★` (5.0) = highest, `★☆☆☆☆` (1.0) = lowest. Integrated score combines the four channels with a source-benchmarked weighting (published methodology in the 2014 paper).

## Redundancy we have to handle explicitly

Two double-counting risks — spell them out in the plan so we don't trip on them once agreement counts change:

1. **COMPARTMENTS knowledge channel re-ingests GO and UniProt-SubCell.** Using the integrated score as a naive 7th vote would triple-count GO evidence (GO GAF + UniProt query + COMPARTMENTS knowledge). Mitigation: for the surface flag we gate on the **experiments + textmining + predictions** channels only (see "Flag rules" below). The integrated score + knowledge-channel star rating are carried forward as provenance columns, not as independent votes.

2. **COMPARTMENTS experiments channel contains HPA rows verbatim.** Visible in the first 5 rows of the experiments file (`source == "HPA"`). If we ingest HPA directly and also let COMPARTMENTS experiments count as surface evidence, HPA IF would contribute twice. Mitigation: load COMPARTMENTS experiments but **drop `source == "HPA"`** before the per-GO-term aggregation — HPA is already a first-class source.

## Identifier mapping

HPA keys on ENSG; COMPARTMENTS keys on ENSP. Both need to resolve to current UniProt primary accession before the merge.

Two viable strategies; recommend **(a)**:

- **(a) Re-export the UniProt surface-candidate query with `xref_ensembl` and `xref_ensembl_trs`** and build two mapping tables (`ENSG → UniProt primary`, `ENSP → UniProt primary`) from that. Consistent with existing pipeline; no new external dependency. One-to-many and many-to-one cases handled with the same `_normalize_accessions` collapse pattern already in the candidate-universe merge. **Catch:** the UniProt surface query is already pre-filtered — for comprehensive ENSG/ENSP→UniProt mapping we need the full reviewed human proteome's Ensembl xrefs, not just the surface-query subset. So this becomes a new `download_uniprot_ensembl_xrefs.py` that queries `organism_id:9606 AND reviewed:true` with fields `accession,xref_ensembl,xref_ensembl_trs` and emits two long tables.

- **(b) UniProt idmapping file** (`HUMAN_9606_idmapping_selected.tab.gz`, ~1 GB). Authoritative but heavy; duplicates work (a) already does cleanly.

Add to `src/accessible_surfaceome/sources/_support/accession_history.py` (or a new `ensembl_mapping.py`) a `load_ensembl_mapping()` helper that returns `dict[str, list[str]]` for ENSG→UP and ENSP→UP. Mapping ambiguity (one Ensembl ID → multiple reviewed UniProt primaries) reuses the `split_mapping_ambiguous` pattern exactly: duplicate the row onto each primary, set `<source>_split_mapping_ambiguous = 1`, gate the surface flag.

## Per-source surface-flag rules (proposed)

### HPA (`hpa_surface_flag`)

```
hpa_surface_flag = 1 iff any of the following is true (and reliability ≠ "Uncertain"):
  (a) "Extracellular location" is non-empty, OR
  (b) "Plasma membrane" appears in Main location or Additional location, OR
  (c) GO:0005886 (plasma membrane) or GO:0009986 (cell surface) appears in the GO id column
  AND hpa_split_mapping_ambiguous == 0
```

Provenance columns carried forward:
- `hpa_reliability` ∈ {Enhanced, Supported, Approved, Uncertain}
- `hpa_has_extracellular` (bool)
- `hpa_has_plasma_membrane` (bool)
- `hpa_locations` (semicolon-joined string from Main + Additional)
- `hpa_low_confidence_only` = 1 iff reliability == "Uncertain" (mirror of GO's IEA gate)

Rows with reliability == "Uncertain" stay in the merge with `hpa_surface_flag = 0` for provenance, matching the GO / CSPA pattern.

### COMPARTMENTS (`compartments_surface_flag`)

Working set of GO terms treated as "surface":
```
GO:0005886  plasma membrane
GO:0009986  cell surface
GO:0031225  anchored component of membrane
GO:0005887  integral component of plasma membrane
GO:0098552  side of membrane (parent)
GO:0005576  extracellular region
GO:0005615  extracellular space
```

```
compartments_surface_flag = 1 iff
  max(stars) ≥ 3 across {experiments, textmining, predictions} channels
  for any surface GO term (listed above)
  AND compartments_split_mapping_ambiguous == 0
```

Provenance columns:
- `compartments_integrated_stars_max` (float, 0–5; across surface terms; from integrated file)
- `compartments_knowledge_stars_max` (float; knowledge channel — carried but not part of the flag rule to avoid GO double-counting)
- `compartments_experiments_stars_max` (float; HPA rows filtered out)
- `compartments_textmining_stars_max` (float)
- `compartments_predictions_stars_max` (float)
- `compartments_surface_terms` (comma-joined GO IDs that contributed)
- `compartments_low_confidence_only` = 1 iff only stars ≤ 2 from textmining/predictions support it

Threshold `≥ 3` mirrors JensenLab's own default display filter and is their published "moderate-confidence" cutoff. Document the threshold in `flag_rules` and wire it into the pre-publish drift assertion (same pattern as the existing GO/CSPA assertion in [`build_candidate_universe.py:645-661`](../../src/accessible_surfaceome/merge/__init__.py:645)).

## Pipeline changes

### New files

```
scripts/data_collection/
  download_hpa_subcellular_location.py          # fetches subcellular_location.tsv.zip + traceability JSON
  download_jensenlab_compartments.py            # fetches all 5 human TSVs + traceability JSON
  download_uniprot_ensembl_xrefs.py             # new; full reviewed human proteome + ENSG/ENSP xrefs

scripts/data_processing/
  build_hpa.py                                  # unzip + reshape → hpa_human_snapshot.tsv (canonical, keyed on UniProt primary after mapping)
  build_jensenlab_compartments.py               # filter to surface GO terms per channel + collapse to per-ENSP rows → jensenlab_compartments_human_snapshot.tsv
  uniprot_ensembl_mapping.py                    # shared ENSG/ENSP → UniProt primary helper
```

### Edits to `build_candidate_universe.py`

1. Add `_load_hpa()` and `_load_compartments()` following the existing `_load_*` pattern.
2. Add `hpa_surface_flag` and `compartments_surface_flag` to `FLAG_COLUMNS` (flag count goes 5 → 7).
3. `DB_FLAG_COLUMNS` becomes UniProt + GO + SURFY + CSPA + HPA + COMPARTMENTS (6) — DeepTMHMM still the lone ML flag. `ml_only_edge_case` logic unchanged.
4. Extend the pre-publish assertion block to re-derive `hpa_surface_flag` and `compartments_surface_flag` from raw evidence columns + split-ambiguity gate, and add matching `flag_rules` entries to the traceability manifest.
5. Per-source accession-normalization stats (the `accession_normalization` block in the summary JSON) extends to cover the ENSG/ENSP→UniProt mapping step, with its own `<source>_split_mapping_ambiguous` counts.
6. Agreement distribution goes from k-of-5 to **k-of-7**. Update plotting script to match.

### Edits to `scripts/analysis/`

- `plot_candidate_source_agreement.py` — widen the bar / UpSet / pairwise-Jaccard plots to 7 sources. Keep the shared `plotting_config.py` helpers.
- `audit_cross_source_uniprot_ids.py` — classify HPA and COMPARTMENTS input accessions against UniProt 2026_01 history (the rows' mapped primaries after ENSG/ENSP→UP resolution).

### Git LFS

All five COMPARTMENTS TSVs exceed the 10 MB LFS threshold; textmining (850 MB) also exceeds GitHub's 100 MB single-file cap for non-LFS storage. Update `.gitattributes`:

```
data/external/jensenlab_compartments/*.tsv filter=lfs diff=lfs merge=lfs -text
data/external/hpa_subcellular/*.tsv filter=lfs diff=lfs merge=lfs -text
data/external/hpa_subcellular/*.zip filter=lfs diff=lfs merge=lfs -text
```

The 850 MB textmining file is borderline — consider pre-filtering at download time to only rows whose `go_id` is in the surface working set (reduces to <5 MB typical). Recommend filter-at-download for textmining specifically; keep the other four files unfiltered so audit rebuilds stay reproducible.

## Expected changes to headline numbers

Rough prior:

- Candidate-universe row count grows by a few hundred to ~1,000. HPA's ENSG coverage is largely inside the UniProt reviewed proteome; COMPARTMENTS covers essentially every ENSP with any annotation (high breadth, low specificity at the textmining tail).
- `n_sources_surface` distribution re-bucketed k-of-7. The existing `549` five-of-five core is a subset of the new `k ≥ 6` bucket if HPA and COMPARTMENTS both corroborate — expect most of those to land at 6/7 or 7/7.
- New low-k rows: COMPARTMENTS-textmining-only hits with no DB corroboration (these should be visible in a `1/7` bucket dominated by COMPARTMENTS).
- HPA surface-flag count will likely land between 2,500 and 3,500 proteins (HPA's Plasma-membrane+Extracellular population is ~2,800–3,200 in v25 per their humanproteome pages); COMPARTMENTS surface-flag at stars ≥ 3 likely 5,000–6,000.

## Traceability & provenance additions

Every downloaded file emits a `*_traceability.json` alongside the TSV with: source URL, local output path, `retrieved_at` timestamp (UTC), file size, SHA256, reused-vs-downloaded flag. Pattern matches the existing `download_uniprot_accession_history.py`. The main `candidate_universe_traceability.json` gains two entries in `sources` and matching `flag_rules` for the new flags.

## Sanity checks before declaring the extension done

Replicating the rigor bar from the M1 onepager:

1. `build_candidate_universe.py` pre-publish assertion extended; all four gated flag rules (GO, CSPA, HPA, COMPARTMENTS) re-derived from raw evidence and match the emitted flags exactly.
2. `merge_level_collisions.tsv` remains empty after adding the two new sources.
3. `collapse_conflicts.tsv` is re-audited with the ENSG/ENSP → UP collapse steps recorded.
4. Spot-check panel (same HLA + IGHM panel as M1, plus CD19, CD20, EGFR from the plan's positive-control list) — each resolves to a single row with HPA and COMPARTMENTS flags set correctly.
5. HPA `Reliability == Uncertain` rows have `hpa_surface_flag = 0` (mirror GO IEA invariant).
6. COMPARTMENTS rows whose only evidence is knowledge-channel have `compartments_surface_flag = 0` (prevents the GO double-count).
7. COMPARTMENTS experiments rows with `source == "HPA"` are excluded from the experiments aggregation (prevents HPA double-count).
8. Agreement histogram (k-of-7) regenerated; `n_with_all_seven_sources` and `n_with_all_six_db_sources` added to the summary.

## Open questions for reviewer

1. **COMPARTMENTS surface-term set.** Should `GO:0005576` (extracellular region) count as surface? It catches secreted proteins that aren't plasma-membrane-anchored, which may or may not belong in the candidate universe given the M0 plan's distinction between `topology` and `surface_status`. Recommend **no** for v0 — add it later only if v1 expands scope to secreted proteins. Currently leaning toward keeping PM + cell-surface + anchored-component only.
2. **COMPARTMENTS stars threshold.** Pilot `≥ 3` as the default; offer a CLI flag to re-compute at `≥ 2` or `≥ 4` for sensitivity analysis. Pipe the chosen threshold into `flag_rules` (so the manifest drift assertion keeps it honest).
3. **HPA `proteinatlas.tsv.zip`** (the full HPA dump) carries additional fields — "Secretome membership", "Protein class: Predicted membrane proteins", "Protein class: Predicted secreted proteins" — that are essentially HPA's curated answers to the same question. Worth ingesting too? Recommend following up in a second PR once the subcellular-location-only integration lands; avoids scope creep.
4. **Textmining TSV size.** The 850 MB file is unwieldy even on LFS. Filter-at-download to `go_id ∈ surface_terms` is the cleaner choice but makes textmining-only audits (e.g., "was this protein textmined to any non-surface location?") impossible from repo state. Recommend filter-at-download with a clearly documented flag to re-fetch unfiltered when needed.
5. **COMPARTMENTS knowledge channel — usage beyond provenance.** We've excluded it from the flag rule to avoid double-counting GO. Should we instead use it as a *tie-breaker* for borderline rows (flag ambiguous when knowledge-stars disagrees with experiments-stars)? Likely yes for downstream disagreement-spotlight analysis; no for the binary surface flag.

## Suggested sequencing

1. **PR 1 (downloader + mapping infrastructure).** `download_hpa_subcellular_location.py`, `download_jensenlab_compartments.py`, `download_uniprot_ensembl_xrefs.py`, `uniprot_ensembl_mapping.py`, `.gitattributes` + LFS wiring. No pipeline changes. Lands the raw data + mapping infra in the repo.
2. **PR 2 (per-source normalizers).** `build_hpa.py`, `build_jensenlab_compartments.py` emitting canonical `hpa_human_snapshot.tsv` and `jensenlab_compartments_human_snapshot.tsv` in `data/processed/`. Independent of the merge.
3. **PR 3 (merge extension).** Add `_load_hpa`, `_load_compartments`, extend FLAG_COLUMNS, extend pre-publish assertion, extend traceability `flag_rules`. Regenerate summary + figures. This is the headline-numbers-changing PR and should get the same multi-round adversarial review as the accession-reconciliation PR.
4. **PR 4 (plot/audit refresh).** Update `plot_candidate_source_agreement.py` and `audit_cross_source_uniprot_ids.py` for k-of-7.

## Sources referenced

- JensenLab COMPARTMENTS downloads: https://compartments.jensenlab.org/Downloads
- JensenLab COMPARTMENTS about page: https://compartments.jensenlab.org/About
- JensenLab COMPARTMENTS primary citation: Binder et al., *Database* (Oxford), 2014, DOI: [10.1093/database/bau012](https://doi.org/10.1093/database/bau012)
- HPA downloads: https://www.proteinatlas.org/about/download
- HPA subcellular-location schema: https://www.proteinatlas.org/humanproteome/subcellular/data
- File sizes / schemas verified by `curl -sI` and `head -5` on 2026-04-17.
