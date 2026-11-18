/**
 * Published cell-surface proteomics studies (S3E8 study compendium).
 *
 * Static files built by `scripts/build/build_surface_proteomics_studies.py`
 * into `public/data/surface-proteomics/`:
 *   - `studies.json` — snapshot provenance + one entry per study arm
 *     (`arms[i]` has index `i`).
 *   - `presence/{NN}.json` — base UniProt accession → symbol, deep-dive flag
 *     and the arm indices it was listed in, sharded by `shardOf`.
 *   - `methods.json` — per-arm methods and source detail, keyed by arm id.
 *
 * Joins are on UniProt accession (isoform suffix stripped), never on symbol.
 * Only `core` / `provisional` arms count as surface detections; the rest are
 * shown but labeled (held, below the reference-overlap screen, a comparator,
 * or another condition of a counted study's samples). Whole-lysate arms are
 * left out of the data entirely.
 */

export type ArmStatus =
  | "core"
  | "provisional"
  | "held"
  | "below_screen"
  | "annotation_selected"
  | "comparator"
  | "perturbed";

/** Every status, in the order the viewer lists them (counted first). */
export const STATUS_ORDER: ArmStatus[] = [
  "core",
  "provisional",
  "held",
  "below_screen",
  "annotation_selected",
  "comparator",
  "perturbed",
];

/** Wording for the sweep-v15 annotation_selected role, verbatim from the S3E8 review. */
export const ANNOTATION_SELECTED_LABEL = "Pre-filtered by surface annotation (shown, not counted)";
/** The same label where a "not counted" marker already sits beside it. */
export const statusShortLabel = (s: ArmStatus) =>
  s === "annotation_selected" ? "Pre-filtered by surface annotation" : STATUS_LABEL[s];
/** The status pill in a table row, where "not counted" and the reason
 *  ("author pre-filtered to …") sit right under it. */
export const statusPillLabel = (s: ArmStatus) =>
  s === "annotation_selected" ? "Pre-filtered" : STATUS_LABEL[s];
export const ANNOTATION_SELECTED_METHODS =
  "Pre-filtered by surface annotation (shown, not counted): the published table was already restricted to proteins annotated or predicted as surface or membrane proteins. Such a table cannot add a candidate or reveal a miss, and it would inflate the share of known surface proteins that the quality screen measures, so it is shown, cited only as support for proteins already in the reference, and never counted.";
/** Added to the held-arm wording with sweep-v15, verbatim. */
export const IMPUTED_NOT_HELD =
  "Imputed values alone do not hold an arm: when every row passed the authors' identification filters, presence in the study is counted (provisional), though per-sample detection is not available.";
export type MethodClass = "intact_cell" | "fractionation";

export interface StudyArm {
  id: string;
  name: string;
  publication: string;
  first_author: string | null;
  /** "George et al. 2026", "A and B 2020" or "A 2020" (surname only), built
   *  from the PubMed author list; "et al." when the author count is unknown. */
  citation?: string | null;
  n_authors?: number | null;
  year: number | null;
  journal: string | null;
  title: string | null;
  pmid: string | null;
  doi: string | null;
  family: string;
  family_label: string;
  method_class: MethodClass;
  intact_cell_labeling: "yes" | "no";
  intact_cell_verified: boolean;
  sample: string | null;
  status: ArmStatus;
  /** For a `perturbed` arm: the arm whose baseline samples it departs from,
   *  the condition ("replicative senescence, …") and its class
   *  ("senescence", "infection", "genetic perturbation", …). */
  parent?: string | null;
  condition?: string | null;
  perturbation?: string | null;
  /** Why this dataset isn't Core ("author pre-filtered to …", "values are
   *  imputed …"); null for Core. Derived in the build, not free text. */
  status_reason?: string | null;
  admitted: boolean;
  n_proteins: number;
  reference_overlap: number | null;
  repository: string | null;
  repository_ids: string[];
  /** Where the raw instrument files are, from the S3E8 raw-data audit
   *  (an arm split from a parent study uses the parent's row). */
  raw_data?: RawData | null;
  /** This arm's tab in the shared study workbook (StudyIndex.study_list). */
  sheet_tab?: string | null;
  /** Curated cell-type group (CELL_GROUPS in the build script). */
  cell_group?: CellGroup;
  /** Cell-line names, for atlases whose table has one column per line. */
  lines?: string[];
  /** The dataset's own quantity measure (e.g. "LFQ intensity"), when it has one. */
  quant_unit?: string;
  /** How the per-protein value is summarized ("mean over the samples …"). */
  quant_note?: string;
  /** Proteins with a value, the denominator of the percentile. */
  n_quantified?: number;
}

