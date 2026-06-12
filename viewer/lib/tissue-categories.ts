/**
 * Tissue organ-system categories for the CellxGene tissue-axis barplot.
 *
 * The CZI Census reports 56 distinct UBERON tissue terms across the human
 * cohort (probed live from D1; see docs/superpowers/specs/2026-06-11-
 * tissue-categories-cellxgene-design.md). Coloring every bar the same teal
 * loses the gene-level expression footprint — a B-cell marker, a kidney-
 * enriched receptor, and a broadly-expressed gene all read identically.
 *
 * This module rolls those 56 tissues up to 14 organ-system / regional
 * categories, each with its own deliverome-palette color. The categories
 * come from UBERON's `is_a` + `part_of` ancestry walk (40/56 mapped via
 * OLS) plus hand-curation for anatomical regions, tissue layers, fluids,
 * and dev-stage terms (the remaining 16). Lookup is a flat
 * dictionary — no runtime ontology calls.
 *
 * Unknown UBERON IDs fall back to `fluids_other` so a new Census release
 * with new tissue terms keeps rendering rather than crashing.
 */

export type TissueCategoryId =
  | "cns"
  | "head_sensory"
  | "respiratory"
  | "cardiovascular"
  | "lymphoid"
  | "digestive"
  | "hepatobiliary_pancreas"
  | "urinary"
  | "endocrine"
  | "reproductive"
  | "skin_adipose"
  | "developmental"
  | "fluids_other";

export interface TissueCategory {
  id: TissueCategoryId;
  label: string;
  /** CSS custom-property name (without the leading `var()`). */
  colorVar: string;
  /** Hex fallback for environments without design-tokens.css loaded. */
  colorFallback: string;
}

/**
 * Display order — used by the legend strip. Roughly anatomical
 * head-to-toe with fluids/dev at the end as "everything else."
 */
/**
 * Palette notes — high-contrast version. Each category gets a hue at
 * least one stop away from its neighbors on the color wheel so 14
 * categories read clearly side-by-side in a bar chart.
 *
 *  - Anchors: deep purple (CNS), saturated teal (respiratory),
 *    crimson (cardiovascular), tangerine (lymphoid), grass (digestive),
 *    rust-brown (hepatobiliary), royal blue (urinary), olive
 *    (endocrine), magenta (reproductive), bronze (skin), bright
 *    purple (musculoskeletal), mustard (developmental), slate (fluids).
 *  - Reds split: cardiovascular is the saturated maroon; reproductive
 *    moves to magenta so two warm reds don't sit next to each other.
 *  - Greens split: digestive is grass green; endocrine is olive; no
 *    more "two teals + a dark teal" cluster.
 *  - Purples: CNS deep, head-and-sensory near-black, musculoskeletal
 *    mid-bright, fluids slate-violet — four distinct purples that
 *    still read as a family.
 */
/**
 * Brand-aligned high-contrast palette. Every color is a deliverome
 * design-token (maroon / teal / amber / lavender + skin + endocrine
 * + muted), distinguished by BRIGHTNESS within each hue family so 14
 * categories still read as distinct adjacent bars.
 *
 * Family allocation:
 *   - Lavender (3): CNS mid · head/sensory deepest · musculoskeletal bright
 *   - Teal (3):     respiratory mid · digestive light · urinary deepest
 *   - Maroon (2):   cardiovascular mid · reproductive light (rose)
 *   - Amber (3):    lymphoid bright · hepatobiliary dark · developmental light
 *   - Endocrine (1): olive
 *   - Skin (1):     warm brown
 *   - Muted (1):    warm gray for "everything else"
 *
 * Stays inside the deliverome editorial palette (no off-brand
 * crimsons / sapphires / hot pinks) while keeping enough brightness
 * separation that the legend and adjacent bars stay readable.
 */
