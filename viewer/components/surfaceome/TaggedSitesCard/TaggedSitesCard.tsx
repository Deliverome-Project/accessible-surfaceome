"use client";

import { type ReactNode, useMemo, useState } from "react";
import { ReasoningDrawer } from "../ReasoningDrawer/ReasoningDrawer";
import { SectionCard } from "../SectionCard/SectionCard";
import type {
  EvidenceSource,
  TaggedSite,
  TaggedSitesFile,
} from "../../../lib/tag-sites-types";
import {
  CATEGORY_HEX,
  CATEGORY_LABEL,
  tagSiteCategory,
} from "../../../lib/tag-sites-types";
import styles from "./TaggedSitesCard.module.css";

const KIND_LABEL: Record<TaggedSite["site_kind"], string> = {
  terminal_n: "N-terminus",
  terminal_c: "C-terminus",
  internal: "Internal loop",
};

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

/** Display token for the junction: prefer the canonical residue_label
 *  ("G101"), else derive a readable fallback from site_kind. */
function residueDisplay(s: TaggedSite): string {
  if (s.residue_label) return s.residue_label;
  if (s.site_kind === "terminal_c") return "C-term";
  if (s.site_kind === "terminal_n") return "N-term";
  if (s.insert_after_residue != null) return `after ${s.insert_after_residue}`;
  return "—";
}

/** Numeric position for sorting the Residue column: junction residue, or the
 *  end for a C-terminal tag (sorts last), 0 for a bare N-terminal tag. */
function residueSortVal(s: TaggedSite): number {
  if (s.insert_after_residue != null) return s.insert_after_residue;
  if (s.site_kind === "terminal_c") return Number.MAX_SAFE_INTEGER;
  return 0;
}

/** Parse a residue_range like "H27-K159" / "89-120" -> [27, 159]; null if
 *  absent/malformed. Mirrors parseSpan in tag-sites-overlay so the table's loop
 *  grouping matches the 3D overlay's collapse. */
function parseRange(range: string | null | undefined): [number, number] | null {
  if (!range) return null;
  const m = /^[A-Za-z]?(\d+)\s*-\s*[A-Za-z]?(\d+)$/.exec(range.trim());
  if (!m) return null;
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 1 || b < a) return null;
  return [a, b];
}

/** One representative row per loop: deterministic sites that share a
 *  residue_range (+ det_path) collapse to the residue closest to the span
 *  midpoint — the SAME anchor the 3D overlay's collapseBySpan picks, so the table
 *  and the structure agree. Sites with no range (termini, single-residue) pass
 *  through unchanged. */
function collapseByLoop(sites: TaggedSite[]): TaggedSite[] {
  const groups = new Map<string, TaggedSite[]>();
  const passthrough: TaggedSite[] = [];
  for (const s of sites) {
    const span = parseRange(s.residue_range);
    if (!span) {
      passthrough.push(s);
      continue;
    }
    const key = `${s.det_path}:${span[0]}-${span[1]}`;
    const g = groups.get(key);
    if (g) g.push(s);
    else groups.set(key, [s]);
  }
  const reps: TaggedSite[] = [];
  for (const g of groups.values()) {
    const span = parseRange(g[0].residue_range) as [number, number];
    const mid = (span[0] + span[1]) / 2;
    g.sort(
      (a, b) => Math.abs(residueSortVal(a) - mid) - Math.abs(residueSortVal(b) - mid),
    );
    reps.push(g[0]); // representative anchor closest to the loop midpoint
  }
  return [...passthrough, ...reps];
}

// --- chips ------------------------------------------------------------------

/** Normalize a compartment to a human label. Accepts both the human words
 *  ("extracellular") and raw DeepTMHMM topology chars (O/I/M/S) so a site whose
 *  `compartment` is missing (older data falls back to `topology_state`, a char)
 *  still reads "extracellular", never a bare "O". */
const TOPO_CHAR_LABEL: Record<string, string> = {
  O: "extracellular",
  I: "intracellular",
  M: "membrane",
  S: "signal",
};

function compartmentLabel(value: string | null): string {
  if (!value) return "—";
  return TOPO_CHAR_LABEL[value] ?? value;
}

function CompartmentChip({ value }: { value: string | null }) {
  const v = compartmentLabel(value);
  const tone =
    v === "extracellular"
      ? styles.chipEc
      : v === "intracellular"
        ? styles.chipIc
        : v === "signal"
          ? styles.chipSig
          : v === "membrane"
            ? styles.chipTm
            : "";
  return <span className={`${styles.chip} ${tone}`}>{v}</span>;
}

function ConfidenceChip({ value }: { value: string | null }) {
  if (!value) return <span className={styles.muted}>—</span>;
  const tone =
    value === "high"
      ? styles.chipHigh
      : value === "medium"
        ? styles.chipMed
        : styles.chipLow;
  return <span className={`${styles.chip} ${tone}`}>{value}</span>;
}

