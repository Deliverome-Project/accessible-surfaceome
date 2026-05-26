"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CatalogRow, TriageCell } from "../../lib/surfaceome";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import { isQueuedDeepDive } from "../../lib/queued-deep-dives";
import {
  CatalogRationaleDrawer,
  type CatalogTriageDetailState,
} from "./CatalogRationaleDrawer";
import styles from "./CatalogTable.module.css";

// Per-row height estimate fed to @tanstack/react-virtual. Rows with
// a triage verdict are taller (two lines — verdict pill above, reason
// underneath) so we keep the estimate slightly above the no-triage
// height. The virtualizer dynamically re-measures as rows enter the
// viewport, so this only needs to be in the right ballpark for the
// initial scroll-height calc and overscan window.
const ROW_ESTIMATE_PX = 56;
const ROW_OVERSCAN = 12;

// CSS Grid template — gene | DB-votes count | 5 DB dots | Triage
// verdict | Reason (flex) | Deep-dive flag. The UniProt-accession
// column was dropped (it duplicated info that's on the deep-dive
// page); the per-row "reason" column is new and takes the remaining
// horizontal space via `minmax(.., 1fr)`. Haiku and Opus calls live
// on /benchmark, not here.
const GRID_TEMPLATE =
  "10rem 3.8rem 5rem 3.5rem 5rem 4.4rem 3.5rem 8rem minmax(8rem, 1fr) 5rem";

// Worker base for the on-demand /v1/triage/{symbol} fetch the row
// expander triggers. Falls back to the production deployment when
// `NEXT_PUBLIC_SURFACEOME_API_BASE` isn't set (local dev or static
// export without a build-time override). The `_PUBLIC_` prefix is
// required for Next.js to inline the value into the client bundle.
const TRIAGE_API_BASE =
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ?? "https://api.deliverome.org/surfaceome";

interface TriageRun {
  created_at: string;
  model: string;
  prompt_variant: string | null;
  prompt_filename: string | null;
  schema_version: string | null;
  replicate: number | null;
  predicted_verdict: string;
  predicted_reason: string | null;
  predicted_confidence: string | null;
  predicted_key_uncertainty: string | null;
  verdict_reasoning: string | null;
  correct: number | null;
  latency_s: number | null;
  n_web_searches: number | null;
  error: string | null;
}

type TriageDetailState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; runs: TriageRun[] };

// Five gating DBs. DeepTMHMM + COMPARTMENTS were demoted from the
// M1 universe gate upstream (kept in the D1 row for fidelity but
// hidden in the public catalog).
const DB_KEYS: { key: keyof CatalogRow["db"]; short: string; long: string }[] = [
  { key: "uniprot", short: "U", long: "UniProt" },
  { key: "go", short: "G", long: "GO" },
  { key: "surfy", short: "S", long: "SURFY" },
  { key: "cspa", short: "C", long: "CSPA" },
  { key: "hpa", short: "H", long: "HPA" },
];

// The catalog's headline call comes from the project's "triage agent"
// — Sonnet 4.6 with an NCBI-context block, run on every protein-coding
// gene. We surface it as "Triage agent" in the UI to keep the catalog
// model-agnostic; the specific model identity is reserved for the
// SurfaceBench benchmark, where cross-model comparison is the point.
// `idx` is the index in the Worker's `triage_by_model` array (still
// fixed at Haiku=0, Sonnet=1, Opus=2 per Worker contract).
const CATALOG_MODELS: { id: string; idx: number; short: string; long: string }[] = [
  { id: "claude-sonnet-4-6", idx: 1, short: "S", long: "Triage agent" },
];

type SortKey =
  | "symbol"
  | "n_sources"
  | "db_uniprot"
  | "db_go"
  | "db_surfy"
  | "db_cspa"
  | "db_hpa"
  | "triage"
  | "deep_dive";
type SortDir = "asc" | "desc";
// The "All" Quick chip was kept after the others were dropped because
// it's the explicit "clear filters" affordance — clicking it restores
// the unfiltered view. Deep-dive moved into the filter panel as a
// proper binary radio so it doesn't AND-conflict with itself.
type QuickFilter = "all";

type DbKey = keyof CatalogRow["db"];
type VerdictKey = "yes" | "contextual" | "no";

const VERDICT_OPTIONS: { key: VerdictKey; label: string }[] = [
  { key: "yes", label: "yes" },
  { key: "contextual", label: "contextual" },
  { key: "no", label: "no" },
];

/** The canonical TriageReason enum from
 *  ``src/accessible_surfaceome/tools/_shared/models.py`` (YesReason,
 *  ContextualReason, NoReason). Grouped by verdict here so the filter
 *  UI can render them under three subheads, but every group's "other"
 *  collapses to the same wire value, so they share a filter state. */