export const TISSUE_CATEGORIES: readonly TissueCategory[] = [
  { id: "cns", label: "CNS", colorVar: "--lavender-mid", colorFallback: "#5848a8" },
  { id: "head_sensory", label: "Head & sensory", colorVar: "--lavender-deepest", colorFallback: "#1e1450" },
  { id: "respiratory", label: "Respiratory", colorVar: "--teal-mid", colorFallback: "#3d6b60" },
  // Cardiovascular: was maroon-mid (#922038). Swapped to amber-mid
  // because the user reserves the deliverome red for the "selected
  // bar" highlight state — having an always-red category competed
  // with that affordance.
  { id: "cardiovascular", label: "Cardiovascular", colorVar: "--amber-mid", colorFallback: "#c07830" },
  { id: "lymphoid", label: "Lymphoid & blood", colorVar: "--amber-bright", colorFallback: "#f4aa28" },
  // Digestive: teal-lt — same family as respiratory but two stops
  // lighter, so they're clearly distinct.
  { id: "digestive", label: "Digestive (GI)", colorVar: "--teal-lt", colorFallback: "#7aab9f" },
  // Hepatobiliary: amber-dark — dark brown, anchors the "warm earth"
  // identity of liver/pancreas. Distinct from skin-mid by saturation.
  { id: "hepatobiliary_pancreas", label: "Hepatobiliary & pancreas", colorVar: "--amber-dark", colorFallback: "#8c4210" },
  // Urinary: teal-deepest — very dark teal, brightness-distinct from
  // respiratory's teal-mid even though same family.
  { id: "urinary", label: "Urinary", colorVar: "--teal-deepest", colorFallback: "#152e28" },
  { id: "endocrine", label: "Endocrine", colorVar: "--endocrine-mid", colorFallback: "#6b8e4e" },
  // Reproductive: was maroon-light. Swapped to lavender-bright since
  // maroon is reserved for the highlighting state. lavender-bright
  // sits in the freed-up slot left by the removed musculoskeletal
  // category, so the purple family is now (CNS, head_sensory,
  // reproductive) instead of (CNS, head_sensory, musculoskeletal).
  { id: "reproductive", label: "Reproductive", colorVar: "--lavender-bright", colorFallback: "#8878c8" },
  { id: "skin_adipose", label: "Skin & adipose", colorVar: "--skin-mid", colorFallback: "#b8704a" },
  // Musculoskeletal: removed. CZI's primary cohort has only ~835
  // cells annotated to UBERON:0001134 (skeletal muscle tissue), too
  // sparse to draw a meaningful category from. The 12 UBERON terms
  // previously here fall to fluids_other.
  // Developmental: amber-light — pale yellow, distinct from lymphoid's
  // amber-bright (more orange-leaning) by hue.
  { id: "developmental", label: "Developmental", colorVar: "--amber-light", colorFallback: "#f4c070" },
  // Fluids / other: muted warm gray — intentionally desaturated so
  // "everything else" doesn't compete with categorical colors.
  { id: "fluids_other", label: "Fluids / other", colorVar: "--muted", colorFallback: "#6f5d5a" },
] as const;

/**
 * 56 UBERON IDs → category. Source: live D1 probe of
 * czi_cellxgene_enrichment (all genes). New unmapped IDs fall back to
 * `fluids_other` via the lookup helper, never crash.
 */
