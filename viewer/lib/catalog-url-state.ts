/**
 * Catalog filter state ⇄ URL query string.
 *
 * Lets a link open the catalog already filtered — e.g. the HTML paper's
 * figure captions link each count to the exact protein set behind it
 * (`/?nsrc=0&triage=yes` → the 87 definitive zero-database rescues) —
 * and lets a reader share the view they built. CatalogTable reads this
 * once on mount and writes it back (history.replaceState) on every
 * filter change.
 *
 * Parameters (all optional; lists are comma-separated, OR within a list
 * unless noted):
 *   q        free-text search
 *   preset   curated presets (canonical, likely, induced, …)
 *   trigger  Induced sub-axes (cancer, disease, stress, immune)
 *   lowlit   1 = low-literature + UniProt list
 *   db       source DBs that must ALL list the gene (AND)
 *   nsrc     number of source DBs listing the gene (0–5)
 *   tier     deep-dive tier (canonical, likely, low, uncertain, no)
 *   triage   triage-agent verdict (yes, contextual, no)
 *   reason   triage-agent reason code
 *   dd       yes | no — has a deep-dive record
 *   sb       any | ge1 | ge3 | not_in — SURFACE-Bind patches
 *   f.<key>  deep-dive enum filter, e.g. f.surface_method_direct=flow_cytometry
 *   b.<key>  deep-dive boolean filter: yes | no
 *
 * Unknown parameters and values are dropped rather than erroring, so a
 * link made against an older filter vocabulary degrades to a broader
 * view instead of an empty or broken page.
 */

export type SurfaceBindMode = "any" | "ge1" | "ge3" | "not_in";

export interface CatalogUrlState {
  q: string;
  presets: string[];
  triggers: string[];
  lowLit: boolean;
  db: string[];
  nSources: number[];
  tiers: string[];
  verdicts: string[];
  reasons: string[];
  deepDive: "yes" | "no" | null;
  surfaceBind: SurfaceBindMode | null;
  ddEnum: Record<string, string[]>;
  ddBool: Record<string, "yes" | "no">;
}

/** The values each parameter may take; anything else is ignored. */
export interface CatalogUrlVocabulary {
  presets: readonly string[];
  triggers: readonly string[];
  db: readonly string[];
  tiers: readonly string[];
  verdicts: readonly string[];
  reasons: readonly string[];
  /** Deep-dive enum field key → its allowed values. */
  ddEnum: Readonly<Record<string, readonly string[]>>;
  ddBoolKeys: readonly string[];
}

const SURFACE_BIND_MODES: readonly SurfaceBindMode[] = ["any", "ge1", "ge3", "not_in"];
const MAX_SOURCES = 5;

export function emptyCatalogUrlState(): CatalogUrlState {
  return {
    q: "",
    presets: [],
    triggers: [],
    lowLit: false,
    db: [],
    nSources: [],
    tiers: [],
    verdicts: [],
    reasons: [],
    deepDive: null,
    surfaceBind: null,
    ddEnum: {},
    ddBool: {},
  };
}

function list(params: URLSearchParams, key: string, allowed: readonly string[]): string[] {
  const raw = params.get(key);
  if (!raw) return [];
  const ok = new Set(allowed);
  const out: string[] = [];
  for (const v of raw.split(",")) {
    const t = v.trim();
    if (ok.has(t) && !out.includes(t)) out.push(t);
  }
  return out;
}

export function parseCatalogUrl(search: string, vocab: CatalogUrlVocabulary): CatalogUrlState {
  const params = new URLSearchParams(search);
  const state = emptyCatalogUrlState();
  state.q = (params.get("q") ?? "").trim();
  state.presets = list(params, "preset", vocab.presets);
  state.triggers = list(params, "trigger", vocab.triggers);
  state.lowLit = params.get("lowlit") === "1";
  state.db = list(params, "db", vocab.db);
  state.nSources = list(
    params,
    "nsrc",
    Array.from({ length: MAX_SOURCES + 1 }, (_, i) => String(i)),
  ).map(Number);
  state.tiers = list(params, "tier", vocab.tiers);
  state.verdicts = list(params, "triage", vocab.verdicts);
  state.reasons = list(params, "reason", vocab.reasons);
  const dd = params.get("dd");
  state.deepDive = dd === "yes" || dd === "no" ? dd : null;
  const sb = params.get("sb") as SurfaceBindMode | null;
  state.surfaceBind = sb && SURFACE_BIND_MODES.includes(sb) ? sb : null;
  for (const [key, allowed] of Object.entries(vocab.ddEnum)) {
    const vals = list(params, `f.${key}`, allowed);
    if (vals.length) state.ddEnum[key] = vals;
  }
  for (const key of vocab.ddBoolKeys) {
    const v = params.get(`b.${key}`);
    if (v === "yes" || v === "no") state.ddBool[key] = v;
  }
  return state;
}

/** True when the state filters nothing (the default catalog view). */
export function isEmptyCatalogUrlState(s: CatalogUrlState): boolean {
  return serializeCatalogUrl(s) === "";
}

/**
 * Query string (without the leading `?`) for a state; "" for the default
 * view. Keys come out in a fixed order so the same filters always produce
 * the same URL. Commas are left literal — they are legal in a query and
 * keep shared links readable.
 */
export function serializeCatalogUrl(s: CatalogUrlState): string {
  const parts: string[] = [];
  const add = (key: string, value: string) => {
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value).replace(/%2C/g, ",")}`);
  };
  if (s.q) add("q", s.q);
  if (s.presets.length) add("preset", s.presets.join(","));
  if (s.triggers.length) add("trigger", s.triggers.join(","));
  if (s.lowLit) add("lowlit", "1");
  if (s.db.length) add("db", s.db.join(","));
  if (s.nSources.length) add("nsrc", [...s.nSources].sort((a, b) => a - b).join(","));
  if (s.tiers.length) add("tier", s.tiers.join(","));
  if (s.verdicts.length) add("triage", s.verdicts.join(","));
  if (s.reasons.length) add("reason", s.reasons.join(","));
  if (s.deepDive) add("dd", s.deepDive);
  if (s.surfaceBind) add("sb", s.surfaceBind);
  for (const key of Object.keys(s.ddEnum).sort()) {
    if (s.ddEnum[key].length) add(`f.${key}`, s.ddEnum[key].join(","));
  }
  for (const key of Object.keys(s.ddBool).sort()) add(`b.${key}`, s.ddBool[key]);
  return parts.join("&");
}
