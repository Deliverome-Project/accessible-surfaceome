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
        `the ${layout.cassette[1] - layout.cassette[0] + 1}-aa cassette is charcoal` +
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
