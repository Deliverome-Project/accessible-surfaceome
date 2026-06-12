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
  | "musculoskeletal"
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
 * Max-contrast palette. Each color targets ≥ 30° hue separation from
 * its neighbors and ≥ 0.6 saturation so adjacent bars read as
 * obviously distinct categories rather than "similar teal-ish thing."
 * Mixes lightness on the warm side (cardiac dark, lymphoid bright)
 * and on the cool side (CNS deep, musculoskeletal light) to
 * distinguish hue-pairs by brightness as well.
 */
export const TISSUE_CATEGORIES: readonly TissueCategory[] = [
  // Vivid purple. Deepest purple in the palette by design — the CNS
  // tier feels heavy / weighted.
  { id: "cns", label: "CNS", colorVar: "--vivid-purple", colorFallback: "#6a1bd9" },
  // Near-black indigo — distinct from CNS purple by brightness,
  // not hue (sensory feels weighted by saturation, not color).
  { id: "head_sensory", label: "Head & sensory", colorVar: "--indigo-night", colorFallback: "#0d1457" },
  // Cyan teal — brighter / more saturated than the original muted
  // teal-mid so it doesn't blend into the digestive green next door.
  { id: "respiratory", label: "Respiratory", colorVar: "--cyan-teal", colorFallback: "#1f9e9e" },
  // Crimson red — sharp and saturated. Adjacent to lymphoid orange
  // but distinct by hue+brightness.
  { id: "cardiovascular", label: "Cardiovascular", colorVar: "--crimson", colorFallback: "#d8203e" },
  // Vivid orange — brighter than the previous tangerine so it
  // separates clearly from the crimson on its left.
  { id: "lymphoid", label: "Lymphoid & blood", colorVar: "--vivid-orange", colorFallback: "#f57e1c" },
  // Saturated green — was grass (#4a9a4a), bumped to a brighter
  // chlorophyll green so digestive doesn't mute against respiratory
  // cyan or endocrine olive.
  { id: "digestive", label: "Digestive (GI)", colorVar: "--bright-green", colorFallback: "#2ec044" },
  // Chocolate brown — much darker than skin (peach), creating a
  // brightness contrast between the two warm-earth slots.
  { id: "hepatobiliary_pancreas", label: "Hepatobiliary & pancreas", colorVar: "--chocolate", colorFallback: "#5d2914" },
  // Sapphire blue — deep + saturated, distinct from the head/sensory
  // indigo by hue (more blue, less violet).
  { id: "urinary", label: "Urinary", colorVar: "--sapphire", colorFallback: "#1f3a8a" },
  // Yellow-olive — pushed toward yellow so it's clearly distinct
  // from digestive's bright green and developmental's mustard.
  { id: "endocrine", label: "Endocrine", colorVar: "--yellow-olive", colorFallback: "#9b9a16" },
  // Hot pink — saturated magenta-pink. Distinct from cardiovascular
  // crimson by being magenta-side of red.
  { id: "reproductive", label: "Reproductive", colorVar: "--hot-pink", colorFallback: "#d83a78" },
  // Peach coral — brighter / pinker than the original bronze so it
  // doesn't blend into hepatobiliary's chocolate brown.
  { id: "skin_adipose", label: "Skin & adipose", colorVar: "--peach", colorFallback: "#e89b4a" },
  // Lilac — much lighter than CNS purple, so adjacent purples read
  // as different brightnesses.
  { id: "musculoskeletal", label: "Musculoskeletal", colorVar: "--lilac", colorFallback: "#b69cea" },
  // Bright yellow — pure, saturated, no orange tint. Distinct from
  // endocrine olive and lymphoid orange.
  { id: "developmental", label: "Developmental", colorVar: "--bright-yellow", colorFallback: "#f5c213" },
  // Warm gray-violet — intentionally desaturated so "everything else"
  // doesn't compete with the categorical colors above it.
  { id: "fluids_other", label: "Fluids / other", colorVar: "--warm-gray", colorFallback: "#8a7e8a" },
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
  // 12. Musculoskeletal
  "UBERON:0002102": "musculoskeletal", // forelimb
  "UBERON:0002103": "musculoskeletal", // hindlimb
  "UBERON:8480009": "musculoskeletal", // tendon of semitendinosus
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
