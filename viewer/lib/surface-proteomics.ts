/**
 * Published cell-surface proteomics studies (S3E8 study compendium).
 *
 * Static files built by `scripts/build/build_surface_proteomics_studies.py`
 * into `public/data/surface-proteomics/`:
 *   - `studies.json` — snapshot provenance + one entry per study arm
 *     (`arms[i]` has index `i`).
 *   - `presence/{NN}.json` — base UniProt accession → symbol, deep-dive flag
 *     and the arm indices it was listed in, sharded by `shardOf`.
 *
 * Joins are on UniProt accession (isoform suffix stripped), never on symbol.
 * Only `core` / `provisional` arms count as surface detections; the rest are
 * shown but labelled (held, below the reference-overlap screen, or a
 * comparator). Whole-lysate arms are left out of the data entirely.
 */

export type ArmStatus = "core" | "provisional" | "held" | "below_screen" | "comparator";
export type MethodClass = "intact_cell" | "fractionation";

export interface StudyArm {
  id: string;
  name: string;
  publication: string;
  first_author: string | null;
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
  admitted: boolean;
  n_proteins: number;
  reference_overlap: number | null;
  repository: string | null;
  repository_ids: string[];
}

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
  /** counted_detection_hist[k] = proteins detected in exactly k counted arms (k >= 1). */
  counted_detection_hist?: number[];
  /** Same over the deep-dived cohort including k = 0: "all" plus one per tier. */
  cohort_detection_hist?: Record<string, number[]>;
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
}

export type PresenceShard = Record<string, PresenceEntry>;

const BASE = "/data/surface-proteomics";

export const STATUS_LABEL: Record<ArmStatus, string> = {
  core: "Core",
  provisional: "Provisional",
  held: "Held",
  below_screen: "High background",
  comparator: "Comparator",
};

export const STATUS_HELP: Record<ArmStatus, string> = {
  core: "Core: intact-cell labeling, and at least 20% of the list are known surface proteins. Counts as surface evidence.",
  provisional:
    "Provisional: intact-cell labeling that passes with a caveat, for example the authors pre-filtered the list to annotated surface proteins, or it sits just under 20%. Counts as surface evidence.",
  held: "Held: the published table can't yet tell us which proteins were detected, for example every value is imputed. Listed, not counted.",
  below_screen:
    "High background: intact-cell labeling, but fewer than 20% of the list are known surface proteins, so it is mostly intracellular contamination. Listed, not counted.",
  comparator:
    "Comparator: membrane fractionation, or labeling that reaches the inner side of the membrane. Shows a protein is on a membrane, not that it faces outward. Not counted.",
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

/** Labeling chemistry families, each with its own chip colour. */
export const FAMILY_ORDER = [
  "biotin-amine",
  "glycoprotein-capture",
  "glycopeptide-capture",
  "peroxidase-proximity",
  "other-chemoproteomic",
  "membrane-fractionation",
] as const;

export function isCounted(arm: StudyArm): boolean {
  return arm.status === "core" || arm.status === "provisional";
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

export function shortCitation(arm: StudyArm): string {
  const author = (arm.first_author ?? "").split(" ")[0];
  return [author, arm.year].filter(Boolean).join(" ") || arm.name;
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
