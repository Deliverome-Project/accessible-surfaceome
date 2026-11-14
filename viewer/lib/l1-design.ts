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
import { STRUCTURES_BASE } from "./structure-viewer-types";

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

/** Members in the browser's order, filtered by rung / class / free text. */
export function filterIndex(
  members: readonly L1IndexMember[],
  f: { rung?: string; membraneClass?: string; query?: string; status?: string },
): L1IndexMember[] {
  const q = (f.query ?? "").trim().toUpperCase();
  return members
    .filter((m) => !f.rung || m.rung === f.rung)
    .filter((m) => !f.membraneClass || m.membrane_class === f.membraneClass)
    .filter((m) => !f.status || (f.status === "none" ? m.pick_status.length === 0 : m.pick_status.includes(f.status as L1SiteStatus)))
    .filter(
      (m) =>
        !q ||
        m.gene_symbol.toUpperCase().includes(q) ||
        m.member_id.toUpperCase() === q ||
        (m.design_id ?? "").toUpperCase() === q,
    )
    .sort((a, b) => a.gene_symbol.localeCompare(b.gene_symbol) || a.member_id.localeCompare(b.member_id));
}

export function countBy<T>(rows: readonly T[], key: (r: T) => string): [string, number][] {
  const m = new Map<string, number>();
  for (const r of rows) m.set(key(r), (m.get(key(r)) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

export async function fetchL1Design(symbol: string, apiBase: string): Promise<L1DesignFile | null> {
  try {
    const res = await fetch(`${apiBase}/v1/l1-design/${encodeURIComponent(symbol)}`);
    if (!res.ok) return null;
    return parseL1Design(await res.json());
  } catch {
    return null;
  }
}

export async function fetchL1Index(apiBase: string): Promise<L1Index | null> {
  try {
    const res = await fetch(`${apiBase}/v1/l1-design`);
    if (!res.ok) return null;
    return parseL1Index(await res.json());
  } catch {
    return null;
  }
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
  gene_symbol: string;
  site_id: string | null;
  verdict: "good" | "no";
  reason: string | null;
  load_version: string;
}

export interface L1AltTagRow {
  suggestion_id: string;
  created_at: string;
  reviewer: string;
  member_id: string;
  design_id: string;
  gene_symbol: string;
  insert_after_residue: number | null;
  placement: L1Placement;
  cassette_variant: string | null;
  reason: string | null;
  load_version: string;
}

export interface L1Reviews {
  reviews: L1ReviewRow[];
  alt_tags: L1AltTagRow[];
}

export const REVIEW_HEADER = "X-L1-Review-Token";

export async function fetchL1Reviews(apiBase: string, token: string): Promise<L1Reviews | "unauthorized" | null> {
  try {
    const res = await fetch(`${apiBase}/v1/l1-review`, { headers: { [REVIEW_HEADER]: token }, cache: "no-store" });
    if (res.status === 401) return "unauthorized";
    if (!res.ok) return null;
    const body = (await res.json()) as L1Reviews;
    return { reviews: body.reviews ?? [], alt_tags: body.alt_tags ?? [] };
  } catch {
    return null;
  }
}

export async function submitL1Review(
  apiBase: string,
  token: string,
  body: Record<string, unknown>,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${apiBase}/v1/l1-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [REVIEW_HEADER]: token },
      body: JSON.stringify(body),
    });
    if (res.ok) return { ok: true };
    const err = (await res.json().catch(() => ({}))) as { error?: string };
    return { ok: false, error: err.error ?? `HTTP ${res.status}` };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

/** Each reviewer's latest verdict per design id (the review log is append-only). */
export function latestVerdicts(rows: readonly L1ReviewRow[]): Map<string, L1ReviewRow[]> {
  const latest = new Map<string, L1ReviewRow>();
  for (const r of [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    latest.set(`${r.design_id}\u0000${r.reviewer}\u0000${r.site_id ?? ""}`, r);
  }
  const out = new Map<string, L1ReviewRow[]>();
  for (const r of latest.values()) {
    const list = out.get(r.design_id) ?? [];
    list.push(r);
    out.set(r.design_id, list);
  }
  return out;
}

/** Map a residue picked on a model to the member's own numbering (native models only). */
export function modelToMemberResidue(modelResidue: number, structure: Pick<L1Structure, "kind" | "residue_offset">): number | null {
  if (structure.kind !== "native") return null;
  return modelResidue - (structure.residue_offset ?? 0);
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
