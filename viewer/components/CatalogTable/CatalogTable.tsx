"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type {
  CatalogRow,
  DeepDiveFilters,
  TriageCell,
} from "../../lib/surfaceome";
import { prettyEnum } from "../../lib/enums";
import {
  DD_BOOL_FIELDS,
  DD_ENUM_FIELDS,
  type DdBoolKey,
  type DdBoolSpec,
  type DdEnumKey,
  type DdEnumSpec,
} from "../../lib/deep-dive-fields";
import { buildTsv, downloadTextFile, type TsvCell } from "../../lib/tsv";
import { isQueuedDeepDive } from "../../lib/queued-deep-dives";
import {
  PRESETS,
  INDUCTION_SUBS,
  type PresetKey,
  type InductionSubKey,
} from "../../lib/catalog-presets";
import { InfoTip } from "../InfoTip/InfoTip";
import { tooltips } from "../../lib/tooltips";
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
// verdict | Reason (flex) | Deep dive | Conf | Evidence | State dep.
// "Deep dive" is the deep-dive agent's headline surface-accessibility
// call, mirroring the "Triage" verdict column; Conf / Evidence /
// State dep. are its supporting vitals. The "reason" column takes the
// remaining horizontal space via `minmax(.., 1fr)`. Haiku and Opus calls
// live on /benchmark, not here.
// 13 columns: Symbol | DB votes | U G S C H | Triage verdict | Reason |
// Deep dive | Conf | Evidence | State dep. The 4 deep-dive columns reuse
// the gene-page traffic-light tones, are sortable, and each links to the
// gene's deep-dive page.
const GRID_TEMPLATE =
  "10rem 3.8rem 5rem 3.5rem 5rem 4.4rem 3.5rem 8rem minmax(8rem, 1fr) 6rem 6.5rem 5.6rem 6rem";

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
  | "dd_access"
  | "dd_conf"
  | "dd_evidence"
  | "dd_state";
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

// Deep-dive filter taxonomy (DD_ENUM_FIELDS / DD_BOOL_FIELDS + the
// DdEnumKey / DdBoolKey types) moved to lib/deep-dive-fields.ts so the
// catalog filter panel and the /compare tool share one source of truth.
type DdBoolFilter = "any" | "yes" | "no";

function verdictTone(v: string | null | undefined): string {
  if (v === "yes") return styles.verdictYes;
  if (v === "no") return styles.verdictNo;
  if (v === "contextual") return styles.verdictContextual;
  return styles.verdictUnknown;
}

