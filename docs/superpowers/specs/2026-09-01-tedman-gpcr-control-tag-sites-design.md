# Tedman GPCR HA control tag sites — design

**Date:** 2026-09-01
**Branch:** `claude/gpcr-control-tag-sites-tedman` (off `origin/dev`)
**Author:** Becca Carlson (with Claude)

## Summary

Ingest the experimentally-validated **N-terminal HA epitope-tag insertion sites** for
~766 human GPCRs from **Tedman et al., "Efficient experimental characterization of the
GPCRome via deep receptor scanning"** (Nat Commun 2026, `10.1038/s41467-026-76564-7`;
bioRxiv `2025.09.19.677468`; Mendeley Data `10.17632/3b4n36z4bg`) as a new class of
**control tag sites** in the existing `dev` tag-site subsystem, and surface them in the
viewer — on the canonical protein and on the specific isoforms already carried by the
viewer — with the measured HA-immunostaining surface-expression value attached.

These are the standardized HA control tags whose immunostaining reports plasma-membrane
expression in deep receptor scanning: a validated, non-disruptive extracellular
epitope-insertion position per GPCR — exactly the "accessible surface site" the catalog
exists to record, and directly reusable for engineering tagged/targeting constructs.

## Data sources (two inputs, joined on `SYMBOL_ENST`)

| Datum | Source | Field(s) | Notes |
|---|---|---|---|
| **HA tag position** | Mendeley deposit `Doc S1. GPCR Plasmid Maps/GPCR Library Index Final.xlsx` (DOI `10.17632/3b4n36z4bg`; index xlsx sha256 `574c1c57…`, byte-identical across deposit v1/v2/v3) | `ha_insert_position` ("position 1 is first codon/AA"), `hgnc_symbol`, `uniprot_id`, `ensembl_gene_id`, `ensembl_transcript_id`, `unique_molecular_identifier`, `gpcr_class`, `signal_peptide_topcons`, `alt_isoform?` | 946 plasmids / 766 genes. Between-residue coordinate: `0-1` (=N-terminus before residue 1) for 834; the other 112 shift downstream (e.g. `27-28`) tracking the 98 signal-peptide receptors (tag on the mature N-terminus after SP cleavage). **This coordinate exists nowhere but the plasmid maps.** |
| **Surface expression** | `deliverome-external://tedman-gpcr-surface-screen/2025-09-19/tedman2025_gpcr_screen_media-2.xlsx` (canonical; verified local mirror sha256 `c0fbcbd1…`) | *Canonical* sheet: `Immunostaining Intensity` (+SD), `Receptor Name`, `gene_id`, `Protein Length`. *Isoforms* sheet: `Surface Expression` (+SD), `Canonical Surface Expression`, `% change in PME`. | Read via `deliverome_analysis.s3.external`; documented byte-identical immunostaining cols to the Mendeley `Doc S2. GPCR DRS Master Table.xlsx`, which is the offline fallback if AWS creds are unavailable. |

## Identifier resolution (per the repo's HGNC-ID rule — never bare symbols)

1. **Canonical protein:** resolve each Tedman gene to its canonical `uniprot_acc` + `hgnc_id`
   via `resolve_by_hgnc_id` / the `gene_identifier` table. The xlsx supplies `uniprot_id`,
   `ensembl_gene_id`, `hgnc_symbol` to seed/verify the resolution.
2. **Junction residue:** project `ha_insert_position` (construct-ORF numbering) →
   `junction_after_residue` in **canonical UniProt numbering**, and read `expected_residue`
   (1-letter residue at the junction) from the canonical sequence. For `0-1` this is
   junction 0 (before residue 1). For post-SP constructs, align the construct N-terminus to
   the canonical sequence and validate `expected_residue`; a mismatch is a hard error (the
   row is dropped and logged, never silently mis-placed).