const REASON_GROUPS: { verdict: VerdictKey; label: string; reasons: string[] }[] = [
  {
    verdict: "yes",
    label: "yes",
    reasons: [
      "classical_surface_receptor",
      "gpi_anchored",
      "multipass_with_exposed_loops",
      "extracellular_face_protein",
      "stable_complex_partner",
    ],
  },
  {
    verdict: "contextual",
    label: "contextual",
    reasons: [
      "cell_state_induced",
      "tissue_restricted_surface",
      "lysosomal_exocytosis",
      "dual_localization",
      "stable_surface_attachment",
    ],
  },
  {
    verdict: "no",
    label: "no",
    reasons: [
      "cytoplasmic",
      "nuclear",
      "mitochondrial_internal",
      "endomembrane_resident",
      "nuclear_envelope",
      "inner_leaflet_anchored",
      "secreted_only",
      "pmhc_only_intracellular",
    ],
  },
];
const REASON_OTHER = "other";

function prettyReason(r: string): string {
  return r.replace(/_/g, " ");
}

/** Map a verdict bucket onto a CSS modifier class on the reason-
 *  group label, so "yes" reads as green, "contextual" as amber, "no"
 *  as maroon — matches the verdict-pill palette in the table. */
function reasonGroupLabelToneClass(v: VerdictKey): string {
  if (v === "yes") return styles.filterReasonGroupLabelYes;
  if (v === "contextual") return styles.filterReasonGroupLabelContextual;
  if (v === "no") return styles.filterReasonGroupLabelNo;
  return styles.filterReasonGroupLabelAny;
}

/** Schema fields the advanced-filter panel could surface once the
 *  Worker payload extends — currently the catalog row doesn't carry
 *  `subcategory` or `headline_risks` (those live on the per-gene
 *  deep-dive JSON). Listed here as a TODO for the panel: when the
 *  /v1/catalog response grows the fields, add chip rows for them. */
// TODO(catalog-filters): deep-dive subcategory chips
//   (single_pass_T1, single_pass_T2, multi_pass, GPCR, GPI_anchored,
//   tetraspanin, ion_channel, transporter, other)
// TODO(catalog-filters): headline_risks chips
//   (shed_form, secreted_form, co_receptor, ecd_too_small,
//   epitope_masked, isoform_decoy, restricted_subdomain,
//   low_endogenous_expression, antibody_validation_weak,
//   ligand_unknown, other)

function verdictTone(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}

interface CatalogTableProps {
  rows: CatalogRow[];
  /** When sourcing from the snapshot, the timestamp at which it was
   *  built. The API path omits it; the toolbar drops the timestamp
   *  chip when undefined. */
  generated_at?: string;
  n_rows: number;
  n_with_triage: number;
  n_with_deep_dive: number;
  /** universe_version identifier from /v1/catalog — included in the
   *  TSV download filename so a downloaded snapshot is traceable. */
  universe_version?: string;
}