export type CellGroup =
  | "blood_cancer"
  | "solid_cancer"
  | "immune"
  | "neural"
  | "stem_stromal"
  | "other_normal"
  | "multi";

export const CELL_GROUP_ORDER: CellGroup[] = [
  "blood_cancer",
  "solid_cancer",
  "immune",
  "neural",
  "stem_stromal",
  "other_normal",
  "multi",
];

export const CELL_GROUP_LABEL: Record<CellGroup, string> = {
  blood_cancer: "Blood cancers",
  solid_cancer: "Solid tumors",
  immune: "Immune cells",
  neural: "Neural cells",
  stem_stromal: "Stem & stromal",
  other_normal: "Other normal cells",
  multi: "Multi-cell-type atlases",
};

export interface StudyIndex {
  generated_at: string;
  snapshot: string;
  source: string;
  n_shards: number;
  n_arms: number;
  n_publications: number;
  n_admitted_arms: number;
  n_admitted_publications: number;
  n_accessions: number;
  n_accessions_admitted: number;
  /** Registry ids the snapshot split into several arms → those arm ids. */
  aliases?: Record<string, string[]>;
  /** The shared study workbook: one tab per study arm. */
  study_list?: { name: string; url: string };
  /** counted_detection_hist[k] = proteins detected in exactly k counted arms (k >= 1). */
  counted_detection_hist?: number[];
  /** Same over the deep-dived cohort including k = 0: "all" plus one per tier. */
  cohort_detection_hist?: Record<string, number[]>;
  /** Surface-preference provenance and validation (see the build script). */
  surface_preference?: {
    reference: string;
    min_surface_values: number;
    min_membrane_values: number;
    n_scored: number;
    auroc_canonical_vs_low_or_not: { vs_procan?: number; vs_membrane?: number };
  };
  /** Whole-lysate arms left out of the published data. */
  excluded_arms?: string[];
  arms: StudyArm[];
}

export interface PresenceEntry {
  /** Display symbol (may be empty when no catalog row exists). */
  s: string;
  /** 1 when the accession has a deep-dive gene page. */
  d: 0 | 1;
  /** Indices into `StudyIndex.arms`. */
  a: number[];
  /** HGNC approved full name, when HGNC cross-references the accession. */
  n?: string;
  /** How many of the five source databases list it (catalog `n_sources`). */
  v?: number;
  /** Deep-dive tier (the catalog's `deep_dive_tier`), deep-dived proteins only. */
  t?: TierCode;
  /** Per-line detection for atlases with `lines`: arm index → line indices. */
  l?: Record<string, number[]>;
  /** Quantity: arm index → [value in the arm's quant_unit, percentile 0-100
   *  within that arm]. Values aren't comparable across arms; percentiles are. */
  q?: Record<string, [number, number]>;
  /** Surface preference: [median percentile in counted surface datasets,
   *  median in membrane-fraction datasets or null, ProCan whole-proteome
   *  percentile or null]. Present only with enough quantified surface data. */
  p?: [number, number | null, number | null];
  /** ProCan whole-proteome percentile (any protein ProCan quantifies). */
  w?: number;
  /** Median percentile across membrane-fraction datasets (needs 3). */
  m?: number;
}

export type PresenceShard = Record<string, PresenceEntry>;

const BASE = "/data/surface-proteomics";

export const STATUS_LABEL: Record<ArmStatus, string> = {
  core: "Core",
  provisional: "Provisional",
  held: "Held",
  below_screen: "High background",
  annotation_selected: ANNOTATION_SELECTED_LABEL,
  comparator: "Comparator",
  perturbed: "Other condition",
};

