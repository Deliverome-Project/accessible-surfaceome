/*
 * L1 library design overlay: per-member tag sites (current picks + alternatives, with
 * their rationale), folded models and contact sites, served by the Worker at
 * /v1/l1-design[/{SYMBOL}] from the l1_*_public tables
 * (cloudflare/migrations/l1_design_v1.sql), plus the token-gated review endpoints
 * (/v1/l1-review*). Client-safe (no node:fs).
 *
 * Residue numbers are in each MEMBER's own native numbering, which is not the gene's
 * canonical numbering when the member is an isoform or an ortholog.
 */
import {
  STRUCTURES_BASE,
  deepTMHMMType,
  libraryVariantLabel,
  type LibraryTopologyRow,
  type StructureVariantLibraryInput,
} from "./structure-viewer-types";
import type { CoReceptorRequirements } from "./surfaceome-types";
import { geneSynonymRank, type SynonymOverlay } from "./gene-jump-entries";

export type L1SiteStatus = "built" | "decided_not_built" | "no_tag" | "pending" | "alternative";
export type L1SiteSource = "rung_builder" | "ranker" | "agent_proposer";

export const STATUS_LABEL: Record<L1SiteStatus, string> = {
  built: "built",
  decided_not_built: "decided, not built",
  no_tag: "no tag",
  pending: "pending",
  alternative: "alternative",
};

export const STATUS_HELP: Record<L1SiteStatus, string> = {
  built: "A tagged construct has been designed and checked for this pick.",
  decided_not_built: "The pick is decided (by Becca, or a session she delegated to) but no construct is built yet.",
  no_tag: "This member gets no tag on this rung; the reason says why (e.g. routed to another rung).",
  pending: "The source table predates the 2026-11-12 delegation and still marks this as held or awaiting approval.",
  alternative: "A ranked or proposed site that is not the current pick, shown for comparison.",
};

export const SOURCE_LABEL: Record<L1SiteSource, string> = {
  rung_builder: "rung builder",
  ranker: "tag-site ranker",
  agent_proposer: "agent proposal (experimental)",
};

export interface L1Site {
  site_id: string;
  rung: string;
  site_source?: L1SiteSource;
  is_primary?: boolean;
  /** 0 = before residue 1; null = no site. */
  insert_after_residue: number | null;
  residue_before: string | null;
  residue_after: string | null;
  leader: string | null;
  cassette: string | null;
  cassette_aa: number | null;
  rank: number | null;
  status: L1SiteStatus;
  decision?: string | null;
  status_detail: string | null;
  confidence?: string | null;
  rejected_alternative?: string | null;
  rationale?: Record<string, unknown> | null;
  source: { pr: number | null; pr_state: string | null; commit: string; path: string };
  decided_by: string;
  implemented_by: string;
  reason: string | null;
}

export interface L1Structure {
  structure_id: string;
  kind: "native" | "tagged";
  site_id: string | null;
  source: string;
  release: string | null;
  r2_key: string | null;
  model_url: string | null;
  proteoform_match: string | null;
  residue_offset: number;
  is_chosen: boolean;
  mean_plddt: number | null;
  cassette_first_model_residue: number | null;
  cassette_last_model_residue: number | null;
  /** Residues in the model file (tagged: native + cassette, mature chain for Igk). */
  model_length_aa?: number | null;
  refold_verdict?: string | null;
  note: string | null;
}

export interface L1Contact {
  residue: number;
  aa: string | null;
  canonical_residue: number | null;
  source: "literature_agent" | "uniprot_binding";
  evidence_types: string | null;
  contact_classes: string | null;
  confidence_tier: "high" | "lower" | "hidden";
  ion_site: boolean;
  additive_only: boolean;
  in_extracellular: boolean;
  topology_state: string | null;
  ligands: string | null;
  pmids: string | null;
}

export interface L1Member {
  member_id: string;
  design_id: string | null;
  gene_symbol: string;
  species: string | null;
  candidate_set: string | null;
  rung: string;
  membrane_class?: string;
  n_tm?: number | null;
  ordered_length_aa: number | null;
  sequence_sha256?: string | null;
  /** UniProt accession of the member's chosen native model. */
  uniprot_acc?: string | null;
  /** Signal-peptide status and UniProt comparison, from the member annotations export
   *  (absent from loads that predate it; see memberSp / uniprotDiffSummary). */
  sp_status?: L1SpStatus | null;
  native_sp_last_residue?: number | null;
  sp_evidence?: string | null;
  sp_concern?: L1SpConcern | null;
  sp_metrics?: L1SpMetrics | null;
  uniprot_canonical_acc?: string | null;
  uniprot_canonical_length?: number | null;
  matches_uniprot_canonical?: boolean | number | null;
  uniprot_diff?: L1UniprotDiff[] | null;
  /** The proteoform audit's decision for this member, when it has one. */
  proteoform?: {
    decision?: string; target?: string; status?: string; flags?: string; reason?: string;
    alternative_rejected?: string; decided_by?: string; implemented_by?: string;
  } | null;
  sites: L1Site[];
  structures: L1Structure[];
  contacts?: L1Contact[];
}

export interface L1Load {
  load_version: string;
  created_at: string;
}

export interface L1DesignFile {
  gene_symbol: string;
  load: L1Load | null;
  members: L1Member[];
}

export interface L1IndexMember {
  member_id: string;
  design_id: string | null;
  gene_symbol: string;
  species: string | null;
  candidate_set: string | null;
  rung: string;
  membrane_class: string;
  n_tm: number | null;
  ordered_length_aa: number | null;
  sequence_sha256: string | null;
  pick_status: L1SiteStatus[];
  /** Leader of the member's primary pick ("igk" or null); undefined when the index
   *  predates the field, which keeps the SP filter hidden rather than wrong. */
  pick_leader?: string | null;
  sp_status?: L1SpStatus | null;
  sp_concern?: L1SpConcern | null;
  matches_uniprot_canonical?: boolean | number | null;
  /** True when any primary pick uses a snorkel tag construct; undefined when the API predates it. */
  has_snorkel?: boolean | number | null;
  /** Canonical sorted signature of primary tag sites (site_id:insert_after:leader:cassette joined by '|'). */
  primary_site_signature?: string | null;
}

export interface L1Index {
  load: L1Load | null;
  members: L1IndexMember[];
}

const STATUSES: ReadonlySet<string> = new Set([
  "built", "decided_not_built", "no_tag", "pending", "alternative",
]);

/** Narrow an unknown payload, or null. Drops a site with an unknown status rather than
 *  rendering it under a misleading pill. */
export function parseL1Design(raw: unknown): L1DesignFile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.gene_symbol !== "string" || !Array.isArray(o.members)) return null;
  const members = (o.members as unknown[]).flatMap((m): L1Member[] => {
    if (!m || typeof m !== "object") return [];
    const r = m as L1Member;
    if (typeof r.member_id !== "string" || typeof r.rung !== "string") return [];
    return [{
      ...r,
      sites: (Array.isArray(r.sites) ? r.sites : []).filter((s) => STATUSES.has(s?.status)),
      structures: Array.isArray(r.structures) ? r.structures : [],
      contacts: Array.isArray(r.contacts) ? r.contacts : [],
    }];
  });
  return { ...(o as unknown as L1DesignFile), members };
}

export function parseL1Index(raw: unknown): L1Index | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (!Array.isArray(o.members)) return null;
  const members = (o.members as L1IndexMember[]).filter(
    (m) => m && typeof m.member_id === "string" && typeof m.gene_symbol === "string",
  );
  return { load: (o.load as L1Load | null) ?? null, members };
}

/** URL of a model's coordinates: our own models are in the public structures bucket,
 *  AlphaFold DB models at their AFDB URL. */
export function l1StructureUrl(s: Pick<L1Structure, "r2_key" | "model_url">): string | null {
  if (s.r2_key) return `${STRUCTURES_BASE}/${s.r2_key.replace(/^\/+/, "")}`;
  return s.model_url ?? null;
}

/** "between E34 and S35", "after the last residue (760)", "before residue 1". */
export function l1SiteLabel(site: L1Site, orderedLength: number | null): string {
  const r = site.insert_after_residue;
  if (r == null) return "no site";
  if (r === 0) return "before residue 1";
  if (orderedLength != null && r === orderedLength) return `after the last residue (${r})`;
  const before = site.residue_before ? `${site.residue_before}${r}` : `${r}`;
  const after = site.residue_after ? `${site.residue_after}${r + 1}` : `${r + 1}`;
  return `between ${before} and ${after}`;
}

/** The arm a site id names (`l1-p1088-a2` → `a2`), or null when it names none. */
export function armLabel(siteId: string): string | null {
  const m = /-(a\d+)$/.exec(siteId);
  return m ? m[1] : null;
}

/** Chosen 3D models for one member: tagged refolds linked to the member's current
 *  sites (primary picks first, passing before failing), followed by native models.
 *  Earlier/unlisted sweep refolds (site_id null or not among the member's current
 *  sites) are excluded so reviewers never see discarded candidate folds. */
export function currentMemberModels(
  structures: readonly L1Structure[],
  sites: readonly Pick<L1Site, "site_id" | "is_primary">[],
): L1Structure[] {
  const chosen = structures.filter((s) => s.is_chosen);
  const primaryIds = new Set(sites.filter((s) => s.is_primary !== false).map((s) => s.site_id));
  const listedIds = new Set(sites.map((s) => s.site_id));
  const verdictRank = (s: L1Structure) => (s.refold_verdict === "pass" ? 0 : s.refold_verdict === "fail" ? 2 : 1);
  const linked = chosen
    .filter((s) => s.kind === "tagged" && s.site_id != null && listedIds.has(s.site_id))
    .sort((a, b) => {
      const pa = a.site_id != null && primaryIds.has(a.site_id) ? 0 : 1;
      const pb = b.site_id != null && primaryIds.has(b.site_id) ? 0 : 1;
      return pa - pb || verdictRank(a) - verdictRank(b);
    });
  const native = chosen.filter((s) => s.kind !== "tagged");
  return [...linked, ...native];
}