export function CatalogTable({
  rows,
  generated_at,
  n_rows,
  n_with_triage,
  n_with_deep_dive,
  universe_version,
}: CatalogTableProps) {
  const [query, setQuery] = useState("");
  const [quick, setQuick] = useState<QuickFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("deep_dive");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  // Advanced filters. `dbFilter` is AND-semantics: a row passes only
  // if every DB in the set voted yes (intersection of `DB ∈ filter`
  // and `row.db[DB] === 1`). `verdictFilter` and `reasonFilter` are
  // both OR-semantics — a row passes if its verdict / reason is in
  // the (non-empty) set. Reasons are a closed enum (TriageReason in
  // models.py: 17 fixed values + "other"), so the UI is a chip
  // multi-select grouped by verdict bucket, not a free-text input.
  const [showFilters, setShowFilters] = useState(false);
  const [dbFilter, setDbFilter] = useState<Set<DbKey>>(new Set());
  const [verdictFilter, setVerdictFilter] = useState<Set<VerdictKey>>(
    new Set(),
  );
  const [reasonFilter, setReasonFilter] = useState<Set<string>>(new Set());
  // Deep-dive is a binary attribute on each row, so the filter is a
  // radio (yes / no / null=either) rather than a Set multi-select.
  // The earlier multi-select form let users select both yes AND no
  // (an empty intersection) without realizing it.
  const [deepDiveFilter, setDeepDiveFilter] = useState<"yes" | "no" | null>(
    null,
  );
  // SURFACE-Bind filter — 4-way exclusive: any / scored ≥1 / scored
  // ≥3 / not in dataset. ``null`` = filter off (all rows pass).
  //  - "any" → ``surface_bind_sites != null`` (in dataset, scored)
  //  - "ge1" → ``surface_bind_sites >= 1`` (has scored targetable patches)
  //  - "ge3" → ``surface_bind_sites >= 3`` (multi-site, design flexibility)
  //  - "not_in" → ``surface_bind_sites == null`` (not in SURFACE-Bind)
  // The chip set deliberately distinguishes "scored but 0 patches"
  // (under "any" but NOT under "ge1") from "not in dataset" so the
  // catalog reader can tell them apart at a glance.
  type SurfaceBindFilter = "any" | "ge1" | "ge3" | "not_in" | null;
  const [surfaceBindFilter, setSurfaceBindFilter] =
    useState<SurfaceBindFilter>(null);

  function toggleDbFilter(key: DbKey) {
    setDbFilter((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }
  function toggleVerdictFilter(key: VerdictKey) {
    // Toggle the verdict, then prune `reasonFilter` so only reasons
    // that belong to a still-selected verdict (or are "other", which
    // is verdict-agnostic) survive.
    const nextVerdict = new Set(verdictFilter);
    if (nextVerdict.has(key)) nextVerdict.delete(key);
    else nextVerdict.add(key);
    setVerdictFilter(nextVerdict);
    // Unrestricted verdict filter ⇒ every reason still applies; no
    // prune needed.
    if (nextVerdict.size === 0) return;
    setReasonFilter((prev) => {
      const compatible = new Set<string>();
      for (const r of prev) {
        if (r === REASON_OTHER) {
          compatible.add(r);
          continue;
        }
        const group = REASON_GROUPS.find((g) => g.reasons.includes(r));
        if (group && nextVerdict.has(group.verdict)) {
          compatible.add(r);
        }
      }
      return compatible;
    });
  }
  function toggleReasonFilter(key: string) {
    setReasonFilter((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }
  function toggleDeepDiveFilter(key: "yes" | "no") {
    // Radio: clicking the active chip clears the filter; clicking the
    // other chip switches to it. yes/no are mutually exclusive.
    setDeepDiveFilter((prev) => (prev === key ? null : key));
  }
  function toggleSurfaceBindFilter(key: NonNullable<SurfaceBindFilter>) {
    // 4-way radio — clicking the active chip clears, otherwise switches.
    setSurfaceBindFilter((prev) => (prev === key ? null : key));
  }
  function clearAdvancedFilters() {
    setDbFilter(new Set());
    setVerdictFilter(new Set());
    setReasonFilter(new Set());
    setDeepDiveFilter(null);
    setSurfaceBindFilter(null);
  }
  const activeFilterCount =
    dbFilter.size +
    verdictFilter.size +
    reasonFilter.size +
    (deepDiveFilter !== null ? 1 : 0) +
    (surfaceBindFilter !== null ? 1 : 0);

  // Which reason groups make sense to surface, given the current
  // verdict filter. The triage reason is constrained by the verdict
  // (e.g. `gpi_anchored` only appears on yes-verdict rows), so we
  // hide groups whose verdict isn't in the active filter.
  const visibleReasonGroups = useMemo<{
    groups: typeof REASON_GROUPS;
    showOther: boolean;
    hint: string | null;
  }>(() => {
    if (verdictFilter.size === 0) {
      return { groups: REASON_GROUPS, showOther: true, hint: null };
    }
    const allowed = verdictFilter;
    if (allowed.size === 0) {
      return {
        groups: [],
        showOther: false,
        hint: "No reasons apply — the verdict filter excluded every bucket.",
      };
    }
    return {
      groups: REASON_GROUPS.filter((g) => allowed.has(g.verdict)),
      showOther: true,
      hint: null,
    };
  }, [verdictFilter]);
  // Side-rationale drawer: one selected symbol at a time. Clicking the
  // same symbol again toggles the drawer off. The /v1/triage/{symbol}
  // fetch is lazy — kicked off the first time a symbol is selected,
  // cached for the rest of the session (we don't ship the full per-
  // run reasoning in /v1/catalog: 19k genes × ~1 KB reasoning is too
  // big to inline). The drawer reads the cached detail entry and
  // falls back to the catalog row's headline verdict while the fetch
  // is in flight.
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [triageDetails, setTriageDetails] = useState<
    Record<string, TriageDetailState>
  >({});

  function handleSelectSymbol(symbol: string) {
    setSelectedSymbol((prev) => (prev === symbol ? null : symbol));
    if (triageDetails[symbol]) return;
    setTriageDetails((prev) => ({ ...prev, [symbol]: { status: "loading" } }));
    fetch(`${TRIAGE_API_BASE}/v1/triage/${symbol}`, { cache: "force-cache" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as { runs: TriageRun[] };
        setTriageDetails((prev) => ({
          ...prev,
          [symbol]: { status: "ready", runs: data.runs ?? [] },
        }));
      })
      .catch((err: Error) => {
        setTriageDetails((prev) => ({
          ...prev,
          [symbol]: { status: "error", message: err.message },
        }));
      });
  }

  // ESC closes the drawer. Installed at the table level so the
  // non-modal drawer doesn't need focus to dismiss.
  useEffect(() => {
    if (!selectedSymbol) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedSymbol(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedSymbol]);

  // `mounted` gates the virtualized body so the SSR pass renders an
  // empty body — the header, toolbar, and footnotes still hydrate
  // from server HTML for snappy first paint, and the rows appear on
  // the next client tick. Keeps the static-export HTML tiny.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // The .tableScroll element is the scroll container (overflow-y in
  // CSS), so rows scroll under the sticky header without dragging the
  // whole page around.
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const dbList = Array.from(dbFilter);
    return rows.filter((r) => {
      if (q) {
        // Search across symbol, UniProt, the NCBI descriptive name,
        // and every synonym — so a free-text query like "transferrin"
        // can match a gene whose canonical symbol is TF.
        const syn = r.synonyms ? r.synonyms.join(" ") : "";
        const hay =
          `${r.symbol} ${r.uniprot} ${r.name ?? ""} ${syn}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      // Advanced filters — AND across categories, semantics described
      // alongside the state declarations above.
      if (dbList.length > 0) {
        for (const dbKey of dbList) {
          if (!r.db[dbKey]) return false;
        }
      }
      if (verdictFilter.size > 0) {
        const v = r.triage_by_model[1]?.verdict;
        if (v !== "yes" && v !== "contextual" && v !== "no") return false;
        if (!verdictFilter.has(v)) return false;
      }
      if (reasonFilter.size > 0) {
        const reason = r.triage_by_model[1]?.reason ?? "";
        if (!reasonFilter.has(reason)) return false;
      }
      if (deepDiveFilter !== null) {
        const k = r.deep_dive ? "yes" : "no";
        if (k !== deepDiveFilter) return false;
      }
      if (surfaceBindFilter !== null) {
        const sb = r.surface_bind_sites;
        switch (surfaceBindFilter) {
          case "any":
            // In SURFACE-Bind's dataset at all (scored — even with 0 patches).
            if (sb == null) return false;
            break;
          case "ge1":
            if (sb == null || sb < 1) return false;
            break;
          case "ge3":
            if (sb == null || sb < 3) return false;
            break;
          case "not_in":
            if (sb != null) return false;
            break;
        }
      }
      return true;
    });
  }, [
    rows,
    query,
    quick,
    dbFilter,
    verdictFilter,
    reasonFilter,
    deepDiveFilter,
    surfaceBindFilter,
  ]);

  const sorted = useMemo(() => {
    const copy = filtered.slice();
    const dir = sortDir === "asc" ? 1 : -1;
    const q = query.trim().toLowerCase();
    // When a query is active, override the user-selected sort with a
    // relevance rank so the gene whose SYMBOL is the query lands first.
    // Previously "src" returned dozens of rows where the symbol just
    // *contained* "src" (transcription factors with SRC-prefix names)
    // ahead of the canonical SRC gene because the user-selected sort
    // (deep-dive desc, n_sources desc) didn't know about the query.
    // Rank tiers (lower = better):
    //   0 exact symbol  ("SRC" === q)
    //   1 exact uniprot ("P12931" === q)
    //   2 symbol prefix ("SRCM" startsWith q)
    //   3 symbol contains q anywhere
    //   4 uniprot contains q
    //   5 name contains q
    //   6 synonym contains q
    //   7 fallback (shouldn't fire — filter would have excluded)
    function relevanceRank(r: CatalogRow): number {
      if (!q) return 0;
      const sym = r.symbol.toLowerCase();
      const up = r.uniprot.toLowerCase();
      if (sym === q) return 0;
      if (up === q) return 1;
      if (sym.startsWith(q)) return 2;
      if (sym.includes(q)) return 3;
      if (up.includes(q)) return 4;
      if ((r.name ?? "").toLowerCase().includes(q)) return 5;
      if ((r.synonyms ?? []).some((s) => s.toLowerCase().includes(q))) return 6;
      return 7;
    }
    copy.sort((a, b) => {
      if (q) {
        const ra = relevanceRank(a);
        const rb = relevanceRank(b);
        if (ra !== rb) return ra - rb;
      }
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0;
    });
    return copy;
  }, [filtered, sortKey, sortDir, query]);

  const virtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_ESTIMATE_PX,
    overscan: ROW_OVERSCAN,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();

  function setSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(k);
      setSortDir(k === "symbol" ? "asc" : "desc");
    }
  }

  const gridStyle: React.CSSProperties = {
    // Exposed as a CSS custom property so the row + header rules in
    // the .module.css can share the same template (referenced via
    // `var(--catalog-cols)`).
    ["--catalog-cols" as string]: GRID_TEMPLATE,
  };

  return (
    <div className={styles.wrap} style={gridStyle}>
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <label htmlFor="catalog-search" className="sr-only">
            Filter by symbol, UniProt, gene name, or synonym
          </label>
          <input
            id="catalog-search"
            className={styles.searchInput}
            placeholder="Filter by symbol, UniProt, name, or synonym…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            type="search"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className={styles.chipsActions}>
          <div className={styles.chips} role="tablist" aria-label="Quick filters">
            <button
              type="button"
              className={`${styles.chip} ${quick === "all" ? styles.chipOn : ""}`}
              onClick={() => setQuick("all")}
              aria-pressed={quick === "all"}
            >
              All <span className={styles.chipCount}>{n_rows}</span>
            </button>
            <button
              type="button"
              className={`${styles.chip} ${showFilters ? styles.chipOn : ""}`}
              onClick={() => setShowFilters((s) => !s)}
              aria-pressed={showFilters}
              aria-expanded={showFilters}
              aria-controls="catalog-filter-panel"
            >
              {showFilters ? "Hide filters" : "More filters"}
              {activeFilterCount > 0 ? (
                <span className={styles.chipCount}>{activeFilterCount}</span>
              ) : null}
            </button>
          </div>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={() => {
              // Download what the reader is actually looking at — the
              // current filtered + sorted view, not the full 19k-row
              // catalog. Clear filters to download the whole thing.
              const tsv = buildCatalogTsv(sorted);
              const tag = universe_version ?? "snapshot";
              const filtered = sorted.length !== rows.length;
              const suffix = filtered ? `-filtered-${sorted.length}` : "";
              downloadTextFile(
                `surfaceome-catalog-${tag}${suffix}.tsv`,
                tsv,
              );
            }}
            title={
              sorted.length === rows.length
                ? `Download all ${rows.length.toLocaleString()} catalog rows as TSV`
                : `Download ${sorted.length.toLocaleString()} filtered rows as TSV (of ${rows.length.toLocaleString()} total)`
            }
          >
            TSV ↓{" "}
            <span className={styles.downloadCount}>
              {sorted.length === rows.length
                ? rows.length.toLocaleString()
                : `${sorted.length.toLocaleString()}/${rows.length.toLocaleString()}`}
            </span>
          </button>
        </div>
      </div>

      {showFilters ? (
        <div
          id="catalog-filter-panel"
          className={styles.filterPanel}
          role="region"
          aria-label="Advanced catalog filters"
        >
          <div className={styles.filterRow}>
            <span className={styles.filterLabel}>DBs</span>
            <div className={styles.filterChips}>
              {DB_KEYS.map((d) => {
                const on = dbFilter.has(d.key);
                return (
                  <button
                    key={`db-filter-${d.key}`}
                    type="button"
                    className={`${styles.filterChip} ${on ? styles.filterChipOn : ""}`}
                    onClick={() => toggleDbFilter(d.key)}
                    aria-pressed={on}
                    title={`Require ${d.long} = yes`}
                  >
                    {d.long}
                  </button>
                );
              })}
            </div>
            <span className={styles.filterHint}>
              Requires all checked DBs to vote yes
            </span>
          </div>

          <div className={styles.filterRow}>
            <span className={styles.filterLabel}>Triage</span>
            <div className={styles.filterChips}>
              {VERDICT_OPTIONS.map((v) => {
                const on = verdictFilter.has(v.key);
                // Verdict chips wear the same pill colors as the in-
                // table verdict labels (verdictYes / verdictContextual
                // / verdictNo / verdictUnknown). Combined with the
                // filterVerdictChip styling — uppercase + tracking +
                // pill shape — they read as the same vocabulary as
                // the column verdicts.
                const toneClass =
                  v.key === "yes"
                    ? styles.verdictYes
                    : v.key === "contextual"
                      ? styles.verdictContextual
                      : v.key === "no"
                        ? styles.verdictNo
                        : styles.verdictUnknown;
                return (
                  <button
                    key={`verdict-filter-${v.key}`}
                    type="button"
                    className={`${styles.filterVerdictChip} ${on ? toneClass : ""}`}
                    onClick={() => toggleVerdictFilter(v.key)}
                    aria-pressed={on}
                  >
                    {v.label}
                  </button>
                );
              })}
            </div>
            <span className={styles.filterHint}>
              Any of the checked verdicts
            </span>
          </div>

          <div className={styles.filterReason}>
            <span className={styles.filterLabel}>Triage reason</span>
            <div className={styles.filterReasonGroups}>
              {visibleReasonGroups.hint ? (
                <span className={styles.filterHint}>
                  {visibleReasonGroups.hint}
                </span>
              ) : null}
              {visibleReasonGroups.groups.map((g) => (
                <div
                  className={styles.filterReasonGroup}
                  key={`rg-${g.verdict}`}
                >
                  <span
                    className={`${styles.filterReasonGroupLabel} ${reasonGroupLabelToneClass(g.verdict)}`}
                  >
                    {g.label}
                  </span>
                  <div className={styles.filterChips}>
                    {g.reasons.map((r) => {
                      const on = reasonFilter.has(r);
                      return (
                        <button
                          key={`rf-${r}`}
                          type="button"
                          className={`${styles.filterChip} ${on ? styles.filterChipOn : ""}`}
                          onClick={() => toggleReasonFilter(r)}
                          aria-pressed={on}
                        >
                          {prettyReason(r)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
              {visibleReasonGroups.showOther ? (
                <div className={styles.filterReasonGroup}>
                  <span
                    className={`${styles.filterReasonGroupLabel} ${styles.filterReasonGroupLabelAny}`}
                  >
                    any
                  </span>
                  <div className={styles.filterChips}>
                    {(() => {
                      const on = reasonFilter.has(REASON_OTHER);
                      return (
                        <button
                          type="button"
                          className={`${styles.filterChip} ${on ? styles.filterChipOn : ""}`}
                          onClick={() => toggleReasonFilter(REASON_OTHER)}
                          aria-pressed={on}
                          title="Catch-all bucket the agent uses when nothing else fits"
                        >
                          other
                        </button>
                      );
                    })()}
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div
            className={styles.filterRow}
            role="radiogroup"
            aria-label="Deep dive presence"
          >
            <span className={styles.filterLabel}>Deep dive</span>
            <div className={styles.filterChips}>
              {(["yes", "no"] as const).map((k) => {
                const on = deepDiveFilter === k;
                const toneClass =
                  k === "yes" ? styles.verdictYes : styles.verdictUnknown;
                return (
                  <button
                    key={`dd-filter-${k}`}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    className={`${styles.filterVerdictChip} ${on ? toneClass : ""}`}
                    onClick={() => toggleDeepDiveFilter(k)}
                  >
                    {k}
                  </button>
                );
              })}
            </div>
            <span className={styles.filterHint}>
              {`Has a deep-dive page — currently ${n_with_deep_dive} of ${n_rows.toLocaleString()} genes. Click an active chip to clear.`}
            </span>
          </div>

          {/* SURFACE-Bind filter — Marchand 2026 PNAS scored binder
              patches. Four-way radio, mutually exclusive. ``any`` =
              in dataset (scored, even with 0 patches); ``ge1`` /
              ``ge3`` = scored with at least N patches; ``not_in`` =
              filtered out at SURFACE-Bind's structural QC. Together
              the chips distinguish the three states the SurfaceBindCard
              talks about. */}
          <div
            className={styles.filterRow}
            role="radiogroup"
            aria-label="SURFACE-Bind site count"
          >
            <span className={styles.filterLabel}>SURFACE-Bind</span>
            <div className={styles.filterChips}>
              {(
                [
                  { k: "any", label: "any" },
                  { k: "ge1", label: "≥1 site" },
                  { k: "ge3", label: "≥3 sites" },
                  { k: "not_in", label: "not in" },
                ] as const
              ).map(({ k, label }) => {
                const on = surfaceBindFilter === k;
                return (
                  <button
                    key={`sb-filter-${k}`}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    className={`${styles.filterVerdictChip} ${on ? styles.verdictYes : ""}`}
                    onClick={() => toggleSurfaceBindFilter(k)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <span className={styles.filterHint}>
              {`SURFACE-Bind MaSIF-scored targetable patches (Marchand 2026 PNAS). "any" includes proteins scored with 0 patches; "not in" = filtered at structural QC. Click an active chip to clear.`}
            </span>
          </div>

          {activeFilterCount > 0 ? (
            <div className={styles.filterFoot}>
              <button
                type="button"
                className={styles.filterClearBtn}
                onClick={clearAdvancedFilters}
              >
                Clear filters ({activeFilterCount})
              </button>
            </div>
          ) : null}

          <p className={styles.filterFootnote}>
            Deep-dive subcategory and headline-risk tags will appear here
            once the catalog payload carries them per row.
          </p>
        </div>
      ) : null}

      <div className={styles.resultRow}>
        <p className={styles.resultMeta}>
          {sorted.length === rows.length
            ? `${sorted.length.toLocaleString()} genes`
            : `${sorted.length.toLocaleString()} of ${rows.length.toLocaleString()} genes`}
          {generated_at ? (
            <>
              <span className={styles.dot} aria-hidden="true">
                ·
              </span>
              <span title={generated_at}>generated {generated_at.slice(0, 10)}</span>
            </>
          ) : null}
          <span className={styles.dot} aria-hidden="true">·</span>
          <span>
            TSV is verdicts + reason codes only. Free-text reasoning per
            run is on{" "}
            <Link href="/api/#triage" className={styles.apiHintLink}>
              <code>GET /v1/triage/&#123;SYMBOL&#125;</code>
            </Link>
            .
          </span>
        </p>
      </div>

      <div
        className={styles.tableScroll}
        ref={scrollRef}
        role="table"
        aria-rowcount={sorted.length + 1}
      >
        {/* Header row — sticky, identical grid template as every body row */}
        <div className={`${styles.headerRow} ${styles.row}`} role="row">
          <SortableHeader
            label="Symbol"
            k="symbol"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="left"
          />
          <SortableHeader
            label="DB votes"
            k="n_sources"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Count of DB sources voting surface (0-5)"
          />
          {DB_KEYS.map((d) => (
            <SortableHeader
              key={d.key}
              label={d.long}
              k={`db_${d.key}` as SortKey}
              sortKey={sortKey}
              sortDir={sortDir}
              onClick={setSort}
              align="center"
              title={`${d.long} surface call (sort by yes / no)`}
              extraClass={styles.headerDbCell}
            />
          ))}
          {CATALOG_MODELS.map((m) => (
            <SortableHeader
              key={`mhdr-${m.id}`}
              label={m.long}
              k="triage"
              sortKey={sortKey}
              sortDir={sortDir}
              onClick={setSort}
              align="center"
              title={`Sort by ${m.long} verdict`}
            />
          ))}
          <div className={styles.headerCell} role="columnheader">
            Reason
          </div>
          <SortableHeader
            label="Deep dive"
            k="deep_dive"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
          />
        </div>

        {/* Body — a single positioned container whose height is the
            virtualizer's totalSize. Each visible row is absolutely
            positioned inside it; the browser reserves the full scroll
            height without us shipping 19k DOM rows. */}
        <div
          className={styles.body}
          style={
            mounted && sorted.length > 0
              ? { height: totalSize, position: "relative" }
              : undefined
          }
          role="rowgroup"
        >
          {!mounted ? (
            <div className={styles.loadingRow} role="row" aria-hidden="true">
              Loading {sorted.length.toLocaleString()} rows…
            </div>
          ) : null}
          {mounted && sorted.length > 0
            ? virtualItems.map((item) => {
                const r = sorted[item.index];
                const isSelected = selectedSymbol === r.symbol;
                return (
                  <CatalogRowView
                    key={`${r.symbol}-${r.uniprot}`}
                    row={r}
                    measureRef={virtualizer.measureElement}
                    dataIndex={item.index}
                    virtualStart={item.start}
                    isSelected={isSelected}
                    onSelect={handleSelectSymbol}
                  />
                );
              })
            : null}
          {mounted && sorted.length === 0 ? (
            <div className={styles.empty} role="row">
              No rows match these filters.
            </div>
          ) : null}
        </div>
      </div>

      <CatalogRationaleDrawer
        selectedSymbol={selectedSymbol}
        detail={
          selectedSymbol
            ? (triageDetails[selectedSymbol] as
                | CatalogTriageDetailState
                | undefined)
            : undefined
        }
        fallback={
          selectedSymbol
            ? fallbackFromRows(sorted, selectedSymbol)
            : null
        }
        geneName={
          selectedSymbol ? geneNameFromRows(sorted, selectedSymbol) : null
        }
        hasDeepDive={
          selectedSymbol
            ? Boolean(
                sorted.find((r) => r.symbol === selectedSymbol)?.deep_dive,
              )
            : false
        }
        onClose={() => setSelectedSymbol(null)}
      />
    </div>
  );
}

/** Headline NCBI Sonnet verdict from the catalog row — used as a
 *  synchronous fallback while the drawer's lazy fetch is in flight. */
function fallbackFromRows(
  rows: CatalogRow[],
  symbol: string,
): { verdict: string | null; reason: string | null } | null {
  const row = rows.find((r) => r.symbol === symbol);
  if (!row) return null;
  // idx 1 = Sonnet 4.6 in the Worker's triage_by_model array; see
  // CATALOG_MODELS above for the contract.
  const cell = row.triage_by_model[1];
  return {
    verdict: cell?.verdict ?? null,
    reason: cell?.reason ?? null,
  };
}

function geneNameFromRows(rows: CatalogRow[], symbol: string): string | null {
  const row = rows.find((r) => r.symbol === symbol);
  return row?.name ?? null;
}

/**
 * Build a TSV of the catalog rows — one row per gene, matching the
 * columns shown in the table plus the gene name / synonyms from the
 * NCBI lookup (which the UI uses for search but doesn't render). Bulk
 * download is the full unfiltered dataset; if the reader needs a
 * subset, they can filter in pandas / R after downloading.
 */
function buildCatalogTsv(rows: CatalogRow[]): string {
  const headers = [
    "gene_symbol",
    "uniprot_acc",
    "gene_name",
    "synonyms",
    "n_sources",
    "db_uniprot",
    "db_go",
    "db_surfy",
    "db_cspa",
    "db_hpa",
    "haiku_ncbi_verdict",  "haiku_ncbi_reason",
    "sonnet_ncbi_verdict", "sonnet_ncbi_reason",
    "opus_ncbi_verdict",   "opus_ncbi_reason",
    "has_deep_dive",
  ];
  const body: TsvCell[][] = rows.map((r) => [
    r.symbol,
    r.uniprot,
    r.name ?? "",
    r.synonyms ? r.synonyms.join("|") : "",
    r.n_sources,
    r.db.uniprot,
    r.db.go,
    r.db.surfy,
    r.db.cspa,
    r.db.hpa,
    r.triage_by_model[0]?.verdict ?? "", r.triage_by_model[0]?.reason ?? "",
    r.triage_by_model[1]?.verdict ?? "", r.triage_by_model[1]?.reason ?? "",
    r.triage_by_model[2]?.verdict ?? "", r.triage_by_model[2]?.reason ?? "",
    r.deep_dive ? 1 : 0,
  ]);
  return buildTsv(headers, body);
}

function sortValue(r: CatalogRow, k: SortKey): string | number {
  if (k === "symbol") return r.symbol;
  if (k === "n_sources") return r.n_sources;
  if (k === "db_uniprot") return r.db.uniprot ? 1 : 0;
  if (k === "db_go") return r.db.go ? 1 : 0;
  if (k === "db_surfy") return r.db.surfy ? 1 : 0;
  if (k === "db_cspa") return r.db.cspa ? 1 : 0;
  if (k === "db_hpa") return r.db.hpa ? 1 : 0;
  if (k === "triage") {
    // Sort by the triage-agent verdict (Worker slot 1) — the only
    // model with full-genome coverage. yes > contextual > no > none.
    const v = r.triage_by_model[1]?.verdict;
    if (v === "yes") return 3;
    if (v === "contextual") return 2;
    if (v === "no") return 1;
    return 0;
  }
  if (k === "deep_dive") return r.deep_dive ? 1 : 0;
  return 0;
}

function SortableHeader({
  label,
  k,
  sortKey,
  sortDir,
  onClick,
  align,
  mono,
  title,
  extraClass,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onClick: (k: SortKey) => void;
  align: "left" | "center";
  mono?: boolean;
  title?: string;
  /** Extra class concatenated onto the header div — used to slot
   *  the DB-cell tight padding ({.headerDbCell}) on the DB columns. */
  extraClass?: string;
}) {
  const active = sortKey === k;
  return (
    <div
      role="columnheader"
      className={`${styles.headerCell} ${align === "center" ? styles.headerCenter : ""} ${mono ? styles.headerMono : ""} ${extraClass ?? ""}`}
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        className={`${styles.thBtn} ${active ? styles.thBtnActive : ""}`}
        onClick={() => onClick(k)}
        title={title}
      >
        {label}
        <span className={styles.sortIndicator} aria-hidden="true">
          {active ? (sortDir === "asc" ? "▲" : "▼") : ""}
        </span>
      </button>
    </div>
  );
}

function CatalogRowView({
  row,
  measureRef,
  dataIndex,
  virtualStart,
  isSelected,
  onSelect,
}: {
  row: CatalogRow;
  measureRef?: (el: HTMLDivElement | null) => void;
  dataIndex?: number;
  virtualStart?: number;
  isSelected: boolean;
  onSelect: (symbol: string) => void;
}) {
  // Genes with a deep-dive go straight to the rich deep-dive page on
  // click — the side-rationale drawer is redundant for those (the
  // deep-dive page carries the triage reasoning plus everything else).
  // Genes WITHOUT a deep-dive open the drawer instead, since that's
  // the only place to read the triage call's full text.
  const symbolStack = (
    <span className={styles.symbolStack}>
      <span className={styles.symbolText}>{row.symbol}</span>
      {row.name ? (
        <span className={styles.symbolName} title={row.name}>
          {row.name}
        </span>
      ) : null}
    </span>
  );
  const symbolButton = row.deep_dive ? (
    <Link
      href={`/${row.symbol}/`}
      className={styles.symbolButton}
      aria-label={`Open the deep-dive page for ${row.symbol}`}
    >
      {symbolStack}
    </Link>
  ) : (
    <button
      type="button"
      className={styles.symbolButton}
      onClick={() => onSelect(row.symbol)}
      aria-pressed={isSelected}
      aria-label={`Open triage reasoning for ${row.symbol}`}
    >
      {symbolStack}
    </button>
  );
  const style: React.CSSProperties | undefined =
    virtualStart != null
      ? {
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          transform: `translateY(${virtualStart}px)`,
        }
      : undefined;
  // Queued for deep dive but not yet run — show an orange marker so
  // the reader can spot pending work in the catalog. The check defers
  // to viewer/lib/queued-deep-dives.ts; the helper only fires when
  // the gene has no existing surface_annotation row, so an actual run
  // automatically demotes the queue marker.
  const queued = isQueuedDeepDive(row.symbol, Boolean(row.deep_dive));
  return (
    <div
      ref={measureRef}
      data-index={dataIndex}
      role="row"
      className={`${styles.row} ${isSelected ? styles.rowSelected : ""} ${
        queued ? styles.rowQueuedDeepDive : ""
      }`}
      data-deep-dive={row.deep_dive || undefined}
      data-queued-deep-dive={queued || undefined}
      style={style}
    >
      <div className={`${styles.cell} ${styles.symbolCell}`} role="cell">
        {symbolButton}
        {queued ? (
          <span
            className={styles.queuedDeepDivePill}
            title="Queued for deep-dive run — agent hasn't been executed yet. See viewer/lib/queued-deep-dives.ts."
          >
            queued
          </span>
        ) : null}
      </div>
      <div className={`${styles.cell} ${styles.nCell}`} role="cell">
        <span className={styles.nBubble} data-n={row.n_sources}>
          {row.n_sources}
        </span>
      </div>
      {DB_KEYS.map((d) => {
        const yes = Boolean(row.db[d.key]);
        return (
          <div
            key={d.key}
            className={`${styles.cell} ${styles.dbCell} ${yes ? styles.dbCellYes : ""}`}
            role="cell"
            aria-label={`${d.long}: ${yes ? "yes" : "no"}`}
          >
            <span className={styles.dbDot} aria-hidden="true" />
          </div>
        );
      })}
      {CATALOG_MODELS.map((m) => {
        const cell = row.triage_by_model[m.idx];
        return (
          <div
            key={`triage-${m.id}`}
            className={`${styles.cell} ${styles.triageCell} ${styles.modelCell}`}
            role="cell"
          >
            {cell ? (
              <button
                type="button"
                className={`${styles.verdictBtn} ${styles.verdictLabel} ${styles.verdictMini} ${verdictTone(cell.verdict)}`}
                onClick={() => onSelect(row.symbol)}
                aria-pressed={isSelected}
                title={
                  cell.reason
                    ? `${m.long}: ${cell.verdict} (${cell.reason.replace(/_/g, " ")}) — click for reasoning`
                    : `${m.long}: ${cell.verdict} — click for reasoning`
                }
              >
                {cell.verdict}
              </button>
            ) : (
              <span className={styles.dim} title={`${m.long}: no run on file`}>—</span>
            )}
          </div>
        );
      })}
      <div className={`${styles.cell} ${styles.reasonCell}`} role="cell">
        {(() => {
          const reason = row.triage_by_model[1]?.reason;
          if (!reason) return <span className={styles.dim}>—</span>;
          const pretty = reason.replace(/_/g, " ");
          return (
            <span className={styles.reasonText} title={pretty}>
              {pretty}
            </span>
          );
        })()}
      </div>
      <div className={`${styles.cell} ${styles.deepCell}`} role="cell">
        {row.deep_dive ? (
          <Link
            href={`/${row.symbol}/`}
            className={`${styles.verdictLabel} ${styles.verdictMini} ${styles.verdictYes} ${styles.deepLink}`}
            aria-label={`Open the deep-dive record for ${row.symbol}`}
            title={`Open the deep-dive record for ${row.symbol}`}
          >
            yes
          </Link>
        ) : (
          <span className={styles.dim}>—</span>
        )}
      </div>
    </div>
  );
}
