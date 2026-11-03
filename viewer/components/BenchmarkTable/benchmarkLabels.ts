/**
 * Model + prompt-variant labels for the SurfaceBench matrix.
 *
 * The rendered model / variant lists are DATA-DRIVEN: they come from the
 * matrix payload's `models` / `variants` arrays (what the Worker actually
 * has rows for). The label tables below only supply display names and a
 * display order. An id the tables don't know still renders, after the
 * known ones, under a label derived from the raw id — so the next model
 * or variant shows up without a viewer change, just with a plainer label.
 */
import type {
  BenchmarkMatrix,
  BenchmarkVariantResult,
} from "../../lib/surfaceome-types";

export interface LabelDef {
  id: string;
  /** Compact label for narrow column headers. */
  short: string;
  long: string;
}

export interface ModelLabelDef extends LabelDef {
  /** Model family on line 1 of the compact column header ("Sonnet"). */
  family: string;
  /** Version on line 2 of the compact column header ("4.6"). */
  version: string;
}

/** The production triage configuration: Sonnet 4.6 on the ncbi
 *  (+ IDs) prompt. The page singles this model out visually. */
export const PRODUCTION_MODEL_ID = "claude-sonnet-4-6";
export const PRODUCTION_VARIANT_ID = "ncbi";

// Display order: by family (Haiku → Sonnet → Opus), then version.
export const MODEL_LABELS: ModelLabelDef[] = [
  { id: "claude-haiku-4-5",  short: "H 4.5", long: "Haiku 4.5",  family: "Haiku",  version: "4.5" },
  { id: "claude-haiku-5-5",  short: "H 5.5", long: "Haiku 5.5",  family: "Haiku",  version: "5.5" },
  { id: "claude-sonnet-4-6", short: "S 4.6", long: "Sonnet 4.6", family: "Sonnet", version: "4.6" },
  { id: "claude-sonnet-5",   short: "S 5",   long: "Sonnet 5",   family: "Sonnet", version: "5" },
  { id: "claude-sonnet-5-5", short: "S 5.5", long: "Sonnet 5.5", family: "Sonnet", version: "5.5" },
  { id: "claude-opus-4-8",   short: "O 4.8", long: "Opus 4.8",   family: "Opus",   version: "4.8" },
  { id: "claude-opus-5",     short: "O 5",   long: "Opus 5",     family: "Opus",   version: "5" },
  { id: "claude-opus-5-5",   short: "O 5.5", long: "Opus 5.5",   family: "Opus",   version: "5.5" },
];

// Display order for the expanded model × variant grid.
export const VARIANT_LABELS: LabelDef[] = [
  { id: "naive",           short: "naive",            long: "no context" },
  { id: "ncbi",            short: "NCBI",             long: "HGNC + UniProt + NCBI summary" },
  { id: "ncbi_effort_low", short: "NCBI · low effort", long: "NCBI summary, low reasoning effort" },
  { id: "web_ncbi",        short: "web + NCBI",       long: "NCBI + web search" },
  { id: "pubmed_ncbi",     short: "PubMed + NCBI",    long: "NCBI + PubMed evidence" },
];

function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/** Fallback label for a model id the table doesn't know:
 *  "claude-foo-6-1" → family "Foo", version "6.1". */
export function fallbackModelLabel(id: string): ModelLabelDef {
  const parts = id.replace(/^claude-/, "").split("-");
  const versionStart = parts.findIndex((p) => /^\d+$/.test(p));
  const familyParts = versionStart === -1 ? parts : parts.slice(0, versionStart);
  const versionParts = versionStart === -1 ? [] : parts.slice(versionStart);
  const family = familyParts.map(capitalize).join(" ") || id;
  const version = versionParts.join(".");
  const long = version ? `${family} ${version}` : family;
  return { id, short: long, long, family, version };
}

/** Fallback label for a prompt-variant id the table doesn't know. */
export function fallbackVariantLabel(id: string): LabelDef {
  const label = id.replace(/_/g, " ");
  return { id, short: label, long: label };
}

/** Order `ids` by the label table, unknown ids appended in payload order. */
function orderByLabels<T extends LabelDef>(
  ids: string[],
  known: T[],
  fallback: (id: string) => T,
): T[] {
  const seen = new Set<string>();
  const unique = ids.filter((id) => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
  const knownIds = new Set(known.map((k) => k.id));
  return [
    ...known.filter((k) => seen.has(k.id)),
    ...unique.filter((id) => !knownIds.has(id)).map(fallback),
  ];
}

/** Model ids present in the payload: the declared `models` list plus any
 *  model that has cells in a row but was left off that list. */
function payloadModelIds(matrix: BenchmarkMatrix): string[] {
  const ids = [...(matrix.models ?? [])];
  for (const r of matrix.rows ?? []) {
    for (const m of Object.keys(r.verdicts ?? {})) ids.push(m);
  }
  return ids;
}

function payloadVariantIds(matrix: BenchmarkMatrix): string[] {
  const ids = [...(matrix.variants ?? [])];
  for (const r of matrix.rows ?? []) {
    for (const byVariant of Object.values(r.verdicts ?? {})) {
      for (const v of Object.keys(byVariant ?? {})) ids.push(v);
    }
  }
  return ids;
}

export function modelLabelsFor(matrix: BenchmarkMatrix): ModelLabelDef[] {
  return orderByLabels(payloadModelIds(matrix), MODEL_LABELS, fallbackModelLabel);
}

export function variantLabelsFor(matrix: BenchmarkMatrix): LabelDef[] {
  return orderByLabels(payloadVariantIds(matrix), VARIANT_LABELS, fallbackVariantLabel);
}

/** Why a cell has no verdict. `missing` = no run on file for this
 *  (model, variant); `refused` = the model's safety classifier declined
 *  the call; `errored` = a run exists but produced no valid verdict. */
export type CellStatus = "verdict" | "refused" | "errored" | "missing";

export function cellStatus(
  cell: BenchmarkVariantResult | null | undefined,
): CellStatus {
  if (cell == null) return "missing";
  if (cell.verdict) return "verdict";
  if (cell.error === "refusal") return "refused";
  return "errored";
}

/** Unique, readable TSV column prefix per model id:
 *  "claude-sonnet-4-6" → "sonnet_4_6", "claude-opus-5" → "opus_5". */
export function modelSlug(modelId: string): string {
  return modelId
    .replace(/^claude-/i, "")
    .replace(/[^a-z0-9]+/gi, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}