export const STATUS_HELP: Record<ArmStatus, string> = {
  core: "Core: intact-cell labeling, and at least 20% of the list are Canonical or Likely Surfaceome proteins. Counts as surface evidence.",
  provisional:
    "Provisional: intact-cell labeling that passes with a caveat: it sits within 2 points below the 20% screen (18–20%), it was built from a partial author export, or its values are imputed (presence counted, per-sample detection not available). Counts as surface evidence.",
  held: "Held: the published table can't yet tell us which proteins were detected, for example conditions are pooled with no separable baseline. Listed, not counted.",
  below_screen:
    "High background: intact-cell labeling, but fewer than 20% of the list are Canonical or Likely Surfaceome proteins, so it is mostly intracellular contamination. Listed, not counted.",
  annotation_selected: ANNOTATION_SELECTED_METHODS,
  comparator:
    "Comparator: membrane fractionation, or labeling that reaches the inner side of the membrane. Shows a protein is on a membrane, not that it faces outward. Not counted.",
  perturbed:
    "Other condition: the same study's samples after a change of state, such as senescence, infection, a knockout, a drug or a disease. Each study counts only its baseline (untreated, wild-type or healthy) samples; this list shows what was detected in the other condition. Listed, never counted.",
};

/**
 * One-line meaning of each status, for the Status ⓘ. Rules from the S3E8
 * study (deliverome-analysis, s3e8-cross-method-surfaceome: README,
 * CALIBRATED_INCLUSION.md, FRACTIONATION.md).
 */
export const STATUS_DEFINITION: Record<ArmStatus, string> = {
  core: "Counted. Intact-cell labeling, and at least 20% of its proteins are known surface proteins (Canonical or Likely).",
  provisional:
    "Counted, with the caveat shown next to it: it falls within 2 points below 20%, it is a partial export, or its values are imputed (presence counted, per-sample detection not available).",
  held: "Shown, not counted until a data problem is resolved, such as pooled conditions or an unpublished sample map; the reason is shown next to it.",
  below_screen:
    "Shown, not counted: too few of its proteins are known surface proteins (under 20%, or under the higher bar for a pre-filtered list).",
  annotation_selected:
    "The published table was already restricted to proteins annotated or predicted as surface or membrane proteins; shown, never counted.",
  comparator:
    "Shown for comparison, never counted: membrane fractionation, or labeling that reaches inside the cell, can't show a protein faces outward.",
  perturbed:
    "Shown, never counted: a non-baseline condition (senescent, infected, knockout, treated or diseased samples) of a study whose baseline list is shown separately.",
};

export const METHOD_CLASS_LABEL: Record<MethodClass, string> = {
  intact_cell: "Intact-cell labeling",
  fractionation: "Membrane fractionation",
};

/** Viewer route of the study explorer (linked from deliverome.org's Open Data menu). */
export const STUDIES_PATH = "/surface-proteomics/";

export function studyHref(armIds: string[]): string {
  return armIds.length ? `${STUDIES_PATH}?arm=${armIds.map(encodeURIComponent).join(",")}` : STUDIES_PATH;
}

/** Surface-reference overlap a counted intact-cell arm must reach (the S3E8 screen). */
export const OVERLAP_SCREEN = 0.2;
/** S3E8 admits an intact-cell list up to this many points below the screen, as Provisional only. */
export const OVERLAP_ALLOWANCE_PTS = 2;

export type TierCode = "canonical" | "likely" | "low" | "uncertain" | "no";

export const TIER_LABEL: Record<TierCode | "none", string> = {
  canonical: "Canonical",
  likely: "Likely",
  low: "Low confidence",
  uncertain: "Uncertain",
  no: "Not surface",
  none: "Not deep-dived",
};

export function tierOf(e: PresenceEntry): TierCode | "none" {
  return e.t ?? "none";
}

export const TIER_ORDER: (TierCode | "none")[] = ["canonical", "likely", "low", "uncertain", "no", "none"];

