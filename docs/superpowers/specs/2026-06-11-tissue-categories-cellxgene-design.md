# Tissue-category coloring for the CellxGene tissue barplot

## Problem

The CellxGene tissue-axis barplot (PR #68, `claude/vigilant-borg-50c490`) renders all 56 UBERON tissues as bars of a single teal color (`--teal-mid`). A reader cannot tell at a glance whether the gene's expression footprint is lymphoid-heavy, reproductive-heavy, GI-heavy, or anywhere in between — every bar reads the same regardless of what body system it represents.

Coloring each bar by its tissue's organ system makes the per-gene shape of expression immediately legible: a B-cell-receptor gene's bars cluster on lymphoid colors; a kidney-enriched gene shows urinary tones; a broadly-expressed gene shows a rainbow.

## Source of the grouping

A live D1 probe (this session) found **56 unique UBERON tissues** across 19,308 genes in `czi_cellxgene_enrichment`. OLS hierarchical-ancestor walks gave organ-system parents for 40 of them; the remaining 16 (anatomical regions like `abdomen`/`head`, tissue layers like `mucosa`/`lamina propria`, secretions like `saliva`/`milk`/`CSF`, and dev terms like `embryo`/`yolk sac`) are hand-bucketed.

## The 14 categories (canonical map)

| # | id | label | UBERON IDs |
|---|---|---|---|
| 1 | `cns` | CNS | UBERON:0000955 brain · UBERON:0002240 spinal cord · UBERON:0001851 cortex |
| 2 | `head_sensory` | Head & sensory | UBERON:0000970 eye · UBERON:0000004 nose · UBERON:0001723 tongue · UBERON:0000403 scalp · UBERON:0000033 head · UBERON:0000974 neck |
| 3 | `respiratory` | Respiratory | UBERON:0002048 lung · UBERON:0000977 pleura · UBERON:0001443 chest · UBERON:0016435 chest wall |
| 4 | `cardiovascular` | Cardiovascular | UBERON:0000948 heart · UBERON:0002049 vasculature |
| 5 | `lymphoid` | Lymphoid & blood | UBERON:0000178 blood · UBERON:0002371 bone marrow · UBERON:0000029 lymph node · UBERON:0002106 spleen |
| 6 | `digestive` | Digestive (GI) | UBERON:0001043 esophagus · UBERON:0007650 esophagogastric junction · UBERON:0000945 stomach · UBERON:0000344 mucosa · UBERON:0001155 colon · UBERON:0000160 intestine · UBERON:0000059 large intestine · UBERON:0002108 small intestine · UBERON:0000030 lamina propria |
| 7 | `hepatobiliary_pancreas` | Hepatobiliary & pancreas | UBERON:0002107 liver · UBERON:0002110 gallbladder · UBERON:0001264 pancreas |
| 8 | `urinary` | Urinary | UBERON:0002113 kidney · UBERON:0000056 ureter · UBERON:0001255 urinary bladder · UBERON:0018707 bladder organ |
| 9 | `endocrine` | Endocrine | UBERON:0002369 adrenal gland |
| 10 | `reproductive` | Reproductive | UBERON:0000310 breast · UBERON:0003889 fallopian tube · UBERON:0000992 ovary · UBERON:0001987 placenta · UBERON:0000995 uterus · UBERON:0002367 prostate gland · UBERON:0000473 testis |
| 11 | `skin_adipose` | Skin & adipose | UBERON:0001013 adipose tissue · UBERON:0009472 axilla · UBERON:0002097 skin of body |
| 12 | `musculoskeletal` | Musculoskeletal | UBERON:0002102 forelimb · UBERON:0002103 hindlimb · UBERON:8480009 tendon of semitendinosus |
| 13 | `developmental` | Developmental | UBERON:0000922 embryo · UBERON:0001040 yolk sac |
| 14 | `fluids_other` | Fluids / other | UBERON:0001359 cerebrospinal fluid · UBERON:0001913 milk · UBERON:0001836 saliva · UBERON:0000916 abdomen · UBERON:0003688 omentum |

Any UBERON ID not in this map falls back to `fluids_other` — this gracefully absorbs new tissues if CZI's next Census release introduces new UBERON terms, without breaking the chart.

## Palette

Deliverome's design tokens give 12 distinct color slots (4 families × 3-4 tones). 14 categories need 2 new tokens. Final assignment:

| Category | Token |
|---|---|
| CNS | `--lavender-mid` |
| Head & sensory | `--lavender-deepest` |
| Respiratory | `--teal-mid` |
| Cardiovascular | `--maroon-mid` |
| Lymphoid & blood | `--amber-mid` |
| Digestive | `--teal-mid-lt` |
| Hepatobiliary & pancreas | `--amber-deepest` |
| Urinary | `--teal-deepest` |
| Endocrine | `--endocrine-mid` (new — sage / olive #6b8e4e) |
| Reproductive | `--maroon-deepest` |
| Skin & adipose | `--skin-mid` (new — terracotta / clay #b8704a) |
| Musculoskeletal | `--muted-soft` |
| Developmental | `--lavender-tint` |
| Fluids / other | `--line-soft` |

Sage/olive and terracotta are picked to read distinctly from all four primary families while staying tonally in the deliverome palette (warm earth tones; no neon).

## Architecture

### New file: `viewer/lib/tissue-categories.ts`

A pure data + lookup module. No React, no fetch.

```ts
export type TissueCategoryId =
  | "cns" | "head_sensory" | "respiratory" | "cardiovascular"
  | "lymphoid" | "digestive" | "hepatobiliary_pancreas" | "urinary"
  | "endocrine" | "reproductive" | "skin_adipose" | "musculoskeletal"
  | "developmental" | "fluids_other";

export interface TissueCategory {
  id: TissueCategoryId;
  label: string;          // human-readable, used in legend + tooltip
  colorVar: string;       // CSS var name like "--lavender-mid"
  colorFallback: string;  // hex fallback for environments without design-tokens.css
}

export const TISSUE_CATEGORIES: readonly TissueCategory[] = [/* 14 entries, ordered */];

// 56 UBERON IDs → category id, hand-curated from UBERON ancestry walk.
export const UBERON_TO_CATEGORY: Readonly<Record<string, TissueCategoryId>> = {/* ... */};

export function tissueCategoryForUberonId(uberonId: string): TissueCategory {
  const id = UBERON_TO_CATEGORY[uberonId] ?? "fluids_other";
  return TISSUE_CATEGORIES.find((c) => c.id === id)!;
}
```

### Edit: `viewer/app/design-tokens.css`

Append two new CSS custom properties under the existing token block:

```css
--endocrine-mid: #6b8e4e;
--skin-mid: #b8704a;
```

These mirror the deliverome-internal design system (sage + terracotta) so the cellxgene chart stays palette-consistent with the rest of the viewer.

### Edit: `viewer/components/surfaceome/CellxGeneCard/CellxGeneChart.tsx`

Two narrow changes inside the tissue-axis render path (around line 432):

1. Replace uniform `TISSUE_BAR_COLOR` with `tissueCategoryForUberonId(r.uberon_id)`-driven color. Selected-bar color stays maroon for click contrast.
2. After the chart, render `<TissueCategoryLegend categories={categoriesPresent} />` when ≥ 2 distinct categories appear in `sorted`.

### New sub-component (same file): `TissueCategoryLegend`

Inline, small. Horizontal flex row of swatch + label chips for the categories present in this gene's tissue view. CSS lives in the existing `CellxGeneCard.module.css`.

## Out of scope (explicitly)

- **Body-figure visualization.** The original ask but pivoted to barplot-only coloring.
- **Backfilling categories onto the legacy LLM `ExpressionCard`.** That card already has its own structure; tissue-category coloring there can come in a follow-up if it helps.
- **Editing the cell-type axis.** The cell-type bars stay uniform maroon. The tissue grouping doesn't apply to CL terms.
- **Migrating to ontology-walked categories at query time.** The 56→14 map is small enough to hardcode; ontology-driven lookup would be over-engineered for this surface.

## Testing

- Unit-test `tissueCategoryForUberonId` for all 56 known IDs + 2 unknown IDs (should return `fluids_other`).
- Visual smoke: open the CellxGene tab for 3 genes with distinct expression footprints (EGFR lung-heavy; CD19 lymphoid-heavy; KLK3 reproductive-heavy) and confirm the dominant bars carry the expected color.
- Snapshot the unmapped-fallback case: load a record with a fabricated UBERON ID and confirm bars render as `fluids_other` color rather than crashing.

## Workflow

Implementation lands in `claude/competent-jones-e71f75` (this worktree). After verification, the 1–2 commits get cherry-picked onto `claude/vigilant-borg-50c490` so they ship with PR #68.
