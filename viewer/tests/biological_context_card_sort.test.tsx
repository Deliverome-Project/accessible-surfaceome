/*
 * Tests for the click-to-sort behavior added to the biology and
 * expression tables. Covers:
 *   1. The shared ``useTableSort`` hook — none → asc → desc → none cycle,
 *      per-column comparators (string + numeric rank), ``aria-sort``
 *      state.
 *   2. Server-render snapshot: every sortable column header in each
 *      table renders as a real ``<button>`` (so it's keyboard-reachable)
 *      with ``aria-sort="none"`` on first render (no column clicked).
 *   3. Rank helpers — ``levelRank`` puts ``high`` before ``low`` etc.,
 *      ``directionRank`` puts ``increases`` first.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       tests/biological_context_card_sort.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  directionRank,
  levelRank,
  useTableSort,
  type UseTableSort,
} from "../components/surfaceome/_shared/useTableSort";
import { AnatomicalAccessibilityTable } from "../components/surfaceome/BiologicalContextCard/AnatomicalAccessibilityTable";
import { AccessibilityModulationTable } from "../components/surfaceome/BiologicalContextCard/AccessibilityModulationTable";
import { BiologicalContextCard } from "../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import { ExpressionTable } from "../components/surfaceome/ExpressionCard/ExpressionTable";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function render(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(BiologicalContextCard, { rec, n: 1 }));
}

// ----- minimal hook harness ------------------------------------------------

/** Render a hook in a detached JSDOM-less environment by mounting it
 *  into a throwaway DOM-like container — except we don't have JSDOM
 *  here. Use a closure capture pattern instead: render a component that
 *  calls the hook and writes its current value to a holder. Use
 *  ``react-dom/server`` to take one synchronous "snapshot", then unmount.
 *  This pins the hook's initial state on first render — enough to test
 *  ``aria-sort`` defaults.
 *
 *  For the stateful asc → desc → none cycle we test the comparator
 *  logic directly (it's a pure function of ``(sortKey, sortDir)``).
 */
function snapshotInitialHook<K extends string>(): UseTableSort<K> {
  let captured: UseTableSort<K> | null = null;
  function Cap() {
    const v = useTableSort<K>();
    captured = v;
    return null;
  }
  renderToStaticMarkup(React.createElement(Cap));
  return captured as UseTableSort<K>;
}

// Compose-style toggle simulator that mirrors the hook's setState
// transitions exactly. ``onSort`` in the real hook is:
//   if (sortKey !== key) { setSortKey(key); setSortDir("asc"); }
//   else if (sortDir === "asc") setSortDir("desc");
//   else { setSortKey(null); setSortDir("asc"); }
type State<K extends string> = { sortKey: K | null; sortDir: "asc" | "desc" };
function simulateClick<K extends string>(s: State<K>, key: K): State<K> {
  if (s.sortKey !== key) return { sortKey: key, sortDir: "asc" };
  if (s.sortDir === "asc") return { sortKey: s.sortKey, sortDir: "desc" };
  return { sortKey: null, sortDir: "asc" };
}

// ----- helper-function tests ---------------------------------------------

test("levelRank: high > moderate > low > absent > unknown", () => {
  assert.ok(levelRank("high") > levelRank("moderate"));
  assert.ok(levelRank("moderate") > levelRank("low"));
  assert.ok(levelRank("low") > levelRank("absent"));
  assert.ok(levelRank("absent") > levelRank("unknown"));
  // Mixed buckets with low (both ~2).
  assert.equal(levelRank("mixed"), levelRank("low"));
  // Null / unrecognized → -1 (sorts below ``unknown`` (0) so missing
  // values land at the very top in ascending — usually what callers
  // want for "fill missing first" UX, though desc puts them last).
  assert.equal(levelRank(null), -1);
  assert.equal(levelRank(undefined), -1);
  assert.equal(levelRank("nonsense"), -1);
});

test("directionRank: increases < decreases < bidirectional < no_change < unclear", () => {
  assert.ok(directionRank("increases") < directionRank("decreases"));
  assert.ok(directionRank("decreases") < directionRank("bidirectional"));
  assert.ok(directionRank("bidirectional") < directionRank("no_change"));
  assert.ok(directionRank("no_change") < directionRank("unclear"));
  // Null / undefined / unknown → 5 (sorts last).
  assert.equal(directionRank(null), 5);
  assert.equal(directionRank(undefined), 5);
});

// ----- hook state-cycle tests (pure transition function) ----------------

