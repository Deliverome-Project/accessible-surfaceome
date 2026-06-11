/**
 * Cell-type category mapping + colors for the CellxGene tab's barplot.
 *
 * The CZI cell ontology has ~600 terms in the WMG data and ~3,000 in
 * Cell Ontology total. Most are descendants of ~10 broad classes
 * (epithelial / immune / neural / endothelial / stromal / muscle /
 * reproductive / stem / tumor / other) that group naturally on a
 * gene-page barplot. Rather than hand-curate a full CL → category map
 * for thousands of terms — which would rot every Census refresh — we
 * derive the category from the human label via priority-ordered
 * keyword rules. The rules are designed so the FIRST match wins (e.g.
 * "skeletal muscle fibroblast" hits Stromal via "fibroblast" before
 * Muscle via "muscle"); reorder with care.
 *
 * Colors match the deliverome design system (Maroon / Teal / Amber /
 * Lavender + neutrals). Epithelial gets the primary Maroon accent
 * because the surfaceome cohort is biased toward epithelial-context
 * delivery and that's the most-rendered category.
 */

export const CATEGORIES = [
  "Epithelial",
  "Immune",
  "Neural",
  "Endothelial",
  "Stromal",
  "Muscle",
  "Reproductive",
  "Stem",
  "Tumor",
  "Other",
] as const;

export type CellCategory = (typeof CATEGORIES)[number];

interface Rule {
  /** Substring tested against the lowercase cell type label. */
  needle: string;
  category: CellCategory;
}

/**
 * Priority-ordered keyword rules. ORDER MATTERS: first match wins.
 *
 * Examples of order-sensitive resolutions:
 * - "skeletal muscle fibroblast" → Stromal (fibroblast before muscle)
 * - "vascular smooth muscle cell" → Muscle (smooth muscle before endothelial-adjacent)
 * - "alveolar macrophage" → Immune (macrophage before alveolar)
 * - "microglial cell" → Neural? No — Immune. Microglia ARE immune by
 *   CL lineage even though they live in brain.
 */