// Deep-dive-vital tones — mirror the gene-page GeneHeader logic so the
// catalog's 4 deep-dive columns read with the SAME traffic-light scale:
// success(green) → amber(yellow) → danger(red) → neutral(gray). Returns a
// `.ddTone*` CSS modifier class.
type VitalTone = "success" | "amber" | "danger" | "neutral";
const DD_TONE_CLASS: Record<VitalTone, string> = {
  success: styles.ddToneSuccess,
  amber: styles.ddToneAmber,
  danger: styles.ddToneDanger,
  neutral: styles.ddToneNeutral,
};
function accessibilityTone(v: string | null | undefined): VitalTone {
  if (v === "high") return "success";
  if (v === "moderate") return "amber";
  if (v === "low" || v === "no") return "danger";
  return "neutral";
}
function confidenceTone(v: string | null | undefined): VitalTone {
  if (v === "high") return "success";
  if (v === "moderate") return "amber";
  if (v === "low") return "danger";
  return "neutral";
}
function gradeTone(v: string | null | undefined): VitalTone {
  if (v === "direct_multi_method" || v === "direct_single_method") return "success";
  if (v === "supportive_but_indirect" || v === "conflicting") return "amber";
  return "neutral";
}
function stateDependenceTone(v: string | null | undefined): VitalTone {
  // Same value→color mapping as the gene page (low=red, moderate=amber,
  // high=green) so the whole grid reads as one heatmap.
  if (v === "low") return "danger";
  if (v === "moderate") return "amber";
  if (v === "high") return "success";
  return "neutral";
}
/** Compact label for a deep-dive enum value in a narrow cell. */
function ddShort(v: string | null | undefined): string {
  if (!v) return "—";
  // evidence_grade values are long — abbreviate to a glanceable token.
  const map: Record<string, string> = {
    direct_multi_method: "multi",
    direct_single_method: "single",
    supportive_but_indirect: "indirect",
    conflicting: "mixed",
    weak: "weak",
  };
  return map[v] ?? v.replace(/_/g, " ");
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
  const [sortKey, setSortKey] = useState<SortKey>("dd_access");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  // Advanced filters. `dbFilter` is AND-semantics: a row passes only
  // if every DB in the set voted yes (intersection of `DB ∈ filter`
  // and `row.db[DB] === 1`). `verdictFilter` and `reasonFilter` are
  // both OR-semantics — a row passes if its verdict / reason is in
  // the (non-empty) set. Reasons are a closed enum (TriageReason in
  // models.py: 17 fixed values + "other"), so the UI is a chip
  // multi-select grouped by verdict bucket, not a free-text input.
  const [showFilters, setShowFilters] = useState(false);
  // The filter panel is split into two collapsible groups — Triage
  // (existing chips: DB votes, triage verdict, triage reason, deep-
  // dive present) and Deep Dive (NEW: 13 enum + 8 bool filters from
  // the deep-dive synthesizer's filters block). Both start collapsed
  // so opening the panel doesn't dump 30 chip rows on the reader at
  // once — they expand the section they want to filter on.
  // Filter panel is organized into three collapsible groups:
  //   * Databases — the 5-DB vote pattern (independent of agents)
  //   * Triage    — first-pass Sonnet 4.6 agent (verdict + reason +
  //                 deep-dive-presence bool)
  //   * Deep Dive — the 21 deep-dive Filters fields + SURFACE-Bind
  //                 patch count, split into three independently-
  //                 collapsible subsections inside: "Surface call"
  //                 (synthesizer's classifications), "Risks"
  //                 (accessibility-risk fields) and "Deterministic"
  //                 (DeepTMHMM topology, ECD / evidence buckets,
  //                 SURFACE-Bind MaSIF scoring).
  //                 Only applies to rows where the deep-dive has
  //                 run, except for the SURFACE-Bind patch radio
  //                 which is independent of deep-dive coverage.
  // All three start collapsed so the panel reads as a compact menu;
  // each group's header shows an active-filter count when collapsed.
  const [databasesGroupOpen, setDatabasesGroupOpen] = useState(false);
  const [triageGroupOpen, setTriageGroupOpen] = useState(false);
  const [deepDiveGroupOpen, setDeepDiveGroupOpen] = useState(false);
  // The Deep Dive group body is split into three independently
  // collapsible subsections: "Surface call" (LLM rollups minus risks),
  // "Risks" (the accessibility-risk fields, tagged isRisk in
  // lib/deep-dive-fields.ts), and "Deterministic" (tool readouts +
  // SURFACE-Bind). Default open so expanding the parent group reveals
  // the structure; the reader can then collapse the subsections they
  // don't care about.
  const [ddLlmOpen, setDdLlmOpen] = useState(true);
  const [ddRisksOpen, setDdRisksOpen] = useState(true);
  const [ddDetOpen, setDdDetOpen] = useState(true);
  // Saved-preset selector. "all" = filter off; any other key narrows to
  // deep-dive rows whose `deep_dive_filters` payload passes the
  // preset's predicate (see lib/catalog-presets.ts). Non-deep-dive
  // rows are auto-excluded when a non-"all" preset is active because
  // they have no `deep_dive_filters` to evaluate.
  const [presetKey, setPresetKey] = useState<PresetKey>("all");
  // When Induced is active, optional sub-axis filter on
  // `induction_trigger`. Single-select (not multi) — these are
  // mutually-exclusive label buckets, not orthogonal facets.
  const [inductionSub, setInductionSub] = useState<InductionSubKey | null>(
    null,
  );
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
  // Deep-dive filters — 13 enum-valued + 8 boolean. Enum filters use
  // OR-semantics within a field (any of the checked values passes)
  // and AND across fields. Bool filters are tri-state — "any"
  // (filter off, default), "yes" (require true), "no" (require false).
  // The whole Deep-Dive section is also implicitly a deep_dive=true
  // filter: when any deep-dive filter is set, rows without a
  // deep_dive_filters payload drop out. See the predicate below.
  const [ddEnumFilters, setDdEnumFilters] = useState<
    Record<DdEnumKey, Set<string>>
  >(() => {
    const out = {} as Record<DdEnumKey, Set<string>>;
    for (const f of DD_ENUM_FIELDS) out[f.key] = new Set();
    return out;
  });
  const [ddBoolFilters, setDdBoolFilters] = useState<
    Record<DdBoolKey, DdBoolFilter>
  >(() => {
    const out = {} as Record<DdBoolKey, DdBoolFilter>;
    for (const f of DD_BOOL_FIELDS) out[f.key] = "any";
    return out;
  });

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
  function toggleDdEnumFilter(field: DdEnumKey, value: string) {
    setDdEnumFilters((prev) => {
      const nextSet = new Set(prev[field]);
      if (nextSet.has(value)) nextSet.delete(value);
      else nextSet.add(value);
      return { ...prev, [field]: nextSet };
    });
  }
  function cycleDdBoolFilter(field: DdBoolKey, value: DdBoolFilter) {
    // Tri-state radio: clicking the active chip clears back to "any";
    // clicking any other chip switches to it.
    setDdBoolFilters((prev) => ({
      ...prev,
      [field]: prev[field] === value ? "any" : value,
    }));
  }
  function clearAdvancedFilters() {
    setDbFilter(new Set());
    setVerdictFilter(new Set());
    setReasonFilter(new Set());
    setDeepDiveFilter(null);
    setSurfaceBindFilter(null);
    setDdEnumFilters(() => {
      const out = {} as Record<DdEnumKey, Set<string>>;
      for (const f of DD_ENUM_FIELDS) out[f.key] = new Set();
      return out;
    });
    setDdBoolFilters(() => {
      const out = {} as Record<DdBoolKey, DdBoolFilter>;
      for (const f of DD_BOOL_FIELDS) out[f.key] = "any";
      return out;
    });
  }

  // Render helpers for the deep-dive filter rows — extracted so the
  // three subsections (Surface call / Risks / Deterministic) share one
  // implementation instead of triplicating the ~40-line enum and bool
  // row JSX. Closures over the filter state + toggle handlers declared
  // above; called via `.map(renderDdEnumRow)` / `.map(renderDdBoolRow)`.
  function renderDdEnumRow(field: DdEnumSpec) {
    const sel = ddEnumFilters[field.key];
    return (
      <div key={`dd-enum-${field.key}`} className={styles.filterRowDd}>
        <span className={styles.filterLabelWithTip}>
          {field.label}
          <InfoTip label={`About ${field.label}`} wide>
            {tooltips[field.tooltipKey] ?? field.label}
          </InfoTip>
        </span>
        <div className={styles.filterChips}>
          {field.values.map((v) => {
            const on = sel.has(v);
            // Prefer the field's explicit display label (caps acronyms
            // like GPI / GPCR / pMHC that prettyEnum would mangle).
            const label = field.valueLabels?.[v] ?? prettyEnum(v);
            return (
              <button
                key={`dd-${field.key}-${v}`}
                type="button"
                className={`${styles.filterChip} ${on ? styles.filterChipOn : ""}`}
                onClick={() => toggleDdEnumFilter(field.key, v)}
                aria-pressed={on}
                title={`Require ${field.label} = ${label}`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  function renderDdBoolRow(field: DdBoolSpec) {
    const mode = ddBoolFilters[field.key];
    // Single "yes" toggle — boolean is one-or-the-other; ON requires
    // true, OFF (default) = no filter. Dropped the "no" chip per user
    // feedback.
    const triStates: { k: DdBoolFilter; label: string }[] = [
      { k: "yes", label: "yes" },
    ];
    return (
      <div
        key={`dd-bool-${field.key}`}
        className={styles.filterRowDd}
        role="radiogroup"
        aria-label={field.label}
      >
        <span className={styles.filterLabelWithTip}>
          {field.label}
          <InfoTip label={`About ${field.label}`} wide>
            {tooltips[field.tooltipKey] ?? field.label}
          </InfoTip>
        </span>
        <div className={styles.filterChips}>
          {triStates.map(({ k, label }) => {
            const on = mode === k;
            const toneClass =
              on && k === "yes"
                ? styles.verdictYes
                : on && k === "no"
                  ? styles.verdictNo
                  : "";
            return (
              <button
                key={`dd-${field.key}-${k}`}
                type="button"
                role="radio"
                aria-checked={on}
                className={`${styles.filterVerdictChip} ${toneClass}`}
                onClick={() => cycleDdBoolFilter(field.key, k)}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // Count Deep-Dive filter slots that are non-default. Each enum field
  // with ≥1 chip selected counts as one filter; each bool field set
  // to "yes" or "no" counts as one. (Bool tri-state in "any" mode
  // counts as off.) The SURFACE-Bind patch-count radio also lives
  // inside the Deep Dive group (Deterministic subhead), so it counts
  // toward the group's active-filter chip.
  const ddEnumActiveCount = DD_ENUM_FIELDS.reduce(
    (n, f) => n + (ddEnumFilters[f.key].size > 0 ? 1 : 0),
    0,
  );
  const ddBoolActiveCount = DD_BOOL_FIELDS.reduce(
    (n, f) => n + (ddBoolFilters[f.key] !== "any" ? 1 : 0),
    0,
  );
  const ddActiveCount =
    ddEnumActiveCount +
    ddBoolActiveCount +
    (surfaceBindFilter !== null ? 1 : 0);

  const activeFilterCount =
    dbFilter.size +
    verdictFilter.size +
    reasonFilter.size +
    (deepDiveFilter !== null ? 1 : 0) +
    ddActiveCount;
  // `ddActive` gates the deep-dive predicate (requires deep_dive=true
  // and applies enum/bool filters). It does NOT include the SURFACE-
  // Bind radio — that filter runs independently regardless of deep-
  // dive coverage, so it doesn't force the deep-dive presence gate.
  const ddActive = ddEnumActiveCount + ddBoolActiveCount > 0;

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

  // Click-outside-to-close. The drawer is non-modal (no backdrop
  // overlay — keeps the catalog table scannable beside it), so a
  // global mousedown listener handles outside clicks. The dependency
  // chain (selectedSymbol → drawerRef.current) skips installation
  // when the drawer is closed.
  const drawerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!selectedSymbol) return;
    const onDocMouseDown = (e: MouseEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (drawerRef.current && drawerRef.current.contains(target)) return;
      // Clicking another catalog row should reselect (handled by the
      // row's own click handler) rather than just close. The row's
      // handler runs first because we attach mousedown at the document
      // level; React's click runs after. To avoid closing-then-
      // reopening, ignore clicks on elements inside the catalog table
      // body — the row handler will toggle selection itself.
      const tableEl = document.querySelector(`.${styles.tableScroll}`);
      if (tableEl && tableEl.contains(target)) return;
      setSelectedSymbol(null);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
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
      // Preset filter — runs the chosen preset's predicate against
      // the row's `deep_dive_filters`. Rows without a deep-dive
      // payload auto-drop because no preset evaluates true on null.
      // Same contract as the deep-dive filter group below — the
      // payload is only emitted by the Worker for deep-dive rows.
      if (presetKey !== "all") {
        const ddf = r.deep_dive_filters;
        if (!ddf) return false;
        const preset = PRESETS.find((p) => p.key === presetKey);
        if (preset && !preset.predicate(ddf)) return false;
        // Induction sub-axis only applies when "induced" preset is
        // active (the sub buckets read `induction_trigger`).
        if (presetKey === "induced" && inductionSub) {
          const sub = INDUCTION_SUBS.find((s) => s.key === inductionSub);
          if (sub && !sub.predicate(ddf)) return false;
        }
      }
      // Deep-dive filter group. Any active filter here implies
      // deep_dive=true — rows without a deep_dive_filters payload
      // drop out entirely, because we can't evaluate the predicate.
      // This matches the Worker contract: the field is only emitted
      // when the gene has a deep-dive AND the annotation_json parsed.
      if (ddActive) {
        const ddf = r.deep_dive_filters;
        if (!ddf) return false;
        for (const f of DD_ENUM_FIELDS) {
          const sel = ddEnumFilters[f.key];
          if (sel.size === 0) continue;
          const v = ddf[f.key] as string | undefined;
          if (v == null || !sel.has(v)) return false;
        }
        for (const f of DD_BOOL_FIELDS) {
          const mode = ddBoolFilters[f.key];
          if (mode === "any") continue;
          const v = ddf[f.key] as boolean | undefined;
          if (typeof v !== "boolean") return false;
          if (mode === "yes" && !v) return false;
          if (mode === "no" && v) return false;
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
    ddActive,
    ddEnumFilters,
    ddBoolFilters,
    presetKey,
    inductionSub,
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
    //   0 exact symbol      ("SRC" === q)
    //   1 exact uniprot     ("P12931" === q)
    //   2 exact alias       ("LAT1" === any alias of SLC7A5 → SLC7A5 wins
    //                        over noisier substring matches in other rows)
    //   3 symbol prefix     ("SRCM" startsWith q)
    //   4 alias prefix      (search "cd8" surfaces CD8A/CD8B over genes
    //                        that just contain "cd8" mid-name)
    //   5 symbol contains q anywhere
    //   6 uniprot contains q
    //   7 name contains q
    //   8 alias contains q anywhere
    //   9 fallback (shouldn't fire — filter would have excluded)
    function relevanceRank(r: CatalogRow): number {
      if (!q) return 0;
      const sym = r.symbol.toLowerCase();
      const up = r.uniprot.toLowerCase();
      const aliases = (r.synonyms ?? []).map((s) => s.toLowerCase());
      if (sym === q) return 0;
      if (up === q) return 1;
      if (aliases.some((a) => a === q)) return 2;
      if (sym.startsWith(q)) return 3;
      if (aliases.some((a) => a.startsWith(q))) return 4;
      if (sym.includes(q)) return 5;
      if (up.includes(q)) return 6;
      if ((r.name ?? "").toLowerCase().includes(q)) return 7;
      if (aliases.some((a) => a.includes(q))) return 8;
      return 9;
    }
    copy.sort((a, b) => {
      if (q) {
        const ra = relevanceRank(a);
        const rb = relevanceRank(b);
        if (ra !== rb) return ra - rb;
        // Within-tier tiebreak: prefer rows with stronger surface signal
        // (more DB votes among UniProt-KW / GO-CC / SURFY / CSPA / HPA).
        // Catalog readers are looking for surface proteins by default, so
        // when two rows tie on relevance (e.g. "lat1" exact-matches both
        // LAT and SLC7A5 as aliases), the higher-vote row wins.
        if (a.n_sources !== b.n_sources) return b.n_sources - a.n_sources;
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
    // Without a stable key the virtualizer caches measured heights by
    // INDEX. When the search query narrows or the sort flips, indices
    // shift and a previously-measured tall row (e.g. multi-line gene
    // name) at index N is reused for whatever row now lives at N,
    // leaving the next row's translateY mis-positioned and bleeding
    // into it visually. Keying by gene symbol ties each measurement
    // to the actual row identity, so re-sorts / filters re-use the
    // right cached height. Symptom that surfaced this: searching
    // "KLK2" caused the KLK2 row to partially overlap the one below.
    getItemKey: (index) => sorted[index]?.symbol ?? index,
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
      {/* Saved-preset selector row. Sits above the search +
       *  quick-filters because the preset is the coarsest filter on
       *  the page — picking one narrows the table to a curated
       *  shortlist (Canonical / Likely / Cell-state induced / Cell-
       *  type restricted) before any of the existing facet chips
       *  apply. Counts are computed over the FULL row set (pre-
       *  filter) so the badges read as "preset population", not
       *  "preset ∩ current other filters" — the reader can see how
       *  many rows the preset would yield before they narrow with
       *  search / DB chips.
       *
       *  Non-"all" presets evaluate against `r.deep_dive_filters`,
       *  so the 19k non-deep-dive rows always exclude themselves.
       *  This makes Canonical = "3" not "19,000 + 3"; the
       *  badge tells the reader what's actually clickable. */}
      <div className={styles.presetBar} role="tablist" aria-label="Catalog presets">
        {PRESETS.map((p) => {
          const count = p.key === "all"
            ? rows.length
            : rows.reduce(
                (n, r) => (r.deep_dive_filters && p.predicate(r.deep_dive_filters) ? n + 1 : n),
                0,
              );
          const on = presetKey === p.key;
          return (
            <button
              key={p.key}
              type="button"
              role="tab"
              aria-selected={on}
              className={`${styles.presetChip} ${on ? styles.presetChipOn : ""}`}
              onClick={() => {
                setPresetKey(p.key);
                // Reset the induction sub-axis whenever the parent
                // preset changes — otherwise stale sub-selections
                // would silently narrow the new preset.
                if (p.key !== "induced") setInductionSub(null);
              }}
              title={p.description}
            >
              {p.label}
              <span className={styles.presetCount}>{count.toLocaleString()}</span>
            </button>
          );
        })}
        {/* Induction sub-chips — only meaningful when Induced is
         *  active. Hidden otherwise to avoid visual clutter. */}
        {presetKey === "induced" ? (
          <div className={styles.presetSubBar}>
            <span className={`label-mono ${styles.presetSubLabel}`}>
              by trigger:
            </span>
            {INDUCTION_SUBS.map((s) => {
              const count = rows.reduce(
                (n, r) =>
                  r.deep_dive_filters &&
                  PRESETS.find((p) => p.key === "induced")!.predicate(r.deep_dive_filters) &&
                  s.predicate(r.deep_dive_filters)
                    ? n + 1
                    : n,
                0,
              );
              const on = inductionSub === s.key;
              return (
                <button
                  key={s.key}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  className={`${styles.presetChip} ${styles.presetSubChip} ${on ? styles.presetChipOn : ""}`}
                  onClick={() => setInductionSub((cur) => (cur === s.key ? null : s.key))}
                  title={s.description}
                >
                  {s.label}
                  <span className={styles.presetCount}>{count.toLocaleString()}</span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

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
          <div className={styles.filterGroup}>
            {/* === Databases group =================================
             *  Independent of the agent pipeline — these are the 5
             *  gating DB votes from the candidate-universe build
             *  (UniProt, GO, SURFY, CSPA, HPA). Moved out of the
             *  Triage group per user feedback: DB votes are neither
             *  triage nor deep-dive output, they're an upstream
             *  signal that both pipelines consume. */}
            <div className={styles.groupHeaderRow}>
              <button
                type="button"
                className={styles.groupHeader}
                onClick={() => setDatabasesGroupOpen((v) => !v)}
                aria-expanded={databasesGroupOpen}
                aria-controls="catalog-filter-group-databases"
              >
                <span className={styles.groupHeaderChevron} aria-hidden="true">
                  {databasesGroupOpen ? "▾" : "▸"}
                </span>
                Databases
                {!databasesGroupOpen && dbFilter.size > 0 ? (
                  <span className={styles.chipCount}>{dbFilter.size}</span>
                ) : null}
              </button>
              <InfoTip label="About the Databases filter group" wide>
                {tooltips.catalog_databases_group}
              </InfoTip>
            </div>
            {databasesGroupOpen ? (
              <div
                id="catalog-filter-group-databases"
                className={styles.groupBody}
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
              </div>
            ) : null}
          </div>{/* end .filterGroup (Databases) */}

          {/* === Triage group ===================================== */}
          <div className={styles.filterGroup}>
            <div className={styles.groupHeaderRow}>
              <button
                type="button"
                className={styles.groupHeader}
                onClick={() => setTriageGroupOpen((v) => !v)}
                aria-expanded={triageGroupOpen}
                aria-controls="catalog-filter-group-triage"
              >
                <span className={styles.groupHeaderChevron} aria-hidden="true">
                  {triageGroupOpen ? "▾" : "▸"}
                </span>
                Triage
                {!triageGroupOpen &&
                verdictFilter.size +
                  reasonFilter.size +
                  (deepDiveFilter !== null ? 1 : 0) >
                  0 ? (
                  <span className={styles.chipCount}>
                    {verdictFilter.size +
                      reasonFilter.size +
                      (deepDiveFilter !== null ? 1 : 0)}
                  </span>
                ) : null}
              </button>
              <InfoTip label="About the Triage filter group" wide>
                {tooltips.catalog_triage_group}
              </InfoTip>
            </div>
            {triageGroupOpen ? (
              <div
                id="catalog-filter-group-triage"
                className={styles.groupBody}
              >
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

              </div>
            ) : null}
          </div>{/* end .filterGroup (Triage) */}

          {/* === Deep Dive group =====================================
           *  Three independently-collapsible subsections inside:
           *    • Surface call — synthesizer's own classifications,
           *      re-emitted from the merged A1+A2 evidence ledger
           *      (LLM rollups, excluding the risk fields)
           *    • Risks — accessibility risks (shed / secreted decoy
           *      pool, epitope masking, co-receptor dependency) tagged
           *      isRisk in lib/deep-dive-fields.ts; LLM provenance but
           *      a separate topical bucket
           *    • Deterministic — tool-derived readouts (DeepTMHMM
           *      topology, ledger-count buckets, SURFACE-Bind MaSIF
           *      patch scoring from Balbi et al 2026 PNAS, PMID
           *      41604262). No LLM involvement; reproducible by
           *      re-running the underlying tool.
           *  SURFACE-Bind patch radio absorbed here per user
           *  feedback (was previously a 4th top-level group). */}
          <div className={styles.filterGroup}>
            <div className={styles.groupHeaderRow}>
              <button
                type="button"
                className={styles.groupHeader}
                onClick={() => setDeepDiveGroupOpen((v) => !v)}
                aria-expanded={deepDiveGroupOpen}
                aria-controls="catalog-filter-group-deep-dive"
              >
                <span className={styles.groupHeaderChevron} aria-hidden="true">
                  {deepDiveGroupOpen ? "▾" : "▸"}
                </span>
                Deep Dive
                {!deepDiveGroupOpen && ddActiveCount > 0 ? (
                  <span className={styles.chipCount}>{ddActiveCount}</span>
                ) : null}
              </button>
              <InfoTip label="About the Deep Dive filter group" wide>
                {tooltips.catalog_deep_dive_group}
              </InfoTip>
            </div>
            {deepDiveGroupOpen ? (
              <div
                id="catalog-filter-group-deep-dive"
                className={styles.groupBody}
              >
                {n_with_deep_dive === 0 ? (
                  <p className={styles.ddEmptyHint}>
                    No rows carry deep-dive filters yet. The catalog
                    payload exposes them once the Worker rev that
                    serves the `deep_dive_filters` projection is live.
                  </p>
                ) : null}

                {/* ── Surface call subsection (LLM rollups, minus
                 *  risks) — independently collapsible. ──────────── */}
                <div className={styles.subheadButtonRow}>
                  <button
                    type="button"
                    className={styles.subheadButton}
                    onClick={() => setDdLlmOpen((v) => !v)}
                    aria-expanded={ddLlmOpen}
                  >
                    <span className={styles.groupHeaderChevron} aria-hidden="true">
                      {ddLlmOpen ? "▾" : "▸"}
                    </span>
                    Surface call
                  </button>
                  <InfoTip wide label="About surface-call deep-dive filters">
                    {tooltips.catalog_deep_dive_llm_subhead}
                  </InfoTip>
                </div>
                {ddLlmOpen ? (
                  <div className={styles.subgroupBody}>
                    {DD_ENUM_FIELDS.filter(
                      (f) => f.provenance === "llm" && !f.isRisk,
                    ).map(renderDdEnumRow)}
                    {DD_BOOL_FIELDS.filter(
                      (f) => f.provenance === "llm" && !f.isRisk,
                    ).map(renderDdBoolRow)}
                  </div>
                ) : null}

                {/* ── Risks subsection — accessibility risks tagged
                 *  isRisk in lib/deep-dive-fields.ts (orthogonal to
                 *  provenance). Independently collapsible. ───────── */}
                <div className={styles.subheadButtonRow}>
                  <button
                    type="button"
                    className={styles.subheadButton}
                    onClick={() => setDdRisksOpen((v) => !v)}
                    aria-expanded={ddRisksOpen}
                  >
                    <span className={styles.groupHeaderChevron} aria-hidden="true">
                      {ddRisksOpen ? "▾" : "▸"}
                    </span>
                    Risks
                  </button>
                  <InfoTip wide label="About risk filters">
                    {tooltips.catalog_deep_dive_risks_subhead}
                  </InfoTip>
                </div>
                {ddRisksOpen ? (
                  <div className={styles.subgroupBody}>
                    {DD_ENUM_FIELDS.filter((f) => f.isRisk).map(renderDdEnumRow)}
                    {DD_BOOL_FIELDS.filter((f) => f.isRisk).map(renderDdBoolRow)}
                  </div>
                ) : null}

                {/* ── Deterministic subsection — tool readouts +
                 *  SURFACE-Bind radio. Independently collapsible. ── */}
                <div className={styles.subheadButtonRow}>
                  <button
                    type="button"
                    className={styles.subheadButton}
                    onClick={() => setDdDetOpen((v) => !v)}
                    aria-expanded={ddDetOpen}
                  >
                    <span className={styles.groupHeaderChevron} aria-hidden="true">
                      {ddDetOpen ? "▾" : "▸"}
                    </span>
                    Deterministic
                  </button>
                  <InfoTip
                    wide
                    label="About deterministic-tool deep-dive filters"
                  >
                    {tooltips.catalog_deep_dive_deterministic_subhead}
                  </InfoTip>
                </div>
                {ddDetOpen ? (
                  <div className={styles.subgroupBody}>
                    {/* SURFACE-Bind patch radio FIRST — moved here from
                     *  the deleted top-level SURFACE-Bind group. Source:
                     *  Balbi et al 2026 PNAS (PMID 41604262); see
                     *  tooltips.catalog_surface_bind_group for the
                     *  citation context (still wired through the gene-
                     *  page SURFACE-Bind card). The 4-way radio is the
                     *  same shape as before: any / ≥1 / ≥3 / not in.
                     *  Not in DD_ENUM/BOOL_FIELDS — inline JSX. */}
                    <div
                      className={styles.filterRow}
                      role="radiogroup"
                      aria-label="SURFACE-Bind site count"
                    >
                      <span className={styles.filterLabel}>SURFACE-Bind</span>
                      <div className={styles.filterChips}>
                        {(
                          [
                            { k: "any", label: "any (scored)" },
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
                        {`"any" includes proteins scored with 0 patches; "not in" = filtered at structural QC. Click an active chip to clear.`}
                      </span>
                    </div>
                    {DD_ENUM_FIELDS.filter(
                      (f) => f.provenance === "deterministic",
                    ).map(renderDdEnumRow)}
                    {DD_BOOL_FIELDS.filter(
                      (f) => f.provenance === "deterministic",
                    ).map(renderDdBoolRow)}
                  </div>
                ) : null}
              </div>
            ) : null}
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
            ; the full deep-dive SurfaceomeRecord is on{" "}
            <Link href="/api/#genes" className={styles.apiHintLink}>
              <code>GET /v1/genes/&#123;SYMBOL&#125;</code>
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
        {/* Header row — sticky, identical grid template as every body row.
            "Deep dive" is the deep-dive agent's headline call, mirroring the
            "Triage agent" column; Conf / Evidence / State dep. are its
            supporting vitals (each with an InfoTip). */}
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
            k="dd_access"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Deep-dive agent surface verdict (sort)"
            extraClass={styles.ddHeaderCell}
            info="The deep-dive agent's surface verdict — does this protein reach the cell surface in at least one cell state (high, moderate, low, or no)? The levels are evidence strength for the surfaces-at-all call, not a steady-state magnitude. Present only for genes with a deep dive; click to open it."
          />
          <SortableHeader
            label="Conf"
            k="dd_conf"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Deep-dive agent confidence in the call (sort)"
            extraClass={styles.ddHeaderCell}
            info="How confident the deep-dive agent is in its surface verdict — high, moderate, or low."
          />
          <SortableHeader
            label="Evidence"
            k="dd_evidence"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Deep-dive experimental surface-evidence grade (sort)"
            extraClass={styles.ddHeaderCell}
            info="Strength of the experimental surface evidence behind the call — from direct multi-method down to weak or conflicting."
          />
          <SortableHeader
            label="State dep."
            k="dd_state"
            sortKey={sortKey}
            sortDir={sortDir}
            onClick={setSort}
            align="center"
            title="Deep-dive state-dependence of the surface call (sort)"
            extraClass={styles.ddHeaderCell}
            info="How much the surface verdict depends on cell state or context (e.g. activation, stress) — low, moderate, or high."
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
        drawerRef={drawerRef}
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
  // Deep-dive vitals — ordinal scales so DESC puts the strongest call on
  // top (mirrors the gene-page traffic-light ordering). Null / no-deep-dive
  // sorts to 0 (the bottom on DESC).
  if (k === "dd_access") {
    const v = r.deep_dive_filters?.surface_accessibility;
    return v === "high" ? 4 : v === "moderate" ? 3 : v === "low" ? 2 : v === "no" ? 1 : 0;
  }
  if (k === "dd_conf") {
    const v = r.deep_dive_filters?.confidence;
    return v === "high" ? 3 : v === "moderate" ? 2 : v === "low" ? 1 : 0;
  }
  if (k === "dd_evidence") {
    const v = r.deep_dive_filters?.evidence_grade;
    return v === "direct_multi_method"
      ? 5
      : v === "direct_single_method"
        ? 4
        : v === "supportive_but_indirect"
          ? 3
          : v === "conflicting"
            ? 2
            : v === "weak"
              ? 1
              : 0;
  }
  if (k === "dd_state") {
    const v = r.deep_dive_filters?.state_dependence;
    return v === "high" ? 3 : v === "moderate" ? 2 : v === "low" ? 1 : 0;
  }
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
  info,
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
  /** Optional InfoTip body rendered as a sibling ⓘ after the sort
   *  button (e.g. a one-line explanation of a deep-dive vital). Its
   *  trigger is a separate <button>, so clicking ⓘ never triggers sort. */
  info?: ReactNode;
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
      {info ? (
        <InfoTip align="end" label={`About the ${label} column`}>
          {info}
        </InfoTip>
      ) : null}
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
  // Short name (the symbol — which IS the protein short name for most
  // genes: EGFR, CD81, LAT, FN1) leads as the primary identifier; the
  // long descriptive name is the subtitle for readers who don't know
  // the symbol cold. Falls back to symbol-only when no description.
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
          // Prefer the DEEP-DIVE reason (surface_call_reason — re-derived
          // from the full evidence ledger) when a deep dive exists; fall
          // back to the first-pass triage reason otherwise.
          const ddReason = row.deep_dive_filters?.surface_call_reason;
          const triageReason = row.triage_by_model[1]?.reason;
          const reason = ddReason ?? triageReason;
          if (!reason) return <span className={styles.dim}>—</span>;
          const pretty = reason.replace(/_/g, " ");
          const src = ddReason ? "deep dive" : "triage";
          return (
            <span className={styles.reasonText} title={`${pretty} (${src})`}>
              {pretty}
            </span>
          );
        })()}
      </div>
      {(() => {
        // 4 deep-dive vitals — "Deep dive" (the headline accessibility call,
        // mirroring Triage) · Conf · Evidence · State dep., toned with the
        // gene-page traffic-light scale. Empty dash when no deep dive; each
        // populated vital links to the gene's deep-dive page.
        const ddf = row.deep_dive_filters;
        const vital = (
          val: string | null | undefined,
          tone: VitalTone,
          label: string,
          title: string,
        ) => (
          <div className={`${styles.cell} ${styles.ddCell}`} role="cell">
            {val ? (
              <Link
                href={`/${row.symbol}/`}
                className={`${styles.ddVital} ${DD_TONE_CLASS[tone]} ${styles.ddVitalLink}`}
                title={`${title} — open the ${row.symbol} deep-dive`}
                aria-label={`${title} — open the ${row.symbol} deep-dive page`}
              >
                {label}
              </Link>
            ) : (
              <span className={styles.dim}>—</span>
            )}
          </div>
        );
        return (
          <>
            {vital(
              ddf?.surface_accessibility,
              accessibilityTone(ddf?.surface_accessibility),
              ddf?.surface_accessibility ?? "—",
              `Deep-dive surface verdict: ${ddf?.surface_accessibility ?? "n/a"}`,
            )}
            {vital(
              ddf?.confidence,
              confidenceTone(ddf?.confidence),
              ddf?.confidence ?? "—",
              `Deep-dive confidence: ${ddf?.confidence ?? "n/a"}`,
            )}
            {vital(
              ddf?.evidence_grade,
              gradeTone(ddf?.evidence_grade),
              ddShort(ddf?.evidence_grade),
              `Deep-dive evidence grade: ${(ddf?.evidence_grade ?? "n/a").replace(/_/g, " ")}`,
            )}
            {vital(
              ddf?.state_dependence,
              stateDependenceTone(ddf?.state_dependence),
              ddf?.state_dependence ?? "—",
              `Deep-dive state dependence: ${ddf?.state_dependence ?? "n/a"}`,
            )}
          </>
        );
      })()}
    </div>
  );
}