/** Tag types as chips — a multi-tag string ("ALFA, DogTag") splits into one
 *  chip per tag. */
function TagChips({ value }: { value: string | null }) {
  const tags = (value ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  if (!tags.length) return <span className={styles.muted}>—</span>;
  return (
    <span className={styles.chipRow}>
      {tags.map((t, i) => (
        <span key={i} className={`${styles.chip} ${styles.chipTag}`}>
          {t}
        </span>
      ))}
    </span>
  );
}

// --- sources + evidence drawer ---------------------------------------------

/** Resolve an evidence source to an external href: explicit url, else a
 *  PubMed link from the PMID, else a doi.org link. Null if unlinkable. */
function sourceHref(src: EvidenceSource): string | null {
  if (src.url) return src.url;
  if (src.pmid) return `https://pubmed.ncbi.nlm.nih.gov/${src.pmid}/`;
  if (src.doi) return `https://doi.org/${src.doi}`;
  return null;
}

function Sources({ sources }: { sources: EvidenceSource[] }) {
  if (!sources.length) return <span className={styles.muted}>—</span>;
  return (
    <span className={styles.sources}>
      {sources.map((src, i) => {
        const href = sourceHref(src);
        const label =
          src.citation ||
          (src.pmid ? `PMID ${src.pmid}` : src.doi ? `DOI ${src.doi}` : "source");
        return href ? (
          <a key={i} href={href} target="_blank" rel="noopener noreferrer">
            {label}
          </a>
        ) : (
          <span key={i}>{label}</span>
        );
      })}
    </span>
  );
}

/** Expandable evidence drawer for one literature site — mirrors the main
 *  sections' ReasoningDrawer. Shows the exact entailment-checked quote(s)
 *  (from sources[].claim), the agent rationale, and the linked sources. */
function SiteEvidenceDrawer({ site }: { site: TaggedSite }) {
  const quotes = site.sources
    .map((src) => src.claim)
    .filter((c): c is string => Boolean(c && c.trim()));
  if (!quotes.length && !site.rationale)
    return <span className={styles.muted}>—</span>;
  return (
    <ReasoningDrawer
      eyebrow={`Tag site · ${residueDisplay(site)}`}
      title="Supporting evidence"
      ariaLabel={`Supporting evidence for ${residueDisplay(site)}`}
      triggerLabel="Quote ↗"
    >
      {quotes.map((q, i) => (
        <blockquote key={i} className={styles.quote}>
          &ldquo;{q}&rdquo;
        </blockquote>
      ))}
      {site.rationale ? (
        <p className={styles.drawerRationale}>{site.rationale}</p>
      ) : null}
      <div className={styles.drawerSources}>
        <Sources sources={site.sources} />
      </div>
    </ReasoningDrawer>
  );
}

// --- generic sortable table -------------------------------------------------

type SortDir = "asc" | "desc";

interface Column {
  key: string;
  label: string;
  /** Sort accessor; omit to make the column non-sortable (plain header). */
  sortVal?: (s: TaggedSite) => string | number;
  render: (s: TaggedSite) => ReactNode;
  cellClass?: string;
}

function SortableTable({
  sites,
  columns,
}: {
  sites: TaggedSite[];
  columns: Column[];
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey && c.sortVal);
    if (!col || !col.sortVal) return sites;
    const sv = col.sortVal;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...sites].sort((a, b) => {
      const av = sv(a);
      const bv = sv(b);
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
  }, [sites, columns, sortKey, sortDir]);

  function onSort(c: Column) {
    if (!c.sortVal) return;
    if (sortKey === c.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(c.key);
      setSortDir("asc");
    }
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={styles.head}
                aria-sort={
                  sortKey === c.key
                    ? sortDir === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
              >
                {c.sortVal ? (
                  <button
                    type="button"
                    className={styles.sortBtn}
                    onClick={() => onSort(c)}
                  >
                    {c.label}
                    <span aria-hidden="true" className={styles.sortArrow}>
                      {sortKey === c.key ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                ) : (
                  c.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.site_id}>
              {columns.map((c) => (
                <td key={c.key} className={c.cellClass}>
                  {c.render(s)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- column definitions -----------------------------------------------------

const LIT_COLUMNS: Column[] = [
  { key: "residue", label: "Residue", sortVal: residueSortVal, render: residueDisplay, cellClass: styles.residue },
  { key: "placement", label: "Placement", sortVal: (s) => KIND_LABEL[s.site_kind], render: (s) => KIND_LABEL[s.site_kind] },
  { key: "compartment", label: "Compartment", sortVal: (s) => compartmentLabel(s.compartment ?? s.topology_state), render: (s) => <CompartmentChip value={s.compartment ?? s.topology_state} /> },
  { key: "tag", label: "Tag", sortVal: (s) => s.tag_type ?? "", render: (s) => <TagChips value={s.tag_type} /> },
  {
    key: "evidence",
    label: "Evidence",
    sortVal: (s) => s.evidence_type ?? "",
    render: (s) => (
      <>
        {s.evidence_type || "—"}
        {s.functional_impact_measured ? (
          <span className={styles.detail}>{s.functional_impact_measured}</span>
        ) : null}
      </>
    ),
    cellClass: styles.evidence,
  },
  { key: "conf", label: "Conf.", sortVal: (s) => CONF_RANK[s.confidence ?? ""] ?? 0, render: (s) => <ConfidenceChip value={s.confidence} /> },
  { key: "sources", label: "Sources", sortVal: (s) => s.sources.length, render: (s) => <Sources sources={s.sources} /> },
  { key: "details", label: "Details", render: (s) => <SiteEvidenceDrawer site={s} /> },
];

const DET_COLUMNS: Column[] = [
  { key: "residue", label: "Residue", sortVal: residueSortVal, render: residueDisplay, cellClass: styles.residue },
  { key: "range", label: "Range", sortVal: (s) => s.residue_range ?? "", render: (s) => <span className={styles.muted}>{s.residue_range ?? "—"}</span> },
  { key: "placement", label: "Placement", sortVal: (s) => KIND_LABEL[s.site_kind], render: (s) => KIND_LABEL[s.site_kind] },
  { key: "compartment", label: "Compartment", sortVal: (s) => compartmentLabel(s.compartment ?? s.topology_state), render: (s) => <CompartmentChip value={s.compartment ?? s.topology_state} /> },
  { key: "path", label: "Path", sortVal: (s) => s.det_path ?? "", render: (s) => (s.det_path ? <span className={`${styles.chip} ${styles.chipPath}`}>{s.det_path}</span> : <span className={styles.muted}>—</span>) },
  { key: "plddt", label: "pLDDT", sortVal: (s) => s.plddt ?? -1, render: (s) => (s.plddt != null ? s.plddt.toFixed(1) : "—") },
  { key: "conf", label: "Conf.", sortVal: (s) => CONF_RANK[s.confidence ?? ""] ?? 0, render: (s) => <ConfidenceChip value={s.confidence} /> },
];

export interface TaggedSitesCardProps {
  taggedSites: TaggedSitesFile | null;
  n?: number;
}

/**
 * §Tag sites — a dedicated section (its own tab, distinct from
 * Internalization) listing engineered epitope/tag insertion points for the
 * protein. Two provenances, matching the structure-viewer overlay legend:
 *   • literature_retrieved — tags published + validated in the literature
 *     (hybrid lit-search + web_search agent), with linked sources;
 *   • deterministic_computed — computed candidate insertion points from the
 *     disorder / surface-loop pipeline (pLDDT + RSA/DSSP, feature-veto).
 * All columns are sortable; tag/compartment/confidence render as chips.
 * `validated_literature` provenance is validation-only and never rendered.
 */
export function TaggedSitesCard({ taggedSites, n }: TaggedSitesCardProps) {
  const sites = taggedSites?.sites ?? [];
  // Surface-accessible literature sites only (N-terminal tags are extracellular
  // by construction — placed after signal-peptide cleavage — even if the residue
  // topology reads "signal").
  const lit = sites.filter(
    (s) =>
      s.provenance === "literature_retrieved" &&
      (s.extracellular || s.site_kind === "terminal_n"),
  );
  // One representative row per loop (mirrors the 3D overlay's collapse) so a long
  // disordered ectodomain shows one row per loop, not a dense run of adjacent rows.
  const det = collapseByLoop(
    sites.filter((s) => s.provenance === "deterministic_computed"),
  );
  const legendCategories = Array.from(
    new Set([...lit, ...det].map((s) => tagSiteCategory(s))),
  );

  if (!taggedSites?.has_data || lit.length + det.length === 0) {
    return (
      <SectionCard n={n} title="Tag sites">
        <p className={styles.empty}>No tag-site suggestions for this protein yet.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      n={n}
      title="Tag sites"
      lede="Engineered epitope/tag insertion points — literature-validated tags and computed candidate positions. Highlighted on the structure viewer above. Click any column header to sort."
    >
      <p className={styles.legend}>
        {legendCategories.map((c) => (
          <span key={c} className={styles.legendItem}>
            <span
              className={styles.dot}
              style={{ background: CATEGORY_HEX[c] }}
              aria-hidden="true"
            />
            {CATEGORY_LABEL[c]}
          </span>
        ))}
      </p>

      {lit.length > 0 ? (
        <>
          <h3 className={styles.subhead}>Literature-validated ({lit.length})</h3>
          <SortableTable sites={lit} columns={LIT_COLUMNS} />
        </>
      ) : null}

      {det.length > 0 ? (
        <>
          <h3 className={styles.subhead}>Computed candidates ({det.length})</h3>
          <SortableTable sites={det} columns={DET_COLUMNS} />
        </>
      ) : null}
    </SectionCard>
  );
}