3. **ENST → UniProt isoform** (for per-isoform pins): **no resolver exists.** Match each
   Tedman transcript's protein sequence/length against `record.deterministic_features.
   isoform_topologies[].sequence` for that gene using `merge/isoform_identity.pct_identity`
   (exact length + ~100% identity ⇒ that UniProt isoform accession). Only isoforms already
   present in `isoform_topologies` are eligible (see Isoforms below).

## What gets emitted

### Canonical control tag site — one `TaggedSite` per gene → `viewer/public/tag-sites/{SYMBOL}.json` `sites[]`
- `provenance: "screen_validated"` — **new category** (UI label **"Screen-validated"**).
- `site_kind: "terminal_n"`, `insert_after_residue` = junction (null/0 = before residue 1),
  `extracellular: true`, `compartment: "extracellular"`, `topology_state` "S"/"O".
- `tag_type: "HA"`, `tag_length_aa: 9`.
- Surface expression rides as **free-text in the evidence fields** (per decision):
  `functional_impact_measured` / `rationale` carry e.g. *"Surface immunostaining PME
  5027 ± 342 (HA immunostaining, Tedman deep receptor scanning)."*
- `sources`: Tedman et al. 2026 with **PMID** + DOI + Mendeley DOI (PMID looked up during
  build, per the citation rule).
- `residue_before`/`residue_after`/`residue_label` filled for mechanical verification.

### Per-isoform control pins — `isoform_pins[]` in the same JSON (static-asset-only)
- Emitted **only for isoforms already in `record.isoform_topologies`** (the viewer's
  IsoformsCard rows + 3D variant tabs are built solely from that list; a pin for an absent
  isoform renders nowhere). This is precisely the "isoforms we already have in the viewer"
  scope.
- `isoform_id` = resolved UniProt isoform accession; `isoform_residue` (own axis) +
  `left_pct`; `tag_type: "HA"`; unique `site_id` (`tedman::ha::{isoform_id}`).
- **Model extension:** add a distinguishing marker to `IsoformTagPin` (Python dict + TS) —
  a `classification: "control"` value (widening the current `shared|unique`) plus an
  optional `note` string carrying the isoform PME + `% change in PME`. Thread the pin's real
  provenance/classification through `IsoformsCard.pinsFor` (which currently hardcodes
  `deterministic_computed`).

## New provenance wiring — `screen_validated` (canonical sites)

Durable by construction: `screen_validated ∉ {deterministic_computed, literature_retrieved}`,
so both `regenerate_tag_sites.py` (preserves non-deterministic) and
`regenerate_tag_site_lit.py` (preserves non-`literature_retrieved`) leave it untouched — it
cannot be clobbered by a later deterministic or literature re-run.

Touch points:
- **Python** `src/accessible_surfaceome/tag_sites/model.py` — add `screen_validated` to the
  provenance vocabulary; a curated-site constructor.
- **TS** `viewer/lib/tag-sites-types.ts` — add to `TaggedSiteProvenance`, `tagSiteCategory()`,
  `CATEGORY_HEX/TOKEN/LABEL`, and the overlay `RENDERED` set.
- **Card** `TaggedSitesCard.tsx` — render `screen_validated` (its own "Screen-validated"
  section/badge, alongside literature + computed).
- **Tab gate** `GeneDetail.tsx` — include `screen_validated` in the renderable-sites check.
- **Overlay** `tag-sites-overlay.ts` — include in `RENDERED`; place on TopologyBar + 3D.
- **Design tokens** `viewer/app/design-tokens.css` — add `--tag-site-screen-validated` and
  `--tag-site-isoform-control` (also backfill the never-defined
  `--tag-site-isoform-shared`/`-unique` referenced by `TopologyBar.tsx` — latent gap).
- **Counts (optional)** `tag-site-counts.ts` / `build-tag-site-counts.mjs` — a bucket for the
  new category if we want a catalog filter facet.

## Storage & publish (straight to live)

- **Canonical sites → public D1 + live Worker.** `provenance` is a free-text TEXT column in
  `tag_site_public` — **no schema change.** Run `scripts/sync_tag_sites_to_d1.py --version
  2026-09-01` (replace-all-per-gene) for the ~766 genes, then **purge the edge cache** for
  each affected `/v1/tag-sites/{SYMBOL}` so they go live immediately. Worker `handleTagSites`
  returns all rows unchanged.
- **Isoform pins → static asset only** (not in D1; merged client-side from
  `/tag-sites/{SYMBOL}.json`). They go live when the branch's
  `viewer/public/tag-sites/*.json` is deployed by the Cloudflare Pages build (i.e. on merge
  to `dev`). **So "straight to live" means: canonical sites live via D1 immediately; isoform
  pins live on the next Pages deploy of the branch.** No D1/sync/Worker change for pins.

## Files (new + modified)

**New**
- `scripts/build_tedman_gpcr_controls.py` — join the two sources, resolve IDs, project
  junctions, write `data/tag_sites/tedman_gpcr_controls.tsv` (curated table, committed).
- `scripts/emit_tedman_tag_sites.py` — read the table + per-gene records (isoform_topologies
  + sequences, from the Worker/D1), emit/merge canonical sites + isoform pins into each
  `viewer/public/tag-sites/{SYMBOL}.json` via `emit_tag_sites_json`.
- `data/tag_sites/tedman_gpcr_controls.tsv` (+ `.md` provenance).
- Tests mirroring existing ones (`tests/test_tag_sites_*`): model round-trip of the new
  provenance, emitter merge, isoform-control pin, junction-residue verification.

**Modified** — `tag_sites/model.py`, `viewer/lib/tag-sites-types.ts`,
`viewer/lib/tag-sites-overlay.ts`, `TaggedSitesCard.tsx`, `GeneDetail.tsx`,
`IsoformsCard.tsx` (`pinsFor`), `TopologyBar.tsx` (control color), `design-tokens.css`,
and the ~766 `viewer/public/tag-sites/{SYMBOL}.json` (generated).

## Scope

- **766 GPCRs** (canonical), classes A/B/C/F/Taste/Vomeronasal. Intersect with the cohort;
  report any Tedman gene not in the catalog (expected near-zero — all are surface receptors).
- **Isoform pins** only for the subset of the 105 Tedman-isoform genes whose isoform also
  exists in `isoform_topologies` (report the resolved/unresolved counts).
- Keep the Tedman set in its **own** `tedman_gpcr_controls.tsv` — do NOT bulk-append 766 rows
  into the hand-curated `data/tag_sites/positive_controls.tsv` benchmark file. (The ~5 GPCR
  terminal controls already there — ADRB2, GLP1R, GIPR, CALCR, ADORA1 — overlap Tedman; the
  emitter dedups by `site_id` so no double render.)

## Quality gates

- `bash scripts/check-py.sh` (ruff + ty + pytest); the viewer test suite
  (`viewer/tests/run_tag_sites_tests.sh`, `tagged_sites_card.test.tsx`, overlay/derive tests).
- No prompt change ⇒ no `gen_prompt_review.py` / prompt-leak run needed.
- Spot-check a handful of GPCRs on a local viewer before/after the D1 push.

## Out of scope

- No deterministic-benchmark wiring: Tedman sites are `terminal_n`, which
  `benchmark_tag_sites_all_controls.py` skips by design (the table stays benchmark-ready).
- No new isoforms added to `isoform_topologies` (that's the topology sweep, a different
  subsystem) — pins are limited to isoforms already present.
- The full 947 SnapGene `.dna` maps + FASTA are the provenance source, not shipped to the
  viewer; only the per-gene tag position + PME are surfaced.

## Decisions (resolved with Becca)

1. Deploy: dev branch; results OK in live Worker + public D1.
2. Data model: sites for each GPCR **and** for isoforms already in the viewer.
3. Provenance category: **new**, named **`screen_validated`** / "Screen-validated".
4. Surface expression: **free-text in the site's evidence**.
5. Isoforms: **extend now** for per-isoform control pins.
6. Publish: **straight to live** (canonical via D1 + purge; isoform pins via Pages deploy).