export const TIER_HELP: Record<TierCode | "none", string> = {
  canonical:
    "Our high-confidence surface shortlist: the deep dive found direct evidence that the protein sits on the cell surface and is reachable from outside.",
  likely:
    "Surface on broader evidence than Canonical: accessible, but with a caveat such as a mostly intracellular pool or surface display only in some cell states.",
  low: "Below the Likely bar: the deep dive rated surface accessibility low or moderate, or the evidence is too thin for a shortlist.",
  uncertain: "The deep dive could not settle whether the protein reaches the surface.",
  no: "The deep dive judged the protein not accessible at the cell surface.",
  none: "No deep-dive record: our triage step did not put this protein forward as a surface candidate, so it has no gene page.",
};

/** "A", "B", … "Z", "AA" — short handles for selected studies in a comparison. */
export function letter(i: number): string {
  let s = "";
  let n = i;
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

/**
 * Where a protein detected in `k` counted datasets ranks among every protein
 * any counted dataset detected: the share with fewer detections, and the
 * median count. Null when the histogram is missing or `k` is 0.
 */
export function countedRank(
  hist: number[] | undefined,
  k: number,
): { below: number; total: number; median: number } | null {
  if (!hist || k < 1) return null;
  const total = hist.reduce((s, x) => s + x, 0);
  if (!total) return null;
  const below = hist.slice(1, k).reduce((s, x) => s + x, 0);
  let acc = 0;
  let median = 1;
  for (let i = 1; i < hist.length; i++) {
    acc += hist[i];
    if (acc >= total / 2) {
      median = i;
      break;
    }
  }
  return { below: below / total, total, median };
}

/** Share of a histogram (indexed by detection count, k = 0 included) strictly below `k`. */
export function shareBelow(hist: number[] | undefined, k: number): { below: number; total: number } | null {
  if (!hist) return null;
  const total = hist.reduce((s, x) => s + x, 0);
  if (!total) return null;
  return { below: hist.slice(0, k).reduce((s, x) => s + x, 0) / total, total };
}

export type RawFlag =
  | "raw_public"
  | "raw_private_or_embargoed"
  | "processed_only"
  | "accession_invalid"
  | "raw_not_deposited";

export interface RawData {
  flag: RawFlag;
  repository?: string;
  accessions?: string[];
  url?: string;
}

/** Short wording for each raw-data audit flag. */
export const RAW_FLAG_LABEL: Record<RawFlag, string> = {
  raw_public: "raw files",
  raw_private_or_embargoed: "raw files, not yet released",
  processed_only: "processed files only, no raw files",
  accession_invalid: "printed accession doesn't resolve",
  raw_not_deposited: "raw data not deposited",
};

/** Labeling chemistry families, each with its own chip color. */
export const FAMILY_ORDER = [
  "biotin-amine",
  "glycoprotein-capture",
  "glycopeptide-capture",
  "peroxidase-proximity",
  "other-chemoproteomic",
  "membrane-fractionation",
] as const;

/** Whole-compendium downloads written by the build. */
export const DOWNLOADS = {
  matrix: `/data/surface-proteomics/surface_proteomics_matrix.tsv`,
  datasets: `/data/surface-proteomics/surface_proteomics_datasets.tsv`,
  methods: `/data/surface-proteomics/surface_proteomics_methods.tsv`,
};

/** One source table. Linked only through a public URL (or the page it was
 *  downloaded from); otherwise the reader goes through the paper or deposit. */
export interface SourceFile {
  file?: string;
  sheet?: string | number;
  /** Archive (and nested archives) the file was read from. */
  archive?: string;
  url?: string;
  page?: string;
  repository_path?: string;
  /** Tables this one was rebuilt from, when it is a derived table. */
  derived_from?: SourceFile[];
  derivation?: string;
  note?: string;
  sha256?: string;
}

export interface SampleGroup {
  cell_type?: string;
  condition?: string;
  columns: string[];
  scale?: string;
  min_observed?: number;
  detection_floor?: number;
  replicate_kind?: string;
  use_for_membership?: boolean;
}

export interface Extraction {
  file?: string;
  accession_column?: string;
  gene_column?: string;
  filters?: string[];
  sample_groups?: SampleGroup[];
}

/** Per-arm methods and source detail (methods.json, keyed by arm id). */
export interface ArmMethods {
  method?: string;
  method_source?: string;
  beads?: string;
  lot?: string;
  instrument?: string;
  instrument_detail?: string;
  instrument_source?: string;
  cell_or_tissue?: string;
  sample_scope?: string;
  source_files?: SourceFile[];
  extractions?: Extraction[];
  parent_study?: string;
  annotation_filter?: string;
  filter_universe?: string;
  n_total_ids?: number;
  n_in_reference?: number;
  overlap_cutoff?: number;
  borderline_margin?: number;
  rationale?: string;
  target_species?: string;
  species_note?: string;
  n_species_excluded?: number;
  n_species_unresolved?: number;
}

/** "11,900" / "0.042" / "23.4": a value at three significant figures, readable. */
export function formatQuant(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e6) return v.toExponential(2).replace("e+", "e");
  if (a >= 100) return Math.round(v).toLocaleString("en-US");
  return Number(v.toPrecision(3)).toString();
}