const RULES: Rule[] = [
  // --- Immune (do these first so e.g. "alveolar macrophage" isn't Epithelial) ---
  { needle: "macrophage", category: "Immune" },
  { needle: "monocyte", category: "Immune" },
  { needle: "dendritic", category: "Immune" },
  { needle: "neutrophil", category: "Immune" },
  { needle: "eosinophil", category: "Immune" },
  { needle: "basophil", category: "Immune" },
  { needle: "mast cell", category: "Immune" },
  { needle: "plasma cell", category: "Immune" },
  { needle: "plasmablast", category: "Immune" },
  { needle: "microglia", category: "Immune" },
  { needle: "microglial", category: "Immune" },
  { needle: "megakaryocyte", category: "Immune" },
  { needle: "platelet", category: "Immune" },
  { needle: "erythrocyte", category: "Immune" },
  { needle: "erythroblast", category: "Immune" },
  { needle: "erythroid", category: "Immune" },
  { needle: "thymocyte", category: "Immune" },
  { needle: "lymphocyte", category: "Immune" },
  { needle: "natural killer", category: "Immune" },
  { needle: "leukocyte", category: "Immune" },
  { needle: "innate lymphoid", category: "Immune" },
  { needle: "t cell", category: "Immune" },
  { needle: "b cell", category: "Immune" },
  { needle: "nk cell", category: "Immune" },
  { needle: "regulatory t", category: "Immune" },
  { needle: "cd4-positive", category: "Immune" },
  { needle: "cd8-positive", category: "Immune" },

  // --- Stem / Progenitor (before broader categories to catch e.g. hematopoietic stem cell) ---
  { needle: "stem cell", category: "Stem" },
  { needle: "progenitor", category: "Stem" },
  { needle: "precursor", category: "Stem" },

  // --- Stromal (before Muscle to catch "skeletal muscle fibroblast", before Endothelial for pericytes) ---
  { needle: "fibroblast", category: "Stromal" },
  { needle: "myofibroblast", category: "Stromal" },
  { needle: "mesenchymal", category: "Stromal" },
  { needle: "pericyte", category: "Stromal" },
  { needle: "stromal", category: "Stromal" },
  { needle: "adipocyte", category: "Stromal" },
  { needle: "chondrocyte", category: "Stromal" },
  { needle: "osteoblast", category: "Stromal" },
  { needle: "osteoclast", category: "Stromal" },

  // --- Muscle ---
  { needle: "cardiomyocyte", category: "Muscle" },
  { needle: "myocyte", category: "Muscle" },
  { needle: "smooth muscle", category: "Muscle" },
  { needle: "skeletal muscle", category: "Muscle" },
  { needle: "myoepithelial", category: "Muscle" },
  { needle: "muscle cell", category: "Muscle" },

  // --- Neural ---
  { needle: "neuron", category: "Neural" },
  { needle: "astrocyte", category: "Neural" },
  { needle: "oligodendrocyte", category: "Neural" },
  { needle: "glia", category: "Neural" },
  { needle: "schwann", category: "Neural" },
  { needle: "ependymal", category: "Neural" },
  { needle: "purkinje", category: "Neural" },
  { needle: "neural", category: "Neural" },
  { needle: "neuro", category: "Neural" },

  // --- Endothelial ---
  { needle: "endothelial", category: "Endothelial" },

  // --- Reproductive ---
  { needle: "trophoblast", category: "Reproductive" },
  { needle: "syncytiotroph", category: "Reproductive" },
  { needle: "oocyte", category: "Reproductive" },
  { needle: "spermat", category: "Reproductive" },
  { needle: "germ cell", category: "Reproductive" },
  { needle: "decidual", category: "Reproductive" },
  { needle: "placental", category: "Reproductive" },

  // --- Tumor ---
  { needle: "malignant", category: "Tumor" },
  { needle: "tumor", category: "Tumor" },
  { needle: "neoplastic", category: "Tumor" },
  { needle: "carcinoma", category: "Tumor" },

  // --- Epithelial (broadest — runs last) ---
  { needle: "alveolar", category: "Epithelial" },
  { needle: "club cell", category: "Epithelial" },
  { needle: "ciliated", category: "Epithelial" },
  { needle: "enterocyte", category: "Epithelial" },
  { needle: "hepatocyte", category: "Epithelial" },
  { needle: "keratinocyte", category: "Epithelial" },
  { needle: "podocyte", category: "Epithelial" },
  { needle: "ionocyte", category: "Epithelial" },
  { needle: "tuft cell", category: "Epithelial" },
  { needle: "goblet", category: "Epithelial" },
  { needle: "secretory", category: "Epithelial" },
  { needle: "acinar", category: "Epithelial" },
  { needle: "ductal", category: "Epithelial" },
  { needle: "epithelial", category: "Epithelial" },
  { needle: "epithelium", category: "Epithelial" },
  { needle: "basal", category: "Epithelial" },
  { needle: "mucus", category: "Epithelial" },
  { needle: "pneumocyte", category: "Epithelial" },
  { needle: "kidney loop", category: "Epithelial" },
  { needle: "tubule", category: "Epithelial" },
];

/** Map a cell-type label to its broad category for the barplot color. */
export function categorize(label: string): CellCategory {
  const s = label.toLowerCase();
  for (const r of RULES) {
    if (s.includes(r.needle)) return r.category;
  }
  return "Other";
}

/**
 * Category → fill color. CSS variables (with hex fallbacks) so the
 * palette tracks the design-tokens.css definitions when those evolve.
 */
export const CATEGORY_COLORS: Record<CellCategory, string> = {
  Epithelial: "var(--maroon-mid, #922038)",
  Immune: "var(--teal-mid, #3d6b60)",
  Neural: "var(--lavender-bright, #8878c8)",
  Endothelial: "var(--azure-mid, #2f6b8e)",
  Stromal: "var(--amber-bright, #f4aa28)",
  Muscle: "var(--paprika, #c45e2a)",
  Reproductive: "var(--rose, #c97a8e)",
  Stem: "var(--moss, #5e8a4a)",
  Tumor: "var(--maroon-dark, #6e1428)",
  Other: "var(--ink-faded, #999999)",
};