/** The member's current picks first, then alternatives by source and rank. */
export function sortSites(sites: readonly L1Site[]): L1Site[] {
  const srcOrder: Record<string, number> = { rung_builder: 0, ranker: 1, agent_proposer: 2 };
  return [...sites].sort(
    (a, b) =>
      Number(b.is_primary ?? true) - Number(a.is_primary ?? true) ||
      (srcOrder[a.site_source ?? "rung_builder"] ?? 9) - (srcOrder[b.site_source ?? "rung_builder"] ?? 9) ||
      (a.rank ?? 99) - (b.rank ?? 99) ||
      a.site_id.localeCompare(b.site_id),
  );
}

/** Contacts to draw: hidden-tier rows (ion sites, crystallization additives) only on
 *  request, since the contact agents treat those as hard negatives for ligand contact. */
export function visibleContacts(contacts: readonly L1Contact[], showHidden: boolean): L1Contact[] {
  return contacts.filter((c) => showHidden || c.confidence_tier !== "hidden");
}

/** true / false from the index; null when the API predates `has_snorkel`. */
export function memberHasSnorkel(m: { has_snorkel?: boolean | number | null }): boolean | null {
  const v = m.has_snorkel;
  if (v === null || v === undefined) return null;
  return v === true || v === 1;
}

/** Members in the browser's order, filtered by rung / class / free text. */
export function filterIndex(
  members: readonly L1IndexMember[],
  f: {
    rung?: string; membraneClass?: string; query?: string; status?: string;
    /** "native" | "igk_swap" | "igk_res1" | "none" */
    sp?: string;
    /** "concerning" | "clean" (N-after-SP SignalP vs DeepTMHMM pre/post checks) */
    spConcern?: string;
    /** "yes" = differs from the UniProt canonical, "no" = identical */
    diff?: string;
    /** "yes" = uses a snorkel tag, "no" = does not */
    snorkel?: string;
    /** "mine" | "notmine" | "stale", against `reviewedByMe` / `staleDesignIds` (design ids) */
    reviewed?: string;
    reviewedByMe?: ReadonlySet<string>;
    staleDesignIds?: ReadonlySet<string>;
    /** Build-baked symbol -> aliases map (`/data/gene-synonyms.json`) so alt names
     *  like "CD20" -> MS4A1 or "Nav1.7" -> SCN9A match just like the main viewer. */
    synonyms?: SynonymOverlay | null;
  },
): L1IndexMember[] {
  const q = (f.query ?? "").trim().toUpperCase();
  const mine = f.reviewedByMe ?? new Set<string>();
  const stale = f.staleDesignIds ?? new Set<string>();
  const syn = f.synonyms ?? null;
  const rankOf = (m: L1IndexMember) =>
    q ? geneSynonymRank(m.gene_symbol, syn?.[m.gene_symbol], q) : 0;
  return members
    .filter((m) => !f.rung || m.rung === f.rung)
    .filter((m) => !f.membraneClass || m.membrane_class === f.membraneClass)
    .filter((m) => !f.status || (f.status === "none" ? m.pick_status.length === 0 : m.pick_status.includes(f.status as L1SiteStatus)))
    .filter((m) => !f.sp || indexSpStatus(m) === f.sp)
    .filter((m) => !f.spConcern || m.sp_concern === f.spConcern)
    .filter((m) => !f.diff || (f.diff === "yes" ? uniprotDiffers(m) === true : uniprotDiffers(m) === false))
    .filter((m) => !f.snorkel || (f.snorkel === "yes" ? memberHasSnorkel(m) === true : memberHasSnorkel(m) === false))
    .filter((m) => {
      if (!f.reviewed) return true;
      const id = m.design_id ?? m.member_id;
      if (f.reviewed === "stale") return stale.has(id);
      return (f.reviewed === "mine") === mine.has(id);
    })
    .filter(
      (m) =>
        !q ||
        rankOf(m) < 6 ||
        m.member_id.toUpperCase() === q ||
        (m.design_id ?? "").toUpperCase() === q ||
        // Words that name a class, a rung or an SP type match those too, so "gpcr",
        // "c-terminal", "snorkel" or "igk" find members without opening the filters.
        (q.length >= 3 &&
          (m.membrane_class.toUpperCase().includes(q) ||
            m.rung.toUpperCase().includes(q) ||
            (memberHasSnorkel(m) === true && "SNORKEL".includes(q)) ||
            SP_SEARCH[indexSpStatus(m) ?? ""]?.some((w) => w.includes(q)) === true)),
    )
    .sort((a, b) => {
      if (q) {
        const d = rankOf(a) - rankOf(b);
        if (d !== 0) return d;
      }
      return a.gene_symbol.localeCompare(b.gene_symbol) || a.member_id.localeCompare(b.member_id);
    });
}

// ------------------------------------------------------------ signal peptide / UniProt

export type L1SpStatus = "native" | "igk_swap" | "igk_res1" | "none";
export type L1SpConcern = "clean" | "concerning";

export interface L1SpMetrics {
  deeptmhmm_v1_cut?: number | null;
  signalp_pre_pred?: string | null;
  signalp_pre_cut?: number | null;
  signalp_pre_sp_prob?: number | null;
  signalp_pre_cs_prob?: number | null;
  signalp_post_pred?: string | null;
  signalp_post_cut?: number | null;
  signalp_post_sp_prob?: number | null;
  signalp_post_cs_prob?: number | null;
  cut_spread_aa?: number | null;
  cleavage_prob_delta?: number | null;
  post_leader?: "native" | "igk" | string | null;
  insert_after_residue?: number | null;
  igk_replaces_residues?: string | null;
  concern?: L1SpConcern | null;
  concern_reasons?: string[] | null;
}

export const SP_CONCERN_LABEL: Record<L1SpConcern, string> = {
  concerning: "concerning",
  clean: "clean",
};

export const SP_LABEL: Record<L1SpStatus, string> = {
  native: "native SP",
  igk_swap: "Igκ replaces native SP",
  igk_res1: "Igκ added at residue 1",
  none: "no SP or leader",
};

const SP_SEARCH: Record<string, string[]> = {
  native: ["NATIVE SP", "SIGNAL PEPTIDE"],
  igk_swap: ["IGK", "IGΚ", "IGK SWAP", "LEADER"],
  igk_res1: ["IGK", "IGΚ", "IGK RES1", "LEADER"],
  none: [],
};

/**
 * SP status of an index row. The export's own `sp_status` wins; without it the status
 * is read off the primary pick: an Igk leader on an "N after SP" pick replaces the
 * native SP, on an "N at residue 1" pick it is added in front; no leader on "N after SP"
 * keeps the native SP. Other rungs say nothing about the SP, so they are "none" only
 * when the export says so and otherwise null (unknown). Null too when the index
 * predates `pick_leader`, so a filter cannot silently drop every member.
 */
export function indexSpStatus(m: Pick<L1IndexMember, "rung"> & { sp_status?: L1SpStatus | null; pick_leader?: string | null }): L1SpStatus | null {
  if (m.sp_status) return m.sp_status;
  if (m.pick_leader === undefined) return null;
  const lead = (m.pick_leader ?? "").toLowerCase();
  if (lead.startsWith("igk")) return m.rung.startsWith("N at residue 1") ? "igk_res1" : "igk_swap";
  if (m.rung.startsWith("N after SP")) return "native";
  return null;
}

/** true / false from the export; null when this load does not say. */
export function uniprotDiffers(m: { matches_uniprot_canonical?: boolean | number | null }): boolean | null {
  const v = m.matches_uniprot_canonical;
  if (v === null || v === undefined) return null;
  return !(v === true || v === 1);
}

export interface L1UniprotDiff {
  kind: string;
  member_start: number | null;
  member_end: number | null;
  uniprot_start: number | null;
  uniprot_end: number | null;
  member_aa?: string | null;
  uniprot_aa?: string | null;
}

/** "a substitution at 412 (A→V)", "residues 1–24 not in UniProt", ... one line each. */
export function uniprotDiffLines(diffs: readonly L1UniprotDiff[]): string[] {
  const span = (a: number | null, b: number | null) => (a == null ? "?" : a === b || b == null ? `${a}` : `${a}–${b}`);
  return diffs.map((d) => {
    const here = span(d.member_start, d.member_end);
    const there = span(d.uniprot_start, d.uniprot_end);
    const aa = d.member_aa || d.uniprot_aa ? ` (${d.uniprot_aa || "–"} → ${d.member_aa || "–"})` : "";
    switch (d.kind) {
      case "substitution": return `member ${here} differs from UniProt ${there}${aa}`;
      case "insertion": return `member ${here} not in UniProt${aa}`;
      case "deletion": return `UniProt ${there} missing from the member${aa}`;
      case "n_extension": return `member starts earlier: ${here} before UniProt residue 1`;
      case "c_extension": return `member runs past the UniProt C-terminus: ${here}`;
      case "n_truncation": return `member starts later: UniProt ${there} not ordered`;
      case "c_truncation": return `member ends early: UniProt ${there} not ordered`;
      default: return `${d.kind}: member ${here}, UniProt ${there}${aa}`;
    }
  });
}

export interface L1SpDescription {
  status: L1SpStatus | null;
  /** One line for the member header. */
  text: string;
  /** Why this member uses Igκ vs native SP vs no leader (per-member reason/evidence when
   *  present, else the rung rule). */
  why: string | null;
  /** Native residues this describes, member numbering, for the topology strip. */
  band: { from: number; to: number; kind: "native_sp" | "replaced" } | null;
  /** Where the statement comes from. */
  source: string;
}

/**
 * What the member does at its N-terminus, in words, from (best first) the export's
 * `sp_status` + `native_sp_last_residue`, the primary pick, or the member's own v1
 * topology (leading "S" residues).
 */