export const UBERON_TO_CATEGORY: Readonly<Record<string, TissueCategoryId>> = {
  // 1. CNS
  "UBERON:0000955": "cns",            // brain
  "UBERON:0002240": "cns",            // spinal cord
  "UBERON:0001851": "cns",            // cortex
  // 2. Head & sensory
  "UBERON:0000970": "head_sensory",   // eye
  "UBERON:0000004": "head_sensory",   // nose
  "UBERON:0001723": "head_sensory",   // tongue
  "UBERON:0000403": "head_sensory",   // scalp
  "UBERON:0000033": "head_sensory",   // head
  "UBERON:0000974": "head_sensory",   // neck
  // 3. Respiratory
  "UBERON:0002048": "respiratory",    // lung
  "UBERON:0000977": "respiratory",    // pleura
  "UBERON:0001443": "respiratory",    // chest
  "UBERON:0016435": "respiratory",    // chest wall
  // 4. Cardiovascular
  "UBERON:0000948": "cardiovascular", // heart
  "UBERON:0002049": "cardiovascular", // vasculature
  // 5. Lymphoid & blood
  "UBERON:0000178": "lymphoid",       // blood
  "UBERON:0002371": "lymphoid",       // bone marrow
  "UBERON:0000029": "lymphoid",       // lymph node
  "UBERON:0002106": "lymphoid",       // spleen
  // 6. Digestive (GI)
  "UBERON:0001043": "digestive",      // esophagus
  "UBERON:0007650": "digestive",      // esophagogastric junction
  "UBERON:0000945": "digestive",      // stomach
  "UBERON:0000344": "digestive",      // mucosa
  "UBERON:0001155": "digestive",      // colon
  "UBERON:0000160": "digestive",      // intestine
  "UBERON:0000059": "digestive",      // large intestine
  "UBERON:0002108": "digestive",      // small intestine
  "UBERON:0000030": "digestive",      // lamina propria
  // 7. Hepatobiliary & pancreas
  "UBERON:0002107": "hepatobiliary_pancreas",  // liver
  "UBERON:0002110": "hepatobiliary_pancreas",  // gallbladder
  "UBERON:0001264": "hepatobiliary_pancreas",  // pancreas
  // 8. Urinary
  "UBERON:0002113": "urinary",        // kidney
  "UBERON:0000056": "urinary",        // ureter
  "UBERON:0001255": "urinary",        // urinary bladder
  "UBERON:0018707": "urinary",        // bladder organ
  // 9. Endocrine
  "UBERON:0002369": "endocrine",      // adrenal gland
  // 10. Reproductive
  "UBERON:0000310": "reproductive",   // breast
  "UBERON:0003889": "reproductive",   // fallopian tube
  "UBERON:0000992": "reproductive",   // ovary
  "UBERON:0001987": "reproductive",   // placenta
  "UBERON:0000995": "reproductive",   // uterus
  "UBERON:0002367": "reproductive",   // prostate gland
  "UBERON:0000473": "reproductive",   // testis
  // 11. Skin & adipose
  "UBERON:0001013": "skin_adipose",   // adipose tissue
  "UBERON:0009472": "skin_adipose",   // axilla
  "UBERON:0002097": "skin_adipose",   // skin of body
  // 12. (Musculoskeletal removed — see note above.) Previous
  // forelimb / hindlimb / tendon UBERONs fall to fluids_other now.
  // 13. Developmental
  "UBERON:0000922": "developmental",   // embryo
  "UBERON:0001040": "developmental",   // yolk sac
  // 14. Fluids / other
  "UBERON:0001359": "fluids_other",    // cerebrospinal fluid
  "UBERON:0001913": "fluids_other",    // milk
  "UBERON:0001836": "fluids_other",    // saliva
  "UBERON:0000916": "fluids_other",    // abdomen
  "UBERON:0003688": "fluids_other",    // omentum
};

const CATEGORY_BY_ID: Readonly<Record<TissueCategoryId, TissueCategory>> =
  Object.fromEntries(TISSUE_CATEGORIES.map((c) => [c.id, c])) as Record<
    TissueCategoryId,
    TissueCategory
  >;

/**
 * Resolve a UBERON ID to its category record. Unknown IDs return the
 * `fluids_other` fallback so chart code can render without crashing.
 */
export function tissueCategoryForUberonId(uberonId: string): TissueCategory {
  const id = UBERON_TO_CATEGORY[uberonId] ?? "fluids_other";
  return CATEGORY_BY_ID[id];
}

/**
 * CSS color string for a UBERON ID: `var(--token, #hex)`. Convenience
 * wrapper around `tissueCategoryForUberonId` for inline style use.
 */
export function tissueCategoryColorFor(uberonId: string): string {
  const cat = tissueCategoryForUberonId(uberonId);
  return `var(${cat.colorVar}, ${cat.colorFallback})`;
}