/** "92nd percentile". */
export function ordinalPct(p: number): string {
  const teen = p % 100 >= 11 && p % 100 <= 13;
  const suffix = teen ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[p % 10] ?? "th";
  return `${p}${suffix} percentile`;
}

export type PrefVerdict = "enriched" | "carryover" | "unclear";

/** Surface minus each reference (percentile points), their mean, and a verdict:
 *  at least +10 = surface-enriched, at most -10 = intracellular-carryover pattern. */
export function surfacePreference(p: PresenceEntry["p"]): {
  vsProcan: number | null;
  vsMembrane: number | null;
  mean: number | null;
  verdict: PrefVerdict | null;
} {
  if (!p) return { vsProcan: null, vsMembrane: null, mean: null, verdict: null };
  const [surf, membrane, procan] = p;
  const vsProcan = procan == null ? null : surf - procan;
  const vsMembrane = membrane == null ? null : surf - membrane;
  const parts = [vsProcan, vsMembrane].filter((x): x is number => x != null);
  const mean = parts.length ? Math.round(parts.reduce((a, b) => a + b, 0) / parts.length) : null;
  const verdict =
    mean == null ? null : mean >= 10 ? "enriched" : mean <= -10 ? "carryover" : "unclear";
  return { vsProcan, vsMembrane, mean, verdict };
}

export const PREF_LABEL: Record<PrefVerdict, string> = {
  enriched: "Surface-enriched",
  carryover: "Intracellular carryover pattern",
  unclear: "No clear difference",
};

export function isCounted(arm: StudyArm): boolean {
  return arm.status === "core" || arm.status === "provisional";
}

/**
 * The counting rule a page applies. By default it is `isCounted`: each study
 * counts only its baseline samples. A reader can opt in to also counting the
 * other conditions (senescent, infected, knockout, treated, diseased), and
 * then an other-condition arm counts only when its baseline arm is counted,
 * so the same lab, method and quality screen stand behind it. Other
 * conditions of held, high-background or comparator studies never count.
 */
export function countingRule(
  arms: readonly StudyArm[],
  includeOther: boolean,
): (arm: StudyArm) => boolean {
  if (!includeOther) return isCounted;
  const byId = new Map(arms.map((a) => [a.id, a]));
  return (arm) => {
    if (isCounted(arm)) return true;
    if (arm.status !== "perturbed" || !arm.parent) return false;
    const parent = byId.get(arm.parent);
    return parent ? isCounted(parent) : false;
  };
}

/** Other-condition arms that would count with the opt-in (their baseline is counted). */
export function countableOtherConditions(arms: readonly StudyArm[]): StudyArm[] {
  const counts = countingRule(arms, true);
  return arms.filter((a) => a.status === "perturbed" && counts(a));
}

/** URL parameter that turns the opt-in on (`?oc=1`), shared by the study
 *  table and the gene-page link into it. */
export const INCLUDE_OTHER_PARAM = "oc";

export const INCLUDE_OTHER_LABEL = "Also count other conditions";