export function memberSp(member: Pick<L1Member, "rung" | "sites" | "sp_status" | "native_sp_last_residue" | "sp_evidence">, topology?: string | null): L1SpDescription {
  const pick = member.sites.find((s) => s.is_primary !== false);
  const leader = (pick?.leader ?? "").toLowerCase();
  const ins = pick?.insert_after_residue ?? null;
  const spEnd = member.native_sp_last_residue ?? null;
  const topoSp = topology ? (/^S+/.exec(topology)?.[0].length ?? 0) : 0;
  const status: L1SpStatus | null =
    member.sp_status ?? indexSpStatus({ rung: member.rung, pick_leader: pick ? pick.leader ?? null : undefined }) ??
    (topology ? (topoSp ? "native" : "none") : null);
  const evidence = member.sp_evidence ? ` (${member.sp_evidence})` : "";
  const explicitWhy = pick?.reason?.trim() || member.sp_evidence?.trim() || null;
  const source = member.sp_status ? `design export${evidence}` : pick && (leader || member.rung.startsWith("N after SP")) ? "the primary pick" : topology ? "DeepTMHMM v1 topology" : "not known";
  if (status === "igk_swap") {
    const removed = ins != null && ins > 0 ? ins : spEnd;
    const sp = spEnd ? `native SP 1–${spEnd}` : "the native SP";
    const extra = removed && spEnd && removed > spEnd ? `; native 1–${removed} not in the construct` : "";
    return {
      status,
      text: spEnd
        ? `Igκ leader replaces ${sp}${extra}`
        : `Igκ leader replaces the native N-terminus${removed ? ` (native residues 1–${removed})` : ""}`,
      why: explicitWhy ?? "Native SP swapped for Igκ leader so the N-terminal tag cleaves cleanly and stays exposed.",
      band: removed ? { from: 1, to: removed, kind: "replaced" } : null,
      source,
    };
  }
  if (status === "igk_res1") {
    return {
      status,
      text: "Igκ leader added before residue 1 (no native signal peptide)",
      why: explicitWhy ?? "Extracellular N-terminus without a native SP; Igκ leader directs surface translocation of the tag.",
      band: null,
      source,
    };
  }
  if (status === "native") {
    const end = spEnd ?? (topoSp || null);
    return {
      status,
      text: `native signal peptide${end ? ` (cleaved 1–${end})` : ""}, kept${ins != null && member.rung.startsWith("N after SP") ? `; tag after residue ${ins}` : ""}`,
      why: explicitWhy ?? "Native SP retained; tag inserted after the cleavage site without needing an Igκ swap.",
      band: end ? { from: 1, to: end, kind: "native_sp" } : null,
      source: spEnd ? source : end ? "DeepTMHMM v1 topology" : source,
    };
  }
  if (status === "none") {
    return {
      status,
      text: "no signal peptide and no leader",
      why: explicitWhy ?? "No native SP and no Igκ leader needed (tagged internally/C-terminally or cytoplasmic N-terminus).",
      band: null,
      source,
    };
  }
  return { status: null, text: "signal peptide: not stated for this member", why: null, band: null, source };
}

