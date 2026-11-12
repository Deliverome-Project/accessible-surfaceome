/*
 * L1 library design overlay: per-member suggested tag sites and folded models, served
 * by the Worker at /v1/l1-design/{SYMBOL} from the l1_*_public tables
 * (cloudflare/migrations/l1_design_v1.sql). Client-safe (no node:fs).
 *
 * Residue numbers are in each MEMBER's own native numbering, which is not the gene's
 * canonical numbering when the member is an isoform or an ortholog.
 */
import { STRUCTURES_BASE } from "./structure-viewer-types";

export type L1SiteStatus = "built" | "proposed" | "held";

export interface L1Site {
  site_id: string;
  rung: string;
  /** 0 = before residue 1; null = no site chosen yet. */
  insert_after_residue: number | null;
  residue_before: string | null;
  residue_after: string | null;
  leader: string | null;
  cassette: string | null;
  cassette_aa: number | null;
  rank: number | null;
  status: L1SiteStatus;
  status_detail: string | null;
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
  note: string | null;
}

export interface L1Member {
  member_id: string;
  design_id: string | null;
  gene_symbol: string;
  species: string | null;
  candidate_set: string | null;
  rung: string;
  ordered_length_aa: number | null;
  sites: L1Site[];
  structures: L1Structure[];
}

export interface L1DesignFile {
  gene_symbol: string;
  load: { load_version: string; created_at: string } | null;
  members: L1Member[];
}

const STATUSES: ReadonlySet<string> = new Set(["built", "proposed", "held"]);

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
    }];
  });
  return { ...(o as unknown as L1DesignFile), members };
}

/** URL of a model's coordinates: our own models are in the public structures bucket,
 *  AlphaFold DB models at their AFDB URL. */
export function l1StructureUrl(s: Pick<L1Structure, "r2_key" | "model_url">): string | null {
  if (s.r2_key) return `${STRUCTURES_BASE}/${s.r2_key.replace(/^\/+/, "")}`;
  return s.model_url ?? null;
}

/** "after E34 ↓ S35", "after Met1", "C-terminal, after residue 760". */
export function l1SiteLabel(site: L1Site, orderedLength: number | null): string {
  const r = site.insert_after_residue;
  if (r == null) return "no site chosen";
  if (r === 0) return "before residue 1";
  if (orderedLength != null && r === orderedLength) return `after the last residue (${r})`;
  const before = site.residue_before ? `${site.residue_before}${r}` : `${r}`;
  const after = site.residue_after ? `${site.residue_after}${r + 1}` : `${r + 1}`;
  return `between ${before} and ${after}`;
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