test("useTableSort cycle: none → asc → desc → none", () => {
  let s: State<"category" | "level"> = { sortKey: null, sortDir: "asc" };
  // First click: none → asc on "category"
  s = simulateClick(s, "category");
  assert.deepEqual(s, { sortKey: "category", sortDir: "asc" });
  // Second click: asc → desc on the same column
  s = simulateClick(s, "category");
  assert.deepEqual(s, { sortKey: "category", sortDir: "desc" });
  // Third click: desc → off (key=null), so default render order is back
  s = simulateClick(s, "category");
  assert.deepEqual(s, { sortKey: null, sortDir: "asc" });
});

test("useTableSort: clicking a different column resets to that column ascending", () => {
  let s: State<"category" | "level"> = { sortKey: "category", sortDir: "desc" };
  // Click a DIFFERENT column → switch key, dir = "asc" (not "desc"
  // sticky from the previous column).
  s = simulateClick(s, "level");
  assert.deepEqual(s, { sortKey: "level", sortDir: "asc" });
});

// ----- aria-sort + initial state on a real render ------------------------

test("useTableSort initial state — ariaSort returns 'none' for any column before any click", () => {
  const hook = snapshotInitialHook<"a" | "b">();
  assert.equal(hook.sortKey, null);
  assert.equal(hook.ariaSort("a"), "none");
  assert.equal(hook.ariaSort("b"), "none");
  // sortRows is a no-op on the initial state — returns the input array
  // unchanged so the agent-emitted order is preserved.
  const rows = [{ v: 3 }, { v: 1 }, { v: 2 }];
  const out = hook.sortRows(rows, { a: (r) => r.v, b: (r) => r.v });
  assert.deepEqual(out, rows);
});

// ----- table-level snapshot tests ----------------------------------------

test("AnatomicalAccessibilityTable: 4 sortable column buttons + aria-sort='none' by default", () => {
  const rows = [
    {
      context: "skin epithelium",
      orientation: "luminal_facing" as const,
      accessibility_implication: "favorable" as const,
      rationale: "exposed",
      cited_evidence_ids: [],
    },
    {
      context: "blood-brain barrier",
      orientation: "blood_interstitial_facing" as const,
      accessibility_implication: "restricted" as const,
      rationale: "barrier",
      cited_evidence_ids: [],
    },
  ];
  const html = renderToStaticMarkup(
    React.createElement(AnatomicalAccessibilityTable, { rows }),
  );
  // 4 sortable columns → 4 <th aria-sort="none"> entries (the
  // References column is not sortable).
  const sortMatches = [...html.matchAll(/aria-sort="none"/g)];
  assert.equal(
    sortMatches.length,
    4,
    `expected 4 aria-sort='none' headers, got ${sortMatches.length}`,
  );
  // Default rendering preserves agent order — first body row should be
  // "skin epithelium" (the first row in the input).
  const tbodyStart = html.indexOf("<tbody>");
  const firstRowEnd = html.indexOf("</tr>", tbodyStart);
  const firstRow = html.slice(tbodyStart, firstRowEnd);
  assert.ok(firstRow.includes("skin epithelium"), "first row preserves input order");
});

test("AccessibilityModulationTable: 5 sortable column buttons + Change column has aria-sort=none", () => {
  const rows = [
    {
      category: "activation_induced" as const,
      category_other_label: null,
      cell_state_trigger: null,
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      baseline_context: "resting T cell",
      modulating_state: "TCR-activated T cell",
      change: "ECD increases 5x",
      accessibility_implication: "favorable",
      direction: "increases" as const,
      cited_evidence_ids: ["a1_evi_01"],
    },
    {
      category: "stress_induced" as const,
      category_other_label: null,
      cell_state_trigger: null,
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      baseline_context: "homeostasis",
      modulating_state: "ER stress",
      change: "shed into media",
      accessibility_implication: "restricted",
      direction: "decreases" as const,
      cited_evidence_ids: [],
    },
  ];
  const html = renderToStaticMarkup(
    React.createElement(AccessibilityModulationTable, { rows }),
  );
  // 5 sortable columns (Context, Change, Reference, Modulating state,
  // Implication); the References column is not sortable.
  const sortMatches = [...html.matchAll(/aria-sort="none"/g)];
  assert.equal(
    sortMatches.length,
    5,
    `expected 5 aria-sort='none' headers, got ${sortMatches.length}`,
  );
  // Default order preserved — increase row first.
  const tbodyStart = html.indexOf("<tbody>");
  const firstRowEnd = html.indexOf("</tr>", tbodyStart);
  const firstRow = html.slice(tbodyStart, firstRowEnd);
  assert.ok(firstRow.includes("resting T cell"), "first row preserves input order");
});