export function countBy<T>(rows: readonly T[], key: (r: T) => string): [string, number][] {
  const m = new Map<string, number>();
  for (const r of rows) m.set(key(r), (m.get(key(r)) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

/** Worker base for the L1 design load. NEXT_PUBLIC_L1_DESIGN_API_BASE points only the
 *  L1 surfaces elsewhere (a local `wrangler dev` holding a candidate load). */
export const L1_DESIGN_API_BASE =
  process.env.NEXT_PUBLIC_L1_DESIGN_API_BASE ??
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ??
  "https://api.deliverome.org/surfaceome";

/**
 * Outcome of one design load. A load that ARRIVED and holds no member for the
 * gene ("empty") is a different fact from a load that could not be fetched
 * ("error"), and the card must not render the second as the first: for most of
 * the cohort the honest reading of a bare "no design" was "the API call failed".
 */
export type L1DesignFetch =
  | { kind: "ok"; file: L1DesignFile }
  | { kind: "empty" }
  | { kind: "error" };

export async function fetchL1DesignResult(symbol: string, apiBase: string): Promise<L1DesignFetch> {
  let res: Response;
  try {
    res = await fetch(`${apiBase}/v1/l1-design/${encodeURIComponent(symbol)}`);
  } catch {
    return { kind: "error" };
  }
  // The Worker answers 200 with `members: []` for a gene the load does not
  // cover, so a 404 here means the ROUTE is missing (an older Worker), not
  // that the gene has no design — both are fetch failures, not absences.
  if (!res.ok) return { kind: "error" };
  let file: L1DesignFile | null;
  try {
    file = parseL1Design(await res.json());
  } catch {
    return { kind: "error" };
  }
  // Unparseable body: the payload is not a design load at all (an HTML error
  // page, a shape change). Not an absence either.
  if (!file) return { kind: "error" };
  // `load: null` is the Worker's soft-fail: `l1Load` catches every D1 error and
  // degrades to `{ load: null, members: [] }` with a 200 (see its own comment,
  // "Missing tables ... degrade to `load: null` rather than a 500"). A gene the
  // load genuinely does not cover still carries the load header with an empty
  // member list, so a missing header means the load table did not answer — the
  // one case where a 200 is a failure, and the one this card must not print as
  // "no design is published".
  if (!file.load) return { kind: "error" };
  return file.members.length ? { kind: "ok", file } : { kind: "empty" };
}

/** Back-compat shape for callers that only need "a design or nothing"
 *  (the header's library chip, the review browser). */
export async function fetchL1Design(symbol: string, apiBase: string): Promise<L1DesignFile | null> {
  const r = await fetchL1DesignResult(symbol, apiBase);
  return r.kind === "ok" ? r.file : null;
}

/**
 * Why a gene has no L1 design, as far as the gene record can say.
 *
 * `obligate_partner`: the gene is NOT an L1 member and its record reports that
 * surface expression requires an obligate partner. The L1 cohort filter
 * (`final_library.py`) drops a gene whose obligate partner the host cell line
 * does not express, because the ORF delivered on its own is not surface-displayed
 * — so a reviewer looking at the TCR-CD3 subunits, the BCR subunits or B2M is
 * looking at a deliberate exclusion, not at work nobody has got to. The record
 * does not carry the filter's own verdict (the partner's cell-line TPM), so this
 * names the criterion that applies, never "this is the gate that fired".
 *
 * `unpublished`: nothing in the record explains the absence — for a library
 * member that is a gap in the published load.
 */
export type L1AbsenceReason = "obligate_partner" | "unpublished";

export function l1AbsenceReason(a: {
  inFgLibrary: boolean;
  coReceptor: CoReceptorRequirements | null | undefined;
}): L1AbsenceReason {
  if (a.inFgLibrary) return "unpublished";
  const cr = a.coReceptor;
  if (!cr || cr.surface_expression_dependency !== "required") return "unpublished";
  // Nothing to show a reviewer without either a partner or a rationale, and an
  // unexplained "excluded" reads worse than a plain absence.
  const partners = (cr.partners ?? []).filter((p) => p.trim());
  if (!partners.length && !(cr.rationale ?? "").trim()) return "unpublished";
  return "obligate_partner";
}

/**
 * Outcome of fetching `/v1/l1-design`. Distinguishes a genuine `200` response
 * (including `{ load: null, members: [] }` when no load is published) from a
 * network failure, HTTP error, or unparseable body so the review page never
 * tells a reviewer "No v1 library design is published on this API yet" on a
 * transient 503 or network hiccup.
 */
export type L1IndexFetch =
  | { kind: "ok"; data: L1Index }
  | { kind: "error"; status?: number };

async function fetchL1IndexOnce(apiBase: string): Promise<{ result: L1IndexFetch; retryable: boolean }> {
  let res: Response;
  try {
    res = await fetch(`${apiBase}/v1/l1-design`);
  } catch {
    return { result: { kind: "error" }, retryable: true };
  }
  if (!res.ok) {
    return {
      result: { kind: "error", status: res.status },
      retryable: res.status >= 500 || res.status === 429,
    };
  }
  let raw: unknown;
  try {
    raw = await res.json();
  } catch {
    return { result: { kind: "error", status: res.status }, retryable: true };
  }
  const data = parseL1Index(raw);
  if (!data) return { result: { kind: "error", status: res.status }, retryable: false };
  return { result: { kind: "ok", data }, retryable: false };
}

export async function fetchL1IndexResult(
  apiBase: string,
  { retryDelayMs = 500 }: { retryDelayMs?: number } = {},
): Promise<L1IndexFetch> {
  const first = await fetchL1IndexOnce(apiBase);
  if (first.result.kind === "ok" || !first.retryable) return first.result;
  if (retryDelayMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
  }
  const second = await fetchL1IndexOnce(apiBase);
  return second.result;
}

export async function fetchL1Index(apiBase: string): Promise<L1Index | null> {
  const r = await fetchL1IndexResult(apiBase);
  return r.kind === "ok" ? r.data : null;
}

// --------------------------------------------------------------------------- reviews

export type L1Placement = "rung_default" | "n_term" | "c_term" | "internal" | "after_sp" | "igk_tag";

export const PLACEMENT_LABEL: Record<L1Placement, string> = {
  rung_default: "the member's rung (default)",
  n_term: "N-terminus",
  c_term: "C-terminus",
  internal: "internal (after residue)",
  after_sp: "after the signal peptide (after residue)",
  igk_tag: "Igκ leader + tag",
};

export interface L1ReviewRow {
  review_id: string;
  created_at: string;
  reviewer: string;
  member_id: string;
  design_id: string;
  sequence_sha256?: string | null;
  gene_symbol: string;
  site_id: string | null;
  verdict: "good" | "no";
  reason: string | null;
  load_version: string;
  site_signature?: string | null;
}

export interface L1AltTagRow {
  suggestion_id: string;
  created_at: string;
  reviewer: string;
  member_id: string;
  design_id: string;
  sequence_sha256?: string | null;
  gene_symbol: string;
  insert_after_residue: number | null;
  placement: L1Placement;
  cassette_variant: string | null;
  reason: string | null;
  load_version: string;
  site_signature?: string | null;
}

export interface L1Reviews {
  reviews: L1ReviewRow[];
  alt_tags: L1AltTagRow[];
}

export const REVIEW_HEADER = "X-L1-Review-Token";
export const INVITE_HEADER = "X-L1-Invite-Token";

/** Resolve a magic invite code to its pre-filled reviewer name, if configured. */
export async function fetchL1InviteIdentity(
  apiBase: string,
  inviteToken: string,
): Promise<{ reviewer: string | null; auth_method: string } | null> {
  if (!inviteToken) return null;
  try {
    const res = await fetch(`${apiBase}/v1/l1-review/whoami`, {
      headers: { [INVITE_HEADER]: inviteToken },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { valid?: boolean; reviewer?: string | null; auth_method?: string };
    if (!body.valid) return null;
    return { reviewer: body.reviewer ?? null, auth_method: body.auth_method ?? "invite" };
  } catch {
    return null;
  }
}

/** Reads stay token-gated on the Worker; the page calls this without a token, so it
 *  answers "unauthorized" unless the read endpoints are opened. */
export async function fetchL1Reviews(apiBase: string, token = ""): Promise<L1Reviews | "unauthorized" | null> {
  try {
    const headers: Record<string, string> = token ? { [REVIEW_HEADER]: token } : {};
    const res = await fetch(`${apiBase}/v1/l1-review`, { headers, cache: "no-store" });
    if (res.status === 401) return "unauthorized";
    if (!res.ok) return null;
    const body = (await res.json()) as L1Reviews;
    return { reviews: body.reviews ?? [], alt_tags: body.alt_tags ?? [] };
  } catch {
    return null;
  }
}

/** Writes need the reviewer's name (rate-limited per IP on the Worker, or unlimited with an invite code). */
export async function submitL1Review(
  apiBase: string,
  body: Record<string, unknown>,
  inviteToken = "",
): Promise<{ ok: true; id: string; created_at: string } | { ok: false; error: string }> {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (inviteToken) headers[INVITE_HEADER] = inviteToken;
    const res = await fetch(`${apiBase}/v1/l1-review`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const ok = (await res.json().catch(() => ({}))) as { review_id?: string; suggestion_id?: string; created_at?: string };
      return { ok: true, id: ok.review_id ?? ok.suggestion_id ?? "", created_at: ok.created_at ?? new Date().toISOString() };
    }
    const err = (await res.json().catch(() => ({}))) as { error?: string };
    return { ok: false, error: err.error ?? `HTTP ${res.status}` };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

/** Plain-language message for a review-write error code from the Worker. */
export function reviewErrorMessage(code: string): string {
  switch (code) {
    case "invalid_reviewer":
      return "Add your name at the top of the page first (up to 80 characters).";
    case "turnstile_failed":
      return "The anti-bot check failed or expired. It has been reset: wait a moment, then submit again.";
    case "rate_limited":
      return "Too many submissions from this network in the last hour. Please try again shortly.";
    case "daily_limit_reached":
      return "Public submissions have reached today's safety cap. If you have an invite link, reopen it and submit again.";
    case "forbidden_origin":
      return "Submissions must come from the review page.";
    case "review_disabled":
      return "Saving reviews is not switched on for this API yet.";
    case "reason_required":
      return "Say why it is a no.";
    case "residue_required":
      return "Give the residue the tag goes after.";
    default:
      return code;
  }
}

/** What one verdict is a verdict on: a member, a reviewer and one of the member's tag
 *  sites — or the member as a whole, which is what a null `site_id` means. */
function reviewScope(r: L1ReviewRow): string {
  return `${r.design_id}\u0000${r.reviewer}\u0000${r.site_id ?? ""}`;
}

/** Each reviewer's latest verdict per design id (the review log is append-only). */
export function latestVerdicts(rows: readonly L1ReviewRow[]): Map<string, L1ReviewRow[]> {
  const latest = new Map<string, L1ReviewRow>();
  for (const r of [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    latest.set(reviewScope(r), r);
  }
  const out = new Map<string, L1ReviewRow[]>();
  for (const r of latest.values()) {
    const list = out.get(r.design_id) ?? [];
    list.push(r);
    out.set(r.design_id, list);
  }
  return out;
}

/** The reviews that still stand: each reviewer's last word on each scope. The log keeps
 *  every row, so an earlier verdict on the same scope is a changed mind, not a second
 *  opinion, and reads as one unless it is marked. */
export function standingReviewIds(rows: readonly L1ReviewRow[]): Set<string> {
  const latest = new Map<string, string>();
  for (const r of [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    latest.set(reviewScope(r), r.review_id);
  }
  return new Set(latest.values());
}

/** How a verdict's scope reads: the member as a whole for a null site id, otherwise the
 *  arm and where it inserts. A site id the current load no longer carries still names
 *  its arm, so an older row stays legible. */
export function reviewScopeLabel(
  siteId: string | null,
  sites: readonly L1Site[],
  orderedLength: number | null,
): string {
  if (!siteId) return "the member as a whole";
  const arm = armLabel(siteId);
  const site = sites.find((s) => s.site_id === siteId);
  if (!site) return arm ?? siteId;
  return `${arm ? `${arm} — ` : ""}${l1SiteLabel(site, orderedLength)}${site.is_primary === false ? " (alternative)" : ""}`;
}

/** Canonical fingerprint of one tag site (matches the Worker's primary_site_signature format). */
export function l1SiteSignature(
  site: Pick<L1Site, "site_id" | "insert_after_residue" | "leader" | "cassette">,
): string {
  const ins = site.insert_after_residue == null ? "" : String(site.insert_after_residue);
  return `${site.site_id}:${ins}:${site.leader ?? ""}:${site.cassette ?? ""}`;
}

/** Canonical fingerprint of all primary tag sites on a member. */
export function l1PrimarySiteSignature(
  sites: readonly Pick<L1Site, "site_id" | "is_primary" | "insert_after_residue" | "leader" | "cassette">[],
): string {
  return sites
    .filter((s) => s.is_primary !== false)
    .map(l1SiteSignature)
    .sort()
    .join("|");
}

/**
 * Why a recorded review is out of date for the current member, or null when it still applies.
 * Flags both protein-sequence changes (`sequence_sha256`) and tag-location changes
 * (`site_signature`, removed `site_id`, or older `load_version` for pre-signature rows).
 */
export function reviewStaleReason(
  review: Pick<L1ReviewRow, "sequence_sha256" | "site_id" | "site_signature" | "load_version">,
  member: {
    sequence_sha256?: string | null;
    primary_site_signature?: string | null;
    sites?: readonly Pick<L1Site, "site_id" | "is_primary" | "insert_after_residue" | "leader" | "cassette">[];
  },
  currentLoadVersion?: string | null,
): string | null {
  if (review.sequence_sha256 && member.sequence_sha256 && review.sequence_sha256 !== member.sequence_sha256) {
    return "protein sequence changed";
  }
  if (review.site_signature) {
    if (member.sites) {
      if (review.site_id) {
        const cur = member.sites.find((s) => s.site_id === review.site_id);
        if (!cur) return "reviewed tag site was removed";
        if (l1SiteSignature(cur) !== review.site_signature) return "tag location changed";
      } else if (l1PrimarySiteSignature(member.sites) !== review.site_signature) {
        return "tag location changed";
      }
      return null;
    }
    if (member.primary_site_signature != null) {
      if (review.site_id) {
        const parts = member.primary_site_signature ? member.primary_site_signature.split("|") : [];
        if (!parts.includes(review.site_signature)) return "tag location changed";
      } else if (member.primary_site_signature !== review.site_signature) {
        return "tag location changed";
      }
      return null;
    }
  }
  if (review.site_id && member.sites && !member.sites.some((s) => s.site_id === review.site_id)) {
    return "reviewed tag site was removed";
  }
  if (currentLoadVersion && review.load_version && review.load_version !== currentLoadVersion) {
    return "older design load (tag site may have changed)";
  }
  return null;
}

/** Map a residue picked on a model to the member's own numbering (native models only). */
export function modelToMemberResidue(modelResidue: number, structure: Pick<L1Structure, "kind" | "residue_offset">): number | null {
  if (structure.kind !== "native") return null;
  return modelResidue - (structure.residue_offset ?? 0);
}

/**
 * How a model's residues line up with the member's own numbering, for marks and clicks.
 * Native: one shifted segment. Tagged refold: the native stretches around the cassette
 * (and any leader), from taggedModelLayout, which needs no topology. Null when the
 * numbers cannot describe one construct, so nothing is drawn at a wrong residue.
 */
export function l1ResidueSegments(
  member: Pick<L1Member, "ordered_length_aa" | "sites">,
  model: Pick<L1Structure, "kind" | "site_id" | "residue_offset" | "cassette_first_model_residue" | "cassette_last_model_residue" | "model_length_aa">,
): TaggedModelLayout["segments"] | null {
  const L = member.ordered_length_aa;
  if (!L) return null;
  if (model.kind === "native") return [{ unpLo: 1, unpHi: L, offset: model.residue_offset ?? 0 }];
  const site = member.sites.find((s) => s.site_id === model.site_id);
  const cf = model.cassette_first_model_residue;
  const layout = taggedModelLayout({
    memberLength: L,
    insertAfter: site ? site.insert_after_residue : cf != null ? cf - 1 : null,
    leader: site?.leader ?? null,
    cassetteFirst: cf,
    cassetteLast: model.cassette_last_model_residue,
    modelLength: model.model_length_aa,
  });
  return layout ? layout.segments : null;
}

/** Member residue -> model residue, or null where the model does not carry it. */
export function memberToModel(r: number, segments: TaggedModelLayout["segments"] | null): number | null {
  const seg = segments?.find((sg) => r >= sg.unpLo && r <= sg.unpHi);
  return seg ? r + seg.offset : null;
}

/** Model residue -> member residue, or null for cassette / leader / outside residues. */
export function modelToMember(resi: number, segments: TaggedModelLayout["segments"] | null): number | null {
  const seg = segments?.find((sg) => resi - sg.offset >= sg.unpLo && resi - sg.offset <= sg.unpHi);
  return seg ? resi - seg.offset : null;
}

/**
 * Curated contact sites (structures and databases, the gene page's contact overview)
 * are numbered on a UniProt reference sequence. They can be drawn on a member only when
 * the member's ordered protein IS that sequence; otherwise they are listed, not drawn.
 */
export function curatedContactsAlign(
  memberSha: string | null | undefined,
  referenceSha: string | null | undefined,
): boolean {
  return Boolean(memberSha && referenceSha && memberSha === referenceSha);
}

export interface CuratedContacts {
  uniprot_acc: string;
  release_id: string;
  reference_sequence_sha256: string | null;
  sites: { source: string; partner: string; partner_label?: string; positions?: number[]; context?: string;
           reference?: string; observation_id?: string }[];
}

const CONTACT_API =
  process.env.NEXT_PUBLIC_CONTACT_API_BASE ?? "https://api.deliverome.org/surfaceome";

/** The curated contact sites for one accession, straight from the contact API's current
 *  release (extracellular scope). No offline snapshot fallback: the snapshot carries no
 *  reference-sequence hash, and without one a member can never be shown as aligned. */
export async function fetchCuratedContacts(acc: string, signal?: AbortSignal): Promise<CuratedContacts | null> {
  try {
    const rel = await fetch(`${CONTACT_API}/v1/contact-sites/releases/current`, { signal });
    if (!rel.ok) return null;
    const { release_id } = (await rel.json()) as { release_id: string };
    const res = await fetch(`${CONTACT_API}/v1/contact-sites/releases/${release_id}/proteins/${encodeURIComponent(acc)}`, { signal });
    if (!res.ok) return null;
    const g = (await res.json()) as CuratedContacts;
    if (g.release_id !== release_id || !Array.isArray(g.sites)) return null;
    return { ...g, uniprot_acc: acc, reference_sequence_sha256: g.reference_sequence_sha256 ?? null };
  } catch {
    return null;
  }
}


/** The one name for an L1 member's ordered design, everywhere it is shown. */
export const L1_DESIGNED_ORF_LABEL = "Designed ORF (L1)";

/** Where a tagged refold's residues come from, in the model's own numbering. */
export interface TaggedModelLayout {
  /** member residue r is model residue r + offset, for unpLo <= r <= unpHi. */
  segments: { unpLo: number; unpHi: number; offset: number }[];
  cassette: [number, number];
  /** Model residues that are neither the member's native chain nor the cassette:
   *  the residues an Igk leader leaves after cleavage, or a snorkel's TM module. */
  nonNative: [number, number][];
}

/**
 * Lay a tagged refold out against the member's native numbering.
 *
 * The model is [prefix][cassette][tail]. The tail is always the member's C-terminal
 * end, so it is aligned from the end; the prefix is the member's own residues 1..k
 * unless an Igk leader replaced them (then the prefix is the leader's remnant, not
 * native). Whatever prefix residue is not native (a leader remnant, a snorkel module)
 * is reported as non-native rather than painted as protein. Returns null when the
 * numbers cannot describe one construct, so a wrong map never reaches the viewer.
 */
export function taggedModelLayout(a: {
  memberLength: number | null | undefined;
  insertAfter: number | null | undefined;
  leader: string | null | undefined;
  cassetteFirst: number | null | undefined;
  cassetteLast: number | null | undefined;
  modelLength: number | null | undefined;
}): TaggedModelLayout | null {
  const L = a.memberLength, ins = a.insertAfter, cf = a.cassetteFirst, cl = a.cassetteLast, ml = a.modelLength;
  if (![L, ins, cf, cl, ml].every((v) => Number.isInteger(v))) return null;
  const [len, after, first, last, model] = [L, ins, cf, cl, ml] as number[];
  if (len < 1 || after < 0 || after > len || first < 1 || last < first || last > model) return null;
  const tail = model - last;
  if (tail > len) return null;
  const prefix = a.leader ? 0 : Math.max(0, Math.min(after, first - 1, len - tail));
  const segments: TaggedModelLayout["segments"] = [];
  if (prefix > 0) segments.push({ unpLo: 1, unpHi: prefix, offset: 0 });
  if (tail > 0) segments.push({ unpLo: len - tail + 1, unpHi: len, offset: last - (len - tail) });
  const nonNative: [number, number][] = prefix + 1 <= first - 1 ? [[prefix + 1, first - 1]] : [];
  return { segments, cassette: [first, last], nonNative };
}

/**
 * One gene-page structure tab per current L1 member with a built pick: the refold of
 * the WHOLE ordered tagged protein, its cassette laid out for its own colour.
 *
 * Paired with the member's v1 topology by design id AND ordered-length (and sequence
 * sha when both carry one), for the same reason libraryStructureVariants pairs by
 * candidate id: a model coloured with another proteoform's topology looks plausible.
 */
export function l1TaggedStructureVariants(
  file: L1DesignFile | null,
  topologyRows: readonly LibraryTopologyRow[] | null | undefined,
): StructureVariantLibraryInput[] {
  if (!file) return [];
  const out: StructureVariantLibraryInput[] = [];
  for (const m of file.members) {
    if (!m.design_id) continue;
    const site = m.sites.find((s) => s.is_primary && s.status === "built");
    if (!site) continue;
    const fold =
      m.structures.find((st) => st.kind === "tagged" && st.site_id === site.site_id && st.is_chosen) ??
      m.structures.find((st) => st.kind === "tagged" && st.site_id === site.site_id);
    if (!fold) continue;
    const url = l1StructureUrl(fold);
    const topo = (topologyRows ?? []).find(
      (t) =>
        t.candidate_id === m.design_id &&
        (t.per_residue_topology ?? "").length === m.ordered_length_aa &&
        (!m.sequence_sha256 ||
          !(t as { sequence_sha256?: string | null }).sequence_sha256 ||
          (t as { sequence_sha256?: string | null }).sequence_sha256 === m.sequence_sha256),
    );
    const layout = taggedModelLayout({
      memberLength: m.ordered_length_aa,
      insertAfter: site.insert_after_residue,
      leader: site.leader,
      cassetteFirst: fold.cassette_first_model_residue,
      cassetteLast: fold.cassette_last_model_residue,
      modelLength: fold.model_length_aa,
    });
    if (!url || !layout || !m.ordered_length_aa) continue;
    // No v1 topology for this exact sequence (newer designs are not in the topology
    // table yet): draw the native chain uncoloured rather than drop the tab, so every
    // built pick still shows its tag. "?" is no topology state, so nothing paints it.
    const topology = topo?.per_residue_topology ?? "?".repeat(m.ordered_length_aa);
    const type = topo?.per_residue_topology ? deepTMHMMType(topology) : (m.n_tm ?? 0) > 0 ? "TM" : "SP";
    const verdict = fold.refold_verdict ? `, refold ${fold.refold_verdict}` : "";
    out.push({
      source: "library",
      id: `library-tagged-${m.design_id}`,
      label: L1_DESIGNED_ORF_LABEL,
      sublabel: `${m.design_id}${topo ? ` · ${libraryVariantLabel(topo)}` : ""}`,
      topology,
      deeptmhmm_type: type,
      pdb_url: url,
      candidate_id: m.design_id,
      tranche: "l1",
      candidate_set: m.candidate_set,
      model_source: fold.source,
      proteoform_match: "tagged_construct",
      residue_offset: 0,
      display_range: null,
      note:
        `The ordered tagged protein (${m.rung}, ${m.member_id}), folded whole: ` +
        `the ${layout.cassette[1] - layout.cassette[0] + 1}-aa cassette is orange` +
        (layout.nonNative.length ? ", other non-native residues olive" : "") +
        `${verdict}.` +
        (topo ? "" : " No topology for this exact sequence yet, so the native chain is uncoloured."),
      segments: layout.segments,
      cassette_range: layout.cassette,
      nonnative_ranges: layout.nonNative,
      refold_verdict: fold.refold_verdict ?? null,
    });
  }
  return out;
}

/**
 * The library tabs the gene page shows once the L1 design load is in hand: each current
 * L1 member's tagged refold replaces its native tab, and a tab for an L1 design that is
 * no longer a member is dropped (TFRC's retired 81-aa isoform l1-p2520 was the case:
 * the stale native tab read as "a tiny fragment"). Non-L1 tabs pass through. Without
 * the load nothing changes.
 */
export function withL1DesignVariants(
  libraryTabs: StructureVariantLibraryInput[],
  file: L1DesignFile | null,
  topologyRows: readonly LibraryTopologyRow[] | null | undefined,
): StructureVariantLibraryInput[] {
  if (!file || !file.members.length) return libraryTabs;
  const current = new Set(file.members.map((m) => m.design_id).filter(Boolean) as string[]);
  const tagged = l1TaggedStructureVariants(file, topologyRows);
  const replaced = new Set(tagged.map((t) => t.candidate_id));
  const kept = libraryTabs.filter((t) => {
    const isL1 = (t.tranche ?? "").toLowerCase() === "l1" || t.candidate_id.startsWith("l1-");
    if (!isL1) return true;
    return current.has(t.candidate_id) && !replaced.has(t.candidate_id);
  });
  return [...tagged, ...kept];
}

/** Library-membership marks once the load is in hand: a retired L1 design marks no tab,
 *  and a member with its own Designed ORF (L1) entry marks only that entry. */
export function currentL1Memberships<T extends { candidate_id: string; library: string | null }>(
  byAcc: Map<string, T[]>,
  file: L1DesignFile | null,
): Map<string, T[]> {
  if (!file || !file.members.length) return byAcc;
  const current = new Set(file.members.map((m) => m.design_id).filter(Boolean) as string[]);
  // A member shown as its own Designed ORF (L1) entry is not ALSO badged "L1" on the
  // canonical / isoform tab of the same sequence: one entry for the construct.
  const designed = new Set(l1TaggedStructureVariants(file, []).map((v) => v.candidate_id));
  const out = new Map<string, T[]>();
  for (const [acc, ms] of byAcc) {
    const keep = ms.filter((m) => {
      if ((m.library ?? "").toLowerCase() !== "l1") return true;
      return current.has(m.candidate_id) && !designed.has(m.candidate_id);
    });
    if (keep.length) out.set(acc, keep);
  }
  return out;
}

// ------------------------------------------------- review-page browsing and topology

/**
 * Per-residue topology for the proteins the L1 members encode, from the gene record.
 *
 * The `/v1/l1-design` payload carries `topology_version` but not the string itself; the
 * strings live on the gene record at
 * `deterministic_features.library_designed_topology`, one row per library candidate,
 * keyed by `candidate_id` (which IS the member's `design_id`). Fetched here rather than
 * threaded down from the gene page because the review browser is a client component that
 * never renders inside a gene page.
 *
 * Returns `[]` for any failure: the strip is an aid, so a missing topology must degrade
 * to "no strip", never to a strip drawn from something else.
 */
async function sha256Hex(text: string): Promise<string | null> {
  try {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) return null;
    const buf = await subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}

interface RawGeneTopology {
  per_residue_topology?: string | null;
  sequence?: string | null;
  uniprot_acc?: string | null;
  isoform_id?: string | null;
}

export interface L1GeneContext {
  /** First sentence of the gene record's executive summary (e.g. topology / GPI / complex context). */
  summary: string | null;
  coReceptor: {
    dependency: string;
    partners: string[];
    rationale: string | null;
  } | null;
  shedding: {
    present: boolean;
    severity: string | null;
    sheddase: string | null;
    mechanism: string | null;
    rationale: string | null;
  } | null;
  epitopeMasking: {
    mechanisms: string[];
    severity: string | null;
    rationale: string | null;
  } | null;
  homoOligomer: {
    stoichiometry: number | null;
    isEcdOnly: boolean;
    source: string | null;
  } | null;
}

/** Strip internal ledger evidence IDs like `(a1_evi_01, a2_evi_05)` from gene-record prose. */
function cleanGeneProse(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const cleaned = raw
    .replace(/\s*\((?:[a-z]\d+_evi_\d+(?:\s*,\s*)?)+\)/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  return cleaned || null;
}

function firstSentence(raw: string | null | undefined): string | null {
  const s = cleanGeneProse(raw);
  if (!s) return null;
  const m = /^(.+?[.!?])(?:\s|$)/.exec(s);
  return m ? m[1] : s;
}

export function extractL1GeneContext(body: unknown): L1GeneContext | null {
  if (!body || typeof body !== "object") return null;
  const d = body as Record<string, unknown>;
  const exec = d.executive_summary as { one_paragraph?: string | null } | null | undefined;
  const ar = d.accessibility_risks as Record<string, unknown> | null | undefined;
  const cr = ar?.co_receptor_requirements as {
    surface_expression_dependency?: string | null;
    partners?: string[] | null;
    rationale?: string | null;
  } | null | undefined;
  const sh = ar?.shed_form as {
    present?: boolean | null;
    severity?: string | null;
    sheddase_if_known?: string | null;
    mechanism?: string | null;
    rationale?: string | null;
  } | null | undefined;
  const em = ar?.epitope_masking as {
    mechanism?: string[] | null;
    severity?: string | null;
    rationale?: string | null;
  } | null | undefined;
  const ho = ar?.homo_oligomerization_prediction as {
    present?: boolean | null;
    stoichiometry?: number | null;
    is_ecd_only?: boolean | null;
    source?: string | null;
  } | null | undefined;

  const summary = firstSentence(exec?.one_paragraph);
  const partners = Array.isArray(cr?.partners) ? cr.partners.filter((p): p is string => typeof p === "string" && !!p.trim()) : [];
  const dep = cr?.surface_expression_dependency ?? "";
  const coReceptor =
    (dep && dep !== "none" && dep !== "unknown") || partners.length > 0
      ? { dependency: dep || "partner", partners, rationale: firstSentence(cr?.rationale) }
      : null;
  const shedding = sh?.present
    ? {
        present: true,
        severity: sh.severity ?? null,
        sheddase: sh.sheddase_if_known ?? null,
        mechanism: cleanGeneProse(sh.mechanism),
        rationale: firstSentence(sh.rationale),
      }
    : null;
  const mechanisms = Array.isArray(em?.mechanism)
    ? em.mechanism.filter((x): x is string => typeof x === "string" && !!x.trim() && x !== "none")
    : [];
  const epitopeMasking =
    mechanisms.length > 0
      ? { mechanisms, severity: em?.severity ?? null, rationale: firstSentence(em?.rationale) }
      : null;
  const homoOligomer = ho?.present
    ? {
        stoichiometry: ho.stoichiometry ?? null,
        isEcdOnly: !!ho.is_ecd_only,
        source: ho.source ?? null,
      }
    : null;

  if (!summary && !coReceptor && !shedding && !epitopeMasking && !homoOligomer) return null;
  return { summary, coReceptor, shedding, epitopeMasking, homoOligomer };
}

export async function fetchL1GeneData(
  symbol: string,
  apiBase: string,
  signal?: AbortSignal,
): Promise<{ topologies: LibraryTopologyRow[]; context: L1GeneContext | null }> {
  try {
    const res = await fetch(`${apiBase}/v1/genes/${encodeURIComponent(symbol)}`, { signal });
    if (!res.ok) return { topologies: [], context: null };
    const body = (await res.json()) as {
      deterministic_features?: {
        library_designed_topology?: LibraryTopologyRow[] | null;
        canonical_topology?: RawGeneTopology | null;
        isoform_topologies?: RawGeneTopology[] | null;
      } | null;
    };
    const df = body?.deterministic_features;
    const rows: LibraryTopologyRow[] = Array.isArray(df?.library_designed_topology)
      ? [...df.library_designed_topology]
      : [];
    // Fallback for genes whose record omits `library_designed_topology` (e.g. C5orf15):
    // include canonical / isoform topologies keyed strictly by SHA-256 of their sequence,
    // so l1MemberTopology only accepts them on an exact byte-for-byte sequence match.
    const extras: { raw: RawGeneTopology; cohort: string }[] = [];
    if (df?.canonical_topology) extras.push({ raw: df.canonical_topology, cohort: "human_canonical" });
    if (Array.isArray(df?.isoform_topologies)) {
      for (const iso of df.isoform_topologies) extras.push({ raw: iso, cohort: "human_isoform" });
    }
    for (const { raw, cohort } of extras) {
      if (!raw.per_residue_topology || !raw.sequence) continue;
      if (raw.per_residue_topology.length !== raw.sequence.length) continue;
      const hash = await sha256Hex(raw.sequence);
      if (!hash) continue;
      rows.push({
        per_residue_topology: raw.per_residue_topology,
        ordered_length_aa: String(raw.per_residue_topology.length),
        sequence_sha256: hash,
        cohort,
        topology_acc: raw.isoform_id ?? raw.uniprot_acc ?? undefined,
      });
    }
    return { topologies: rows, context: extractL1GeneContext(body) };
  } catch {
    return { topologies: [], context: null };
  }
}

export async function fetchL1MemberTopologies(
  symbol: string,
  apiBase: string,
  signal?: AbortSignal,
): Promise<LibraryTopologyRow[]> {
  return (await fetchL1GeneData(symbol, apiBase, signal)).topologies;
}

export interface L1RefoldMetric {
  label: string;
  value: string;
  tone: "pass" | "warn" | "neutral";
  help: string;
}

/**
 * Parse quantitative refold QC metrics (`TM to native`, `site lDDT`, `native-region lDDT`,
 * `SpyTag003 RSA`, `ALFA RSA`) out of `model.note` and/or `site.status_detail` so they can
 * be shown as structured metric pills rather than buried in a muted caption.
 */
export function parseRefoldMetrics(
  ...sources: (string | null | undefined)[]
): L1RefoldMetric[] {
  const joined = sources.filter(Boolean).join("; ");
  if (!joined) return [];
  const out: L1RefoldMetric[] = [];
  const seen = new Set<string>();
  const add = (m: L1RefoldMetric) => {
    if (!seen.has(m.label)) {
      seen.add(m.label);
      out.push(m);
    }
  };

  const tm = /TM to native\s+([0-9.]+)/i.exec(joined);
  if (tm) {
    const v = Number(tm[1]);
    add({
      label: "TM to native",
      value: tm[1],
      tone: v >= 0.8 ? "pass" : "warn",
      help: "TM-score comparing the tagged refold to the native structure (≥0.80 = fold preserved).",
    });
  }
  const siteLddt = /(?:site lDDT|lDDT within 15 of the site)\s+([0-9.]+)/i.exec(joined);
  if (siteLddt) {
    const v = Number(siteLddt[1]);
    add({
      label: "Site lDDT",
      value: siteLddt[1],
      tone: v >= 0.7 ? "pass" : "warn",
      help: "Local structural preservation within 15 residues of the tag insertion (≥0.70 target).",
    });
  }
  const natLddt = /native-region lDDT\s+([0-9.]+)/i.exec(joined);
  if (natLddt) {
    const v = Number(natLddt[1]);
    add({
      label: "Native lDDT",
      value: natLddt[1],
      tone: v >= 0.85 ? "pass" : "warn",
      help: "Overall structural preservation across native residues (≥0.85 target).",
    });
  }
  const spy = /SpyTag003\s+(?:buried\s*\()?RSA\s+([0-9.]+)/i.exec(joined);
  if (spy) {
    const v = Number(spy[1]);
    const buried = /SpyTag003\s+buried/i.test(joined) || v < 0.35;
    add({
      label: "SpyTag003 RSA",
      value: spy[1],
      tone: buried ? "warn" : "pass",
      help: "Relative solvent accessibility of SpyTag003 in the tagged refold (higher = more surface-exposed).",
    });
  }
  const alfa = /ALFA\s+(?:buried\s*\()?RSA\s+([0-9.]+)/i.exec(joined);
  if (alfa) {
    const v = Number(alfa[1]);
    const buried = /ALFA\s+buried/i.test(joined) || v < 0.35;
    add({
      label: "ALFA RSA",
      value: alfa[1],
      tone: buried ? "warn" : "pass",
      help: "Relative solvent accessibility of the ALFA control tag in the tagged refold (higher = more exposed).",
    });
  }
  return out;
}

const DECISION_LABELS: Record<string, string> = {
  internal_loop: "Internal extracellular loop",
  igk_swap: "Igκ leader replaces native signal peptide",
  igk_res1: "Igκ leader added before residue 1",
  native_site: "Tag after native signal-peptide cleavage",
  tag_alone: "N-terminal tag without Igκ leader",
  hold_no_passing_arm: "Retained after manual review (no arm passed automated refold thresholds)",
  ranked_proposal: "Runner-up candidate (ranker)",
  "ranked proposal": "Runner-up candidate (ranker)",
  snorkel: "C-terminal snorkel TM-module tag",
};

/** Translate raw internal `decision` tokens into plain-English labels for external scientists. */
export function explainDecision(decision: string | null | undefined): string | null {
  if (!decision) return null;
  const key = decision.trim();
  return DECISION_LABELS[key] ?? key;
}

/**
 * Plain-English explanation of WHY this member uses its assigned tagging strategy
 * (e.g., why neither N- nor C-terminus was free on dual-anchor/intracellular-termini proteins like BST2).
 */
export function explainRungContext(
  member: Pick<L1Member, "rung" | "sites">,
  topology: string | null | undefined,
  geneContext: L1GeneContext | null | undefined,
): string | null {
  const rung = member.rung.toLowerCase();
  const primary = member.sites.find((s) => s.is_primary !== false);
  const first = topology?.[0] ?? null;
  const last = topology && topology.length > 0 ? topology[topology.length - 1] : null;
  const gpiMention = !!(geneContext?.summary && /\bgpi\b/i.test(geneContext.summary));

  if (rung === "internal" || rung.includes("internal")) {
    const reasons: string[] = [];
    if (first === "I") reasons.push("N-terminus is intracellular");
    else if (first === "M") reasons.push("N-terminus starts in a TM helix");
    if (gpiMention) reasons.push("C-terminus is GPI-anchored");
    else if (last === "I") reasons.push("C-terminus is intracellular");
    else if (last === "M") reasons.push("C-terminus ends in a TM helix");
    if (reasons.length === 2) {
      return `Tagged in an internal extracellular loop because neither terminus is free for extracellular tagging (${reasons.join("; ")}).`;
    }
    if (reasons.length === 1) {
      return `Tagged in an internal extracellular loop (${reasons[0]}).`;
    }
    return "Tagged in an exposed internal extracellular loop selected to avoid binding sites and preserve native folding.";
  }
  if (rung.startsWith("n after sp")) {
    if (primary?.leader?.toLowerCase().startsWith("igk")) {
      return "Extracellular N-terminus with a native signal peptide; swapped for the Igκ leader so the N-terminal tag cleaves cleanly and stays exposed.";
    }
    return "Extracellular N-terminus with a native signal peptide; tag placed immediately after the native SP cleavage site.";
  }
  if (rung.startsWith("n at residue 1")) {
    if (primary?.leader?.toLowerCase().startsWith("igk")) {
      return "Extracellular N-terminus without a native signal peptide; Igκ leader added ahead of residue 1 to direct surface translocation of the tag.";
    }
    return "Extracellular N-terminus without a native signal peptide; tag placed directly at residue 1.";
  }
  if (rung.includes("c-term")) {
    if (primary?.cassette?.toLowerCase().includes("snorkel")) {
      return "Intracellular C-terminus; uses a C-terminal snorkel TM module to project the SpyTag003 + ALFA tag into the extracellular space.";
    }
    return "Extracellular C-terminus; tag placed at the free C-terminal end without disrupting internal loops.";
  }
  return null;
}

export interface L1NearestContact {
  distanceAa: number;
  residue: number;
  label: string;
}

export interface L1ExternalTagSite {
  site_id: string;
  provenance: string;
  site_kind: string;
  insert_after_residue: number | null;
  residue_before?: string | null;
  residue_after?: string | null;
  residue_label?: string | null;
  extracellular: boolean;
  tag_type: string;
  rationale?: string | null;
  functional_impact_measured?: string | null;
  validation_level?: string | null;
  sources?: { pmid?: string | null; doi?: string | null }[];
}

export interface L1RenderableExternalTagSite {
  siteId: string;
  residue: number;
  isTedman: boolean;
  tagType: string;
  siteKind: string;
}

export function isL1LiteratureTagProvenance(provenance: string): boolean {
  return provenance === "literature_retrieved" || provenance === "literature_enriched";
}

/**
 * Fetch published literature tag sites and Tedman screen-validated controls from
 * `/v1/tag-sites/{SYMBOL}`, excluding legacy deterministic_computed candidates and
 * non-rendered validated_literature rows.
 */
export async function fetchL1ExternalTagSites(
  symbol: string,
  apiBase: string,
  signal?: AbortSignal,
): Promise<L1ExternalTagSite[]> {
  try {
    const res = await fetch(`${apiBase}/v1/tag-sites/${encodeURIComponent(symbol)}`, { signal });
    if (!res.ok) return [];
    const body = (await res.json()) as { sites?: unknown };
    if (!Array.isArray(body?.sites)) return [];
    return (body.sites as L1ExternalTagSite[]).filter(
      (s) =>
        s &&
        typeof s.site_id === "string" &&
        (s.provenance === "screen_validated" || isL1LiteratureTagProvenance(s.provenance)),
    );
  } catch {
    return [];
  }
}

/** Resolve extracellular literature & Tedman tag sites to 1-indexed canonical residues. */
export function renderableExternalTagSites(
  sites: readonly L1ExternalTagSite[],
  length: number,
): L1RenderableExternalTagSite[] {
  if (length <= 0) return [];
  const out: L1RenderableExternalTagSite[] = [];
  const seen = new Set<string>();
  for (const s of sites) {
    const isTedman = s.provenance === "screen_validated";
    if (!isTedman && !isL1LiteratureTagProvenance(s.provenance)) continue;
    if (!isTedman && !s.extracellular && s.site_kind !== "terminal_n") continue;
    // Unpinned internal sites stay in the table only; never collapse them onto residue 1.
    const raw =
      s.site_kind === "terminal_c"
        ? length
        : s.site_kind === "terminal_n"
          ? s.insert_after_residue || 1
          : (s.insert_after_residue ?? 0);
    if (raw < 1 || raw > length) continue;
    const key = `${isTedman ? "t" : "l"}:${s.site_kind}:${raw}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ siteId: s.site_id, residue: raw, isTedman, tagType: s.tag_type || (isTedman ? "HA" : "tag"), siteKind: s.site_kind });
  }
  return out;
}

/**
 * Sequence distance (in aa) from a tag insertion residue to the nearest annotated
 * contact residue (curated PDB/DB, UniProt binding, or visible literature contacts).
 */
export function nearestContactInfo(
  insertAfter: number | null | undefined,
  contacts: readonly L1Contact[],
  curatedPositions: ReadonlySet<number>,
): L1NearestContact | null {
  if (insertAfter == null) return null;
  let best: L1NearestContact | null = null;
  for (const pos of curatedPositions) {
    const dist = Math.abs(pos - insertAfter);
    if (!best || dist < best.distanceAa) {
      best = { distanceAa: dist, residue: pos, label: `curated contact (${pos})` };
    }
  }
  for (const c of contacts) {
    if (c.confidence_tier === "hidden") continue;
    const dist = Math.abs(c.residue - insertAfter);
    if (!best || dist < best.distanceAa) {
      const src = c.source === "uniprot_binding" ? "UniProt binding" : "literature contact";
      best = { distanceAa: dist, residue: c.residue, label: `${src} (${c.aa ?? ""}${c.residue})` };
    }
  }
  return best;
}

/**
 * The topology row that describes THIS member's ordered protein, or null.
 *
 * Paired by `candidate_id` == `design_id` (or, when the gene record lacks a
 * `library_designed_topology` row for this member, by exact `sequence_sha256` match
 * against a canonical/isoform topology row) and checked for length agreement.
 */
export function l1MemberTopology(
  rows: readonly LibraryTopologyRow[] | null | undefined,
  member: Pick<L1Member, "design_id" | "ordered_length_aa"> & { sequence_sha256?: string | null },
): LibraryTopologyRow | null {
  if (!rows?.length) return null;
  const byId = member.design_id
    ? rows.find((r) => r.candidate_id && r.candidate_id === member.design_id)
    : undefined;
  const row =
    byId ??
    (member.sequence_sha256
      ? rows.find((r) => !r.candidate_id && r.sequence_sha256 === member.sequence_sha256)
      : undefined);
  const topo = row?.per_residue_topology ?? "";
  if (!row || !topo) return null;
  // Sequence is the match of record: when both sides carry a hash they must agree, so a
  // redesigned member that kept its design id never borrows the old protein's topology.
  const rowSha = row.sequence_sha256 ?? null;
  if (member.sequence_sha256 && rowSha && rowSha !== member.sequence_sha256) return null;
  // Only the v1 alphabet is drawn; a row from another tool is not this palette's input.
  if (row.tool && row.tool !== "deeptmhmm_v1") return null;
  // `ordered_length_aa` arrives as a string on the record's rows and as a number on the
  // design payload, so compare numerically rather than by identity.
  const rowLen = Number(row.ordered_length_aa ?? NaN);
  if (Number.isFinite(rowLen) && rowLen !== topo.length) return null;
  const memberLen = member.ordered_length_aa;
  if (memberLen != null && memberLen !== topo.length) return null;
  return row;
}

/** The topology states actually present in a string, in legend order. */
export function topologyStatesPresent(topology: string): string[] {
  const seen = new Set(topology);
  return ["M", "O", "I", "S", "B"].filter((s) => seen.has(s));
}

/**
 * One entry per gene, holding that gene's members in the browsing order they already
 * have.
 *
 * `filterIndex` sorts by gene symbol then member id, so a gene's members are already
 * adjacent; grouping preserves that order, which is what lets the ← → keys keep walking
 * member by member (nothing is skipped) while the list shows one entry per gene with its
 * library reference, isoform and ortholog members as tabs.
 */
export interface L1GeneGroup<T extends { gene_symbol: string }> {
  gene_symbol: string;
  members: T[];
  /** Index of this group's first member in the flat, filtered member list. */
  firstIndex: number;
}

export function groupByGene<T extends { gene_symbol: string }>(
  members: readonly T[],
): L1GeneGroup<T>[] {
  const out: L1GeneGroup<T>[] = [];
  members.forEach((m, i) => {
    const last = out[out.length - 1];
    if (last && last.gene_symbol === m.gene_symbol) last.members.push(m);
    else out.push({ gene_symbol: m.gene_symbol, members: [m], firstIndex: i });
  });
  return out;
}

/**
 * What to call a member on its gene's tab strip: the proteoform it encodes when the
 * topology row says (`libraryVariantLabel` reads the topology *cohort*, which is the only
 * field that knows whether a `library_reference` member is really the canonical or an
 * isoform), otherwise the coarse candidate_set + species the index carries.
 */
export function l1MemberTabLabel(
  member: Pick<L1IndexMember, "candidate_set" | "species">,
  topology?: LibraryTopologyRow | null,
): string {
  if (topology) return libraryVariantLabel(topology);
  const set = (member.candidate_set ?? "").toLowerCase();
  const species = (member.species ?? "").toLowerCase();
  if (set === "ortholog") return species ? `${species[0].toUpperCase()}${species.slice(1)} ortholog` : "Ortholog";
  if (set === "isoform") return "Isoform";
  if (set === "library_reference") return species && species !== "human" ? `Reference (${species})` : "Reference";
  if (set === "expression_rescue") return "Rescue arm";
  return set ? set.replace(/_/g, " ") : "Member";
}

/**
 * Member chip wording on the review page. Every chip is a DESIGNED member, so the first
 * word says which library CDS it is (reference / isoform / ortholog), never a word that
 * could read as "the design vs something else". With the member's topology row in hand
 * it adds the protein that CDS orders: "UniProt canonical" when the reference orders
 * exactly UniProt's canonical sequence, "designed ORF" for an Ensembl-transcript
 * product with no UniProt entry of its own. SMIM7 is the case that read wrongly:
 * "Canonical 75 aa" and "Designed ORF 103 aa" looked like a canonical-vs-design toggle,
 * when they are the reference member and the isoform member, both ordered.
 */
export function l1MemberRoleLabel(member: Pick<L1IndexMember, "candidate_set" | "species">): string {
  const set = (member.candidate_set ?? "").toLowerCase();
  const species = (member.species ?? "").toLowerCase();
  const sp = species ? `${species[0].toUpperCase()}${species.slice(1)}` : "";
  if (set === "library_reference") return species && species !== "human" ? `${sp} reference CDS` : "Reference CDS";
  if (set === "isoform") return "Isoform CDS";
  if (set === "ortholog") return sp ? `${sp} ortholog CDS` : "Ortholog CDS";
  if (set === "expression_rescue") return "Rescue-arm CDS";
  return set ? `${set.replace(/_/g, " ")} CDS` : "Member CDS";
}

/** What protein a member's CDS orders, from its topology row's cohort; null if unknown. */
export function l1OrderedProteinLabel(topology: LibraryTopologyRow | null | undefined): string | null {
  if (!topology) return null;
  const cohort = (topology.cohort ?? "").toLowerCase();
  if (cohort === "human_canonical") return "UniProt canonical";
  if (cohort.startsWith("human_isoform")) {
    const m = /-(\d+)$/.exec(topology.topology_acc ?? "");
    return m ? `UniProt isoform ${m[1]}` : "UniProt isoform";
  }
  if (cohort === "library_designed_orf") return "designed ORF (no UniProt entry)";
  if (cohort.startsWith("cyno") || cohort.startsWith("mouse")) return topology.topology_acc ? `UniProt ${topology.topology_acc}` : null;
  return null;
}

/**
 * Index of the next member whose gene starts with `letter`, searching forward from
 * `from` and wrapping, so pressing the same letter again walks that letter's genes
 * instead of sticking on the first one. -1 when no gene in view starts with it.
 */
export function nextIndexByLetter(
  members: readonly { gene_symbol: string }[],
  letter: string,
  from: number,
): number {
  const L = letter.toUpperCase();
  if (!members.length || L.length !== 1) return -1;
  const start = from < 0 ? 0 : from;
  // step runs to members.length so the last candidate examined is `start` itself: when
  // one gene is the letter's only match, pressing the key again stays on it rather than
  // reporting "no such letter", which would read as a broken key.
  for (let step = 1; step <= members.length; step += 1) {
    const i = (start + step) % members.length;
    if (members[i].gene_symbol.toUpperCase().startsWith(L)) return i;
  }
  return -1;
}

// ------------------------------------------------- membrane + side shading on L1 models

/** How a model's residues relate to the member's ordered protein, for side shading. */
export interface L1ModelMap {
  /** member residue r is model residue r + offset, for unpLo <= r <= unpHi. */
  segments: { unpLo: number; unpHi: number; offset: number }[];
  /** Tagged refolds: the cassette, in model numbering. */
  cassette: [number, number] | null;
  /** Model residues that are neither native nor cassette (an Igk leader remnant). */
  nonNative: [number, number][];
  /** Topology state of the residue the cassette is inserted after (residue 1 for an
   *  N-terminal or Igk-led tag): the side of the membrane the tag is designed to sit on. */
  cassetteSide: string | null;
  /** Set when the refold's site is not in the member's site list (a refold of an earlier
   *  pick): the residue its cassette follows, read off the model itself. */
  unlistedSiteInsertAfter?: number | null;
}

/**
 * Map one of a member's models onto the member's own numbering, so the member's v1
 * topology can be painted on it. Native: one shift by `residue_offset`. Tagged: the
 * piecewise layout around the cassette ({@link taggedModelLayout}). Null when the
 * numbers do not describe one construct; the caller then draws no shading rather than
 * shading drawn from a wrong map.
 */
export function l1ModelMap(
  member: Pick<L1Member, "ordered_length_aa" | "sites">,
  model: Pick<L1Structure, "kind" | "site_id" | "residue_offset" | "cassette_first_model_residue" | "cassette_last_model_residue" | "model_length_aa">,
  topology: string,
): L1ModelMap | null {
  const L = member.ordered_length_aa ?? topology.length;
  if (!topology || L !== topology.length) return null;
  if (model.kind === "native") {
    return { segments: [{ unpLo: 1, unpHi: L, offset: model.residue_offset ?? 0 }], cassette: null, nonNative: [], cassetteSide: null };
  }
  const site = member.sites.find((s) => s.site_id === model.site_id);
  if (!site) {
    // A refold whose site id is no longer among the member's sites (a refold of an
    // earlier pick). Map it from the model alone, and only when the numbers leave no
    // room for a leader or any other non-native residue: native 1..k, cassette, then
    // native k+1..L to the end of the model.
    const cf = model.cassette_first_model_residue, cl = model.cassette_last_model_residue, ml = model.model_length_aa;
    if (cf == null || cl == null || ml == null || cf - 1 + (ml - cl) !== L || cf < 1) return null;
    const after = cf - 1;
    const layout = taggedModelLayout({ memberLength: L, insertAfter: after, leader: null, cassetteFirst: cf, cassetteLast: cl, modelLength: ml });
    if (!layout || layout.nonNative.length) return null;
    return {
      segments: layout.segments, cassette: layout.cassette, nonNative: [],
      cassetteSide: topology.charAt(Math.max(after, 1) - 1) || null, unlistedSiteInsertAfter: after,
    };
  }
  const layout = taggedModelLayout({
    memberLength: L,
    insertAfter: site.insert_after_residue,
    leader: site.leader,
    cassetteFirst: model.cassette_first_model_residue,
    cassetteLast: model.cassette_last_model_residue,
    modelLength: model.model_length_aa,
  });
  if (!layout) return null;
  const ins = site.insert_after_residue ?? 0;
  const at = site.leader || ins < 1 ? 1 : Math.min(ins, L);
  return { segments: layout.segments, cassette: layout.cassette, nonNative: layout.nonNative, cassetteSide: topology.charAt(at - 1) || null };
}

/** Runs of one topology state, already projected into MODEL numbering. */
export function l1ModelStateRuns(topology: string, map: Pick<L1ModelMap, "segments">): { state: string; lo: number; hi: number }[] {
  const out: { state: string; lo: number; hi: number }[] = [];
  let start = 1;
  for (let i = 1; i <= topology.length; i += 1) {
    const st = topology.charAt(i - 1);
    if (i < topology.length && topology.charAt(i) === st) continue;
    for (const seg of map.segments) {
      const a = Math.max(start, seg.unpLo);
      const b = Math.min(i, seg.unpHi);
      if (b >= a) out.push({ state: st, lo: a + seg.offset, hi: b + seg.offset });
    }
    start = i + 1;
  }
  return out;
}

/** Model residue -> member residue through a map's segments; null off the native chain. */
export function l1ModelToMember(map: Pick<L1ModelMap, "segments">): (modelResi: number) => number | null {
  return (r: number) => {
    for (const s of map.segments) if (r >= s.unpLo + s.offset && r <= s.unpHi + s.offset) return r - s.offset;
    return null;
  };
}

/** Half-thickness of the drawn bilayer, from the TM-helix midplane: the ~30 Å
 *  hydrocarbon core. */
export const L1_MEMBRANE_HALF_THICKNESS = 15;