/** Why the opt-in is off by default, for the toggle's tooltip. */
export function includeOtherHelp(nCountable: number, nOther: number): string {
  return (
    `Off by default. Each study counts only its baseline samples (untreated, wild-type or healthy cells). ` +
    `Switching this on also counts the same studies' other conditions, such as senescent, infected, knockout, ` +
    `drug-treated, differentiated or diseased samples, but only where the study's baseline dataset is itself counted: ` +
    `${nCountable} of the ${nOther} other-condition datasets qualify. Other conditions of held, high-background or ` +
    `comparator studies stay uncounted. The totals at the top of the Surface proteomics page are always baseline-only.`
  );
}

export function baseAccession(acc: string): string {
  return acc.trim().split("-")[0].toUpperCase();
}

/** Must match `shard_of` in scripts/build/build_surface_proteomics_studies.py. */
export function shardOf(acc: string, nShards: number): number {
  let h = 0;
  for (let i = 0; i < acc.length; i++) {
    h = (h * 31 + acc.charCodeAt(i)) % 1_000_003;
  }
  return h % nShards;
}

export function paperUrl(arm: StudyArm): string | null {
  if (arm.pmid) return `https://pubmed.ncbi.nlm.nih.gov/${arm.pmid}/`;
  if (arm.doi) return `https://doi.org/${arm.doi}`;
  return null;
}

/** Landing page for a ProteomeXchange / MassIVE / jPOST / PRIDE accession, or null. */
export function repositoryUrl(id: string): string | null {
  const v = id.trim();
  if (/^R?PXD\d+$/.test(v)) return `https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=${v}`;
  if (/^MSV\d+$/.test(v)) return `https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=${v}`;
  if (/^JPST\d+$/.test(v)) return `https://repository.jpostdb.org/entry/${v}`;
  return null;
}

/** How the viewer names a study: "George et al. 2026", surname only. */
export function shortCitation(arm: StudyArm): string {
  if (arm.citation) return arm.citation;
  // Older studies.json without `citation`: drop the initials, assume "et al.".
  const surname = (arm.first_author ?? "").trim().replace(/\s+[A-Z]{1,4}$/, "");
  return surname ? [`${surname} et al.`, arm.year].filter(Boolean).join(" ") : arm.name;
}

let _index: Promise<StudyIndex> | null = null;
const _shards = new Map<number, Promise<PresenceShard>>();

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return (await r.json()) as T;
}

export function loadStudyIndex(): Promise<StudyIndex> {
  if (!_index) {
    _index = getJson<StudyIndex>(`${BASE}/studies.json`).catch((e) => {
      _index = null;
      throw e;
    });
  }
  return _index;
}

export function loadShard(i: number): Promise<PresenceShard> {
  let p = _shards.get(i);
  if (!p) {
    const key = String(i).padStart(2, "0");
    p = getJson<PresenceShard>(`${BASE}/presence/${key}.json`).catch((e) => {
      _shards.delete(i);
      throw e;
    });
    _shards.set(i, p);
  }
  return p;
}

let _methods: Promise<Record<string, ArmMethods>> | null = null;

/** Methods and source detail for every arm (~0.8 MB), loaded on first open. */
export function loadMethods(): Promise<Record<string, ArmMethods>> {
  if (!_methods) {
    _methods = getJson<Record<string, ArmMethods>>(`${BASE}/methods.json`).catch((e) => {
      _methods = null;
      throw e;
    });
  }
  return _methods;
}

/** Arm indices an accession was listed in (empty when never listed). */
export async function loadPresence(acc: string): Promise<{ index: StudyIndex; entry: PresenceEntry | null }> {
  const index = await loadStudyIndex();
  const base = baseAccession(acc);
  const shard = await loadShard(shardOf(base, index.n_shards));
  return { index, entry: shard[base] ?? null };
}

/** Every accession, for the studies explorer. ~1.4 MB across all shards. */
export async function loadAllPresence(): Promise<PresenceShard> {
  const index = await loadStudyIndex();
  const shards = await Promise.all(
    Array.from({ length: index.n_shards }, (_, i) => loadShard(i)),
  );
  return Object.assign({}, ...shards) as PresenceShard;
}