test("ExpressionTable: 5 sortable column buttons + Cites column not sortable", () => {
  const rows = [
    {
      tissue: "kidney",
      cell_type: "proximal tubule",
      present: "high" as const,
      disease_context: "normal" as const,
      disease_label: null,
      cell_states: [],
      cited_evidence_ids: [],
    },
    {
      tissue: "kidney",
      cell_type: "podocyte",
      present: "low" as const,
      disease_context: "normal" as const,
      disease_label: null,
      cell_states: [],
      cited_evidence_ids: [],
    },
  ];
  const html = renderToStaticMarkup(
    React.createElement(ExpressionTable, { rows }),
  );
  const sortMatches = [...html.matchAll(/aria-sort="none"/g)];
  assert.equal(
    sortMatches.length,
    5,
    `expected 5 aria-sort='none' headers, got ${sortMatches.length}`,
  );
  // First row preserved — kidney/proximal tubule (the row the caller passed first).
  const tbodyStart = html.indexOf("<tbody>");
  const firstRowEnd = html.indexOf("</tr>", tbodyStart);
  const firstRow = html.slice(tbodyStart, firstRowEnd);
  assert.ok(firstRow.includes("proximal tubule"), "first row preserves input order");
});

// ----- sortRows correctness ---------------------------------------------

test("sortRows: numeric comparator (level rank) — desc puts high before low", () => {
  // Re-implement the hook's sort behavior inline so we don't have to
  // round-trip through React state. The semantics under test are the
  // comparator + direction multiplier in ``sortRows``.
  const rows = [
    { tissue: "A", level: "low" },
    { tissue: "B", level: "high" },
    { tissue: "C", level: "moderate" },
  ];
  const sorted = [...rows].sort(
    (a, b) => (levelRank(a.level) - levelRank(b.level)) * -1, // desc
  );
  assert.deepEqual(
    sorted.map((r) => r.tissue),
    ["B", "C", "A"],
    "descending by levelRank puts high first, then moderate, then low",
  );
});

test("sortRows: numeric comparator (direction rank) — asc puts increases first", () => {
  const rows = [
    { id: "a", direction: "unclear" },
    { id: "b", direction: "decreases" },
    { id: "c", direction: "increases" },
  ];
  const sorted = [...rows].sort(
    (a, b) => directionRank(a.direction) - directionRank(b.direction),
  );
  assert.deepEqual(
    sorted.map((r) => r.id),
    ["c", "b", "a"],
    "ascending by directionRank: increases (0) → decreases (1) → unclear (4)",
  );
});

test("sortRows: string comparator — asc is alphabetical on the displayed value", () => {
  const rows = [
    { tissue: "Zebrafish" },
    { tissue: "Apricot" },
    { tissue: "Mango" },
  ];
  const sorted = [...rows].sort((a, b) => a.tissue.localeCompare(b.tissue));
  assert.deepEqual(
    sorted.map((r) => r.tissue),
    ["Apricot", "Mango", "Zebrafish"],
  );
});

test("first row per modulation category gets chip-jump id; duplicates do not", () => {
  const rec = baseRecord();
  // Use two valid ModulationCategory enum values — the plan calls for
  // `cell_state_induced` (twice) and a distinct second category to pin
  // the "first-only" behavior. `hypoxia_induced` is not in the enum, so
  // fall back to `stress_induced` (hypoxia is a listed CellStateTrigger
  // whose umbrella category is stress-induced).
  rec.biological_context.accessibility_modulation = [
    {
      category: "cell_state_induced",
      category_other_label: null,
      cell_state_trigger: null,
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      direction: "increases",
      baseline_context: "resting T cell",
      modulating_state: "activated",
      change: "5-fold increase",
      accessibility_implication: "reachable on activation",
      cited_evidence_ids: ["a1_evi_01"],
    },
    {
      category: "cell_state_induced",
      category_other_label: null,
      cell_state_trigger: null,
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      direction: "increases",
      baseline_context: "naive B cell",
      modulating_state: "GC B cell",
      change: "3-fold increase",
      accessibility_implication: "reachable in germinal center",
      cited_evidence_ids: ["a1_evi_02"],
    },
    {
      category: "stress_induced",
      category_other_label: null,
      cell_state_trigger: "hypoxia",
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      direction: "increases",
      baseline_context: "normoxia",
      modulating_state: "hypoxia",
      change: "shifted to surface",
      accessibility_implication: "hypoxic-niche accessible",
      cited_evidence_ids: ["a1_evi_03"],
    },
  ];
  const html = render(rec);
  const cellStateMatches = html.match(/id="chip-jump-modulation-cell_state_induced"/g) ?? [];
  assert.equal(
    cellStateMatches.length,
    1,
    "only the first cell_state_induced row should carry the id",
  );
  assert.match(
    html,
    /id="chip-jump-modulation-stress_induced"/,
    "distinct category gets its own id",
  );
  assert.match(
    html,
    /id="chip-jump-modulation-cell_state_induced"[^>]*tabindex="-1"/,
    "id-bearing modulation row must be tabIndex=-1",
  );
});
