# Clickable §01 Summary metrics chips — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each §01 Summary metrics chip that has "more information" (a rationale row on a tab, or a destination detail block) act as a one-click shortcut: switch to the destination tab and scroll to the matching row with a brief highlight.

**Architecture:** New shared `<ChipJumpButton>` wraps rationale-bearing chips. It sets `location.hash` via `history.replaceState` + dispatches a synthetic `hashchange` event so `<SectionTabs>`'s existing listener swaps the active tab. In the next `requestAnimationFrame` we find the destination element by id, `scrollIntoView`, add a shared `.chip-jump-flash` class for ~1.2 s, and move keyboard focus. Destination ids live in one central map (`viewer/lib/chipJumpTargets.ts`) so producers and consumers can't drift.

**Tech Stack:** Next.js 16 (viewer), React 19, TypeScript, `node:test` + `react-dom/server`'s `renderToStaticMarkup` for render tests (viewer/tests convention; CSS-modules stubbed via `tests/helpers/register.mjs`).

**Reference spec:** `docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md`.

---

## File Structure

**Create:**
- `viewer/lib/chipJumpTargets.ts` — central id-string map. Every producer / consumer imports from here.
- `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.tsx` — the wrapper button.
- `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.module.css` — button styling.
- `viewer/tests/chip_jump_targets.test.ts` — unit test for id shape.
- `viewer/tests/chip_jump_button.test.tsx` — render test for the button component.
- `viewer/tests/filters_card_chip_jump.test.tsx` — render test that FiltersCard wires the composed chips + FeatureChips rationale chips.

**Modify:**
- `viewer/app/globals.css` — add `.chip-jump-flash` keyframes + utility class.
- `viewer/components/surfaceome/FeatureChips/FeatureChips.tsx` — wrap each rationale-bearing chip in `<ChipJumpButton>`; add `id` + `tabIndex={-1}` to each `<FeatureRationales>` row.
- `viewer/components/surfaceome/FiltersCard/FiltersCard.tsx` — wrap `primary`, `contradiction` (when severity ≠ `none`), and modulation-category chips in `<ChipJumpButton>`.
- `viewer/components/surfaceome/BiologicalContextCard/BiologicalContextCard.tsx` — add `id` + `tabIndex={-1}` to the "Subcellular localization" subsection block.
- `viewer/components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard.tsx` — add `id` + `tabIndex={-1}` to the "Contradicting evidence" subsection block.
- `viewer/components/surfaceome/BiologicalContextCard/AccessibilityModulationTable.tsx` — add `id` + `tabIndex={-1}` to the first row (in currently-sorted order) for each distinct `category`.
- `viewer/tests/run_render_tests.sh` — append the two new render test files.

**Do not touch:** `SectionTabs`, `AnchorNav`, `ReasoningDrawer`, `GeneHeader` vitals, record schema, D1, Worker.

---

## Task 1: Central destination-id map

**Files:**
- Create: `viewer/lib/chipJumpTargets.ts`
- Test: `viewer/tests/chip_jump_targets.test.ts`

- [ ] **Step 1: Write the failing test**

Create `viewer/tests/chip_jump_targets.test.ts`:

```ts
/*
 * Unit tests for viewer/lib/chipJumpTargets — the central destination-id
 * map wired between §01 summary chips (producers) and their destination
 * rows / blocks on the Biology / Expression / Risks / Evidence tabs.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/chip_jump_targets.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { chipJumpTargets } from "../lib/chipJumpTargets";

test("featureRationale composes category and key", () => {
  assert.equal(
    chipJumpTargets.featureRationale("biology", "ligand"),
    "chip-jump-biology-ligand",
  );
  assert.equal(
    chipJumpTargets.featureRationale("expression", "level"),
    "chip-jump-expression-level",
  );
});

test("primaryCompartment is a constant", () => {
  assert.equal(chipJumpTargets.primaryCompartment, "chip-jump-primary-compartment");
});

test("contradictingEvidence is a constant", () => {
  assert.equal(
    chipJumpTargets.contradictingEvidence,
    "chip-jump-contradicting-evidence",
  );
});

test("modulationCategory composes category value", () => {
  assert.equal(
    chipJumpTargets.modulationCategory("cell_state_induced"),
    "chip-jump-modulation-cell_state_induced",
  );
});

test("ids are valid HTML fragment identifiers (no spaces, no leading digit)", () => {
  const samples = [
    chipJumpTargets.featureRationale("risks", "epitope"),
    chipJumpTargets.primaryCompartment,
    chipJumpTargets.contradictingEvidence,
    chipJumpTargets.modulationCategory("hypoxia_induced"),
  ];
  for (const id of samples) {
    assert.match(id, /^[a-z][a-z0-9_-]*$/, `id "${id}" must be a safe fragment identifier`);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/chip_jump_targets.test.ts`

Expected: FAIL with `Cannot find module '../lib/chipJumpTargets'`.

- [ ] **Step 3: Write minimal implementation**

Create `viewer/lib/chipJumpTargets.ts`:

```ts
/*
 * Central destination-id map for §01 Summary metrics chip jumps.
 *
 * Both producers (the destination elements on the Biology / Expression
 * / Risks / Evidence tabs) and consumers (the ChipJumpButton wrappers
 * in FiltersCard + FeatureChips) import from this file. Hard-coding
 * the same id in two places would silently drift; one source of truth
 * is the whole point.
 *
 * See docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md.
 */

/** SectionTabs section id → the string that follows "#section-" in the
 *  URL hash. Matches keys in FeatureChips.tsx's FEATURE_CATEGORIES. */
export type ChipJumpTab = "biology" | "expression" | "risks" | "evidence";

export const chipJumpTargets = {
  /** FeatureRationales row for chip `key` in `category`. */
  featureRationale: (category: "biology" | "expression" | "risks", key: string): string =>
    `chip-jump-${category}-${key}`,
  /** Subcellular-localization block on the Biology tab. */
  primaryCompartment: "chip-jump-primary-compartment",
  /** Contradicting-evidence block on the Evidence tab. */
  contradictingEvidence: "chip-jump-contradicting-evidence",
  /** First row (in currently-sorted order) matching `category` in the
   *  accessibility-modulation table on the Biology tab. */
  modulationCategory: (category: string): string => `chip-jump-modulation-${category}`,
} as const;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/chip_jump_targets.test.ts`

Expected: PASS (5/5 tests).

- [ ] **Step 5: Commit**

```bash
git add viewer/lib/chipJumpTargets.ts viewer/tests/chip_jump_targets.test.ts
git commit -m "feat(viewer): central destination-id map for chip jumps"
```

---

## Task 2: `.chip-jump-flash` shared utility class

**Files:**
- Modify: `viewer/app/globals.css`

- [ ] **Step 1: Add the keyframes + utility class**

Open `viewer/app/globals.css`. Append at the end of the file (or under the "utility classes" section if one exists):

```css
/* Post-jump highlight applied to a destination element for ~1.2s after
 * the reader clicks a §01 Summary metrics chip. Background-only (no
 * transform) so the scroll position doesn't shift mid-animation.
 * Shared by rationale rows on Biology/Expression/Risks tabs, the
 * Subcellular-localization block, the Contradicting-evidence block,
 * and the accessibility-modulation table rows. See
 * viewer/components/surfaceome/_shared/ChipJumpButton/. */
@keyframes chip-jump-flash {
  0%   { background-color: var(--accent-soft); }
  100% { background-color: transparent; }
}
.chip-jump-flash {
  animation: chip-jump-flash 1200ms ease-out;
}
```

- [ ] **Step 2: Confirm CSS is well-formed**

Run: `cd viewer && npx --yes stylelint 'app/globals.css' 2>/dev/null || true`

Expected: no output OR a "no config" message — the file must at least parse. If a `.stylelintrc` exists the run should be clean.

- [ ] **Step 3: Commit**

```bash
git add viewer/app/globals.css
git commit -m "feat(viewer): add .chip-jump-flash post-jump highlight utility"
```

---

## Task 3: `<ChipJumpButton>` component

**Files:**
- Create: `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.tsx`
- Create: `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.module.css`
- Test: `viewer/tests/chip_jump_button.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `viewer/tests/chip_jump_button.test.tsx`:

```tsx
/*
 * Server-render tests for <ChipJumpButton>. Interaction (scroll, focus,
 * hashchange) requires jsdom and is verified by manual QA per the plan;
 * these tests pin the rendered markup — real <button>, aria attrs, and
 * the wrapped chip content — because those are the pieces a screen
 * reader and keyboard user rely on.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/chip_jump_button.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChipJumpButton } from "../components/surfaceome/_shared/ChipJumpButton/ChipJumpButton";

test("renders a real <button> wrapping its children", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-biology-ligand", tabId: "biology", ariaLabel: "Jump to rationale: Known ligand" },
      React.createElement("span", null, "chip-content"),
    ),
  );
  assert.match(html, /<button[^>]*type="button"/);
  assert.ok(html.includes("chip-content"), "children must render inside the button");
});

test("carries aria-label and aria-describedby-style hints", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-primary-compartment", tabId: "biology", ariaLabel: "Jump to Primary compartment" },
      "x",
    ),
  );
  assert.ok(
    html.includes('aria-label="Jump to Primary compartment"'),
    "aria-label must be surfaced in markup",
  );
});

test("target and tab metadata are surfaced as data-* attrs (for e2e)", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-contradicting-evidence", tabId: "evidence", ariaLabel: "Jump to Contradicting evidence" },
      "x",
    ),
  );
  assert.ok(html.includes('data-chip-jump-target="chip-jump-contradicting-evidence"'));
  assert.ok(html.includes('data-chip-jump-tab="evidence"'));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/chip_jump_button.test.tsx`

Expected: FAIL with `Cannot find module '../components/surfaceome/_shared/ChipJumpButton/ChipJumpButton'`.

- [ ] **Step 3: Create the module CSS**

Create `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.module.css`:

```css
/* Wrapper button for a §01 Summary metrics chip that jumps to a
 * matching detail row / block on a Biology / Expression / Risks /
 * Evidence tab. Presents as a transparent, tightly-hugging shell so
 * the wrapped <StatusPill> remains the visual chip — the button
 * exists for semantics, keyboard focus, and a subtle affordance. */
.jumpTrigger {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  margin: 0;
  cursor: pointer;
  display: inline-flex;
  line-height: 0; /* let the pill dictate vertical rhythm */
  border-radius: 999px;
  transition: transform 120ms ease-out, box-shadow 120ms ease-out;
}
.jumpTrigger:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}
.jumpTrigger:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

- [ ] **Step 4: Create the component**

Create `viewer/components/surfaceome/_shared/ChipJumpButton/ChipJumpButton.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";
import styles from "./ChipJumpButton.module.css";

interface ChipJumpButtonProps {
  /** DOM id of the destination element on the target tab. Must match
   *  a value produced by ``viewer/lib/chipJumpTargets``. */
  targetId: string;
  /** SectionTabs section id (the string that follows ``#section-``).
   *  Typically one of ``"biology" | "expression" | "risks" | "evidence"``. */
  tabId: string;
  /** aria-label describing the jump (e.g. "Jump to rationale: Known ligand").
   *  Read by screen readers; also used as a title tooltip fallback. */
  ariaLabel: string;
  /** The pill (or any chip content) rendered inside the button. */
  children: ReactNode;
}

/**
 * Wraps a chip so it acts as a one-click shortcut to a destination row /
 * block on one of the top-level tabs. Behavior on click / Enter / Space:
 *
 *   1. If the destination tab isn't active, update the URL hash via
 *      ``history.replaceState`` and dispatch a synthetic ``hashchange``
 *      event so ``<SectionTabs>``'s existing listener swaps sections.
 *      ``replaceState`` (not ``pushState``) avoids polluting the back
 *      stack with an entry per chip click.
 *   2. In the next animation frame, look up the destination by id,
 *      scroll it into view, add ``.chip-jump-flash`` for ~1.2 s to draw
 *      the eye, and move focus so a keyboard user's caret follows the
 *      visual jump.
 *   3. Missing destination is a no-op with a ``console.warn`` in dev.
 *
 * See docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md.
 */
export function ChipJumpButton({
  targetId,
  tabId,
  ariaLabel,
  children,
}: ChipJumpButtonProps) {
  const onActivate = () => {
    if (typeof window === "undefined") return;
    const desiredHash = `#section-${tabId}`;
    const needsTabSwitch = window.location.hash !== desiredHash;
    if (needsTabSwitch) {
      window.history.replaceState({}, "", desiredHash);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }
    // Wait one frame for SectionTabs to toggle data-active so the
    // destination element is measurable when we scroll to it.
    window.requestAnimationFrame(() => {
      const el = document.getElementById(targetId);
      if (!el) {
        if (process.env.NODE_ENV !== "production") {
          // eslint-disable-next-line no-console
          console.warn(
            `[ChipJumpButton] destination id "${targetId}" not found in the DOM. ` +
              "Chip and destination are out of sync — check viewer/lib/chipJumpTargets.",
          );
        }
        return;
      }
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      el.classList.add("chip-jump-flash");
      window.setTimeout(() => el.classList.remove("chip-jump-flash"), 1300);
      // Move keyboard focus so an assistive-tech reader lands at the
      // destination. `preventScroll` lets the smooth scroll above own
      // the visual motion.
      if (typeof (el as HTMLElement).focus === "function") {
        (el as HTMLElement).focus({ preventScroll: true });
      }
    });
  };

  return (
    <button
      type="button"
      className={styles.jumpTrigger}
      aria-label={ariaLabel}
      data-chip-jump-target={targetId}
      data-chip-jump-tab={tabId}
      onClick={onActivate}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/chip_jump_button.test.tsx`

Expected: PASS (3/3 tests).

- [ ] **Step 6: Commit**

```bash
git add viewer/components/surfaceome/_shared/ChipJumpButton/ viewer/tests/chip_jump_button.test.tsx
git commit -m "feat(viewer): ChipJumpButton wrapper for clickable summary chips"
```

---

## Task 4: Add ids + `tabIndex` to `<FeatureRationales>` rows

**Files:**
- Modify: `viewer/components/surfaceome/FeatureChips/FeatureChips.tsx:441-478`
- Test: extend `viewer/tests/biological_context_card_rationale.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `viewer/tests/biological_context_card_rationale.test.tsx` (append at end, above the last test if any; keep imports intact):

```tsx
test("FeatureRationales row carries chip-jump id + tabIndex for scroll target", () => {
  const rec = baseRecord();
  // The biology category's `spec` chip: value is derived from
  // filters.surface_specificity + rationale; we only need the row
  // to render so its id is emitted.
  rec.filters.surface_specificity = "surface_dominant";
  rec.filters.surface_specificity_rationale = "Membrane-anchored per a1_evi_02.";
  const html = render(rec);
  assert.match(
    html,
    /id="chip-jump-biology-spec"/,
    "biology `spec` rationale row must expose the chipJumpTargets.featureRationale id",
  );
  assert.match(
    html,
    /id="chip-jump-biology-spec"[^>]*tabindex="-1"/,
    "destination row must be programmatically focusable via tabIndex=-1",
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_rationale.test.tsx`

Expected: FAIL — the new test errors because the `id="chip-jump-biology-spec"` regex doesn't match the current markup.

- [ ] **Step 3: Modify `<FeatureRationales>` to emit id + tabIndex**

Open `viewer/components/surfaceome/FeatureChips/FeatureChips.tsx`. At the top of the file (with the other imports), add:

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
```

In the `FeatureRationales` component (around line 449), change the `<div>` opening tag to attach the destination id and make the row programmatically focusable. Replace:

```tsx
      {models.map((m) => (
        <div key={m.key} className={styles.rationaleRow}>
```

with:

```tsx
      {models.map((m) => (
        <div
          key={m.key}
          id={chipJumpTargets.featureRationale(category, m.key)}
          tabIndex={-1}
          className={styles.rationaleRow}
        >
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_rationale.test.tsx`

Expected: PASS on all tests including the new one.

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/FeatureChips/FeatureChips.tsx viewer/tests/biological_context_card_rationale.test.tsx
git commit -m "feat(viewer): id + tabIndex on FeatureRationales rows for chip jumps"
```

---

## Task 5: Wrap rationale-bearing chips in `<FeatureChips>`

**Files:**
- Modify: `viewer/components/surfaceome/FeatureChips/FeatureChips.tsx:415-428`
- Test: create `viewer/tests/filters_card_chip_jump.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `viewer/tests/filters_card_chip_jump.test.tsx`:

```tsx
/*
 * Render tests for the §01 Summary metrics clickable-chip wiring.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/filters_card_chip_jump.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FeatureChips } from "../components/surfaceome/FeatureChips/FeatureChips";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function renderFeatureChips(category: "biology" | "expression" | "risks", rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(FeatureChips, { category, rec }));
}

test("chip with rationale renders inside a ChipJumpButton", () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "IGF-1 binding characterized (a1_evi_04).";
  const html = renderFeatureChips("biology", rec);
  assert.match(
    html,
    /<button[^>]*data-chip-jump-target="chip-jump-biology-ligand"/,
    "ligand chip must be wrapped in a ChipJumpButton",
  );
  assert.match(
    html,
    /aria-label="Jump to rationale: Known ligand"/,
    "aria-label must describe the destination",
  );
});

test("chip without rationale renders as static pill (no button)", () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = false;
  rec.filters.has_known_ligand_rationale = null;
  const html = renderFeatureChips("biology", rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    "no chip-jump-target wrapper when rationale is null",
  );
});

test('rationale === "None" is treated as null (static pill)', () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "None";
  const html = renderFeatureChips("biology", rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    'nz("None") is null → chip stays static',
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/filters_card_chip_jump.test.tsx`

Expected: FAIL — no `<button>` wrapper today.

- [ ] **Step 3: Wrap chips in `<FeatureChips>`**

Open `viewer/components/surfaceome/FeatureChips/FeatureChips.tsx`. At the top of the file, add (if not already added by Task 4):

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
import { ChipJumpButton } from "../_shared/ChipJumpButton/ChipJumpButton";
```

In the `FeatureChips` component (around line 415), replace:

```tsx
      {models.map((m) => (
        <li key={m.key}>{m.pill}</li>
      ))}
```

with:

```tsx
      {models.map((m) => {
        const hasRationale = nz(m.rationale) !== null;
        if (!hasRationale) {
          return <li key={m.key}>{m.pill}</li>;
        }
        return (
          <li key={m.key}>
            <ChipJumpButton
              targetId={chipJumpTargets.featureRationale(category, m.key)}
              tabId={category}
              ariaLabel={`Jump to rationale: ${m.label}`}
            >
              {m.pill}
            </ChipJumpButton>
          </li>
        );
      })}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/filters_card_chip_jump.test.tsx`

Expected: PASS (3/3 tests).

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/FeatureChips/FeatureChips.tsx viewer/tests/filters_card_chip_jump.test.tsx
git commit -m "feat(viewer): wrap rationale-bearing FeatureChips in ChipJumpButton"
```

---

## Task 6: Destination id on subcellular-localization block

**Files:**
- Modify: `viewer/components/surfaceome/BiologicalContextCard/BiologicalContextCard.tsx:90-91`
- Test: extend `viewer/tests/biological_context_card_rationale.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `viewer/tests/biological_context_card_rationale.test.tsx`:

```tsx
test("Subcellular localization subsection carries chip-jump id + tabIndex", () => {
  const rec = baseRecord();
  const html = render(rec);
  // The block MUST exist on every gene (baseRecord() gives it a
  // primary_compartment default), and it must be the scroll target.
  assert.match(
    html,
    /id="chip-jump-primary-compartment"/,
    "subcellular-localization block must expose primaryCompartment id",
  );
  assert.match(
    html,
    /id="chip-jump-primary-compartment"[^>]*tabindex="-1"/,
    "destination block must be programmatically focusable",
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_rationale.test.tsx`

Expected: FAIL — the block currently has no id.

- [ ] **Step 3: Modify `BiologicalContextCard`**

Open `viewer/components/surfaceome/BiologicalContextCard/BiologicalContextCard.tsx`. Add the import near the top of the file:

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
```

At line ~90, replace:

```tsx
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Subcellular localization</p>
```

with:

```tsx
      <div
        id={chipJumpTargets.primaryCompartment}
        tabIndex={-1}
        className={styles.subsection}
      >
        <p className={`label-mono ${styles.subhead}`}>Subcellular localization</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_rationale.test.tsx`

Expected: PASS on all tests including the new one.

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/BiologicalContextCard/BiologicalContextCard.tsx viewer/tests/biological_context_card_rationale.test.tsx
git commit -m "feat(viewer): id + tabIndex on Subcellular localization block for chip jumps"
```

---

## Task 7: Destination id on contradicting-evidence block

**Files:**
- Modify: `viewer/components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard.tsx:349-350`
- Test: create `viewer/tests/surface_evidence_card_chip_jump.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `viewer/tests/surface_evidence_card_chip_jump.test.tsx`:

```tsx
/*
 * Render test for the Contradicting-evidence chip-jump destination on
 * the Evidence tab.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/surface_evidence_card_chip_jump.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SurfaceEvidenceCard } from "../components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function render(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(SurfaceEvidenceCard, { rec, n: 1 }));
}

test("Contradicting-evidence block carries chip-jump id + tabIndex when present", () => {
  const rec = baseRecord();
  rec.surface_evidence.contradicting_evidence = [
    {
      severity_for_surface_accessibility: "moderate",
      claim: "Cytoplasmic staining reported in HeLa.",
      cited_evidence_ids: ["a1_evi_09"],
    },
  ];
  const html = render(rec);
  assert.match(
    html,
    /id="chip-jump-contradicting-evidence"/,
    "block must expose contradictingEvidence id when list is non-empty",
  );
  assert.match(
    html,
    /id="chip-jump-contradicting-evidence"[^>]*tabindex="-1"/,
    "destination block must be programmatically focusable",
  );
});

test("Contradicting-evidence block omitted (with its id) when list is empty", () => {
  const rec = baseRecord();
  rec.surface_evidence.contradicting_evidence = [];
  const html = render(rec);
  assert.equal(
    /id="chip-jump-contradicting-evidence"/.test(html),
    false,
    "no id when the block itself isn't rendered",
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/surface_evidence_card_chip_jump.test.tsx`

Expected: FAIL — no id today.

- [ ] **Step 3: Modify `SurfaceEvidenceCard`**

Open `viewer/components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard.tsx`. Add the import near the top:

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
```

Around line 349, replace:

```tsx
        <div className={styles.subsection}>
          <p className={`label-mono ${styles.subhead}`}>Contradicting evidence</p>
```

with:

```tsx
        <div
          id={chipJumpTargets.contradictingEvidence}
          tabIndex={-1}
          className={styles.subsection}
        >
          <p className={`label-mono ${styles.subhead}`}>Contradicting evidence</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/surface_evidence_card_chip_jump.test.tsx`

Expected: PASS (2/2 tests).

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard.tsx viewer/tests/surface_evidence_card_chip_jump.test.tsx
git commit -m "feat(viewer): id + tabIndex on Contradicting evidence block for chip jumps"
```

---

## Task 8: Destination id on first row per modulation category

**Files:**
- Modify: `viewer/components/surfaceome/BiologicalContextCard/AccessibilityModulationTable.tsx:172-196`
- Test: extend `viewer/tests/biological_context_card_sort.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `viewer/tests/biological_context_card_sort.test.tsx` (open the file first to keep existing imports intact — the fixtures import from `./helpers/fixtures` and the card is `BiologicalContextCard`):

```tsx
test("first row per modulation category gets chip-jump id; duplicates do not", () => {
  const rec = baseRecord();
  rec.biological_context.accessibility_modulation = [
    {
      category: "cell_state_induced",
      direction: "increases",
      baseline_context: "resting T cell",
      modulating_state: "activated",
      change: "5-fold increase",
      accessibility_implication: "reachable on activation",
      cited_evidence_ids: ["a1_evi_01"],
    },
    {
      category: "cell_state_induced",
      direction: "increases",
      baseline_context: "naive B cell",
      modulating_state: "GC B cell",
      change: "3-fold increase",
      accessibility_implication: "reachable in germinal center",
      cited_evidence_ids: ["a1_evi_02"],
    },
    {
      category: "hypoxia_induced",
      direction: "increases",
      baseline_context: "normoxia",
      modulating_state: "hypoxia",
      change: "shifted to surface",
      accessibility_implication: "hypoxic-niche accessible",
      cited_evidence_ids: ["a1_evi_03"],
    },
  ];
  const html = render(rec);
  // First cell_state_induced row wins the id; second must not have it.
  const cellStateMatches = html.match(/id="chip-jump-modulation-cell_state_induced"/g) ?? [];
  assert.equal(
    cellStateMatches.length,
    1,
    "only the first cell_state_induced row should carry the id",
  );
  assert.match(
    html,
    /id="chip-jump-modulation-hypoxia_induced"/,
    "distinct category gets its own id",
  );
  // Every id-bearing row must be programmatically focusable.
  assert.match(
    html,
    /id="chip-jump-modulation-cell_state_induced"[^>]*tabindex="-1"/,
    "id-bearing modulation row must be tabIndex=-1",
  );
});
```

(If `biological_context_card_sort.test.tsx` doesn't already define a `render` helper for `BiologicalContextCard`, mirror the one from `biological_context_card_rationale.test.tsx`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_sort.test.tsx`

Expected: FAIL — no `chip-jump-modulation-*` ids today.

- [ ] **Step 3: Modify `AccessibilityModulationTable`**

Open `viewer/components/surfaceome/BiologicalContextCard/AccessibilityModulationTable.tsx`. Near the other imports at the top:

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
```

Just before the `<tbody>` (around line 172), compute the first-per-category set from the currently-sorted array:

```tsx
        <tbody>
          {(() => {
            const firstIdxForCategory = new Map<string, number>();
            sorted.forEach((m, i) => {
              if (m.category && !firstIdxForCategory.has(m.category)) {
                firstIdxForCategory.set(m.category, i);
              }
            });
            return sorted.map((m, i) => {
              const isFirstForCategory =
                m.category != null && firstIdxForCategory.get(m.category) === i;
              return (
                <tr
                  key={i}
                  id={
                    isFirstForCategory
                      ? chipJumpTargets.modulationCategory(m.category as string)
                      : undefined
                  }
                  tabIndex={isFirstForCategory ? -1 : undefined}
                >
                  <td>
                    <StatusPill tone="lavender" size="sm">
                      {prettyEnum(m.category)}
                    </StatusPill>
                  </td>
                  <td>{directionCell(m.direction)}</td>
                  <td>{m.baseline_context}</td>
                  <td>{m.modulating_state}</td>
                  <td>{m.accessibility_implication}</td>
                  <td>
                    {m.change ? (
                      <p className={styles.modChangeCite}>{m.change}</p>
                    ) : null}
                    <EvidenceChipList ids={m.cited_evidence_ids} label="References" />
                  </td>
                </tr>
              );
            });
          })()}
        </tbody>
```

Replace the existing `{sorted.map((m, i) => ( <tr key={i}> ... </tr> ))}` block with the above.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/biological_context_card_sort.test.tsx`

Expected: PASS on all tests including the new one.

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/BiologicalContextCard/AccessibilityModulationTable.tsx viewer/tests/biological_context_card_sort.test.tsx
git commit -m "feat(viewer): id on first row per modulation category for chip jumps"
```

---

## Task 9: Wrap composed chips in `FiltersCard`

**Files:**
- Modify: `viewer/components/surfaceome/FiltersCard/FiltersCard.tsx:414-461` (Accessibility-context group)
- Test: extend `viewer/tests/filters_card_chip_jump.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `viewer/tests/filters_card_chip_jump.test.tsx`:

```tsx
import { FiltersCard } from "../components/surfaceome/FiltersCard/FiltersCard";

function renderFiltersCard(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(FiltersCard, { rec, n: 1 }));
}

test("primary chip is wrapped in a ChipJumpButton to the compartment block", () => {
  const rec = baseRecord();
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<button[^>]*data-chip-jump-target="chip-jump-primary-compartment"[^>]*data-chip-jump-tab="biology"/,
    "primary chip must jump to the Biology tab compartment block",
  );
});

test("contradiction chip stays static when severity is none", () => {
  const rec = baseRecord();
  rec.surface_evidence.contradicting_evidence = [];
  const html = renderFiltersCard(rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-contradicting-evidence"/.test(html),
    false,
    'contradiction === "none" must not be clickable — no destination content',
  );
});

test("contradiction chip is wrapped when severity is present", () => {
  const rec = baseRecord();
  rec.surface_evidence.contradicting_evidence = [
    {
      severity_for_surface_accessibility: "moderate",
      claim: "Cytoplasmic staining reported.",
      cited_evidence_ids: [],
    },
  ];
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<button[^>]*data-chip-jump-target="chip-jump-contradicting-evidence"[^>]*data-chip-jump-tab="evidence"/,
    "contradiction chip must jump to the Evidence tab block",
  );
});

test("modulation category chip is wrapped and targets its row", () => {
  const rec = baseRecord();
  rec.biological_context.accessibility_modulation = [
    {
      category: "cell_state_induced",
      direction: "increases",
      baseline_context: "resting",
      modulating_state: "activated",
      change: "5x",
      accessibility_implication: "up",
      cited_evidence_ids: [],
    },
  ];
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<button[^>]*data-chip-jump-target="chip-jump-modulation-cell_state_induced"[^>]*data-chip-jump-tab="biology"/,
    "modulation category chip must jump to its row on the Biology tab",
  );
});

test("reason chip stays static (no clean destination)", () => {
  const rec = baseRecord();
  rec.executive_summary.surface_call_reason = "classical_surface_receptor";
  const html = renderFiltersCard(rec);
  // The reason value renders inside a StatusPill; the surrounding pill
  // must not be a ChipJumpButton — assert no button carries a chip-jump
  // target for "reason" (no such target id exists in chipJumpTargets).
  assert.equal(
    /aria-label="Jump to reason:/.test(html),
    false,
    "reason chip must remain a plain StatusPill",
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/filters_card_chip_jump.test.tsx`

Expected: FAIL — the composed chips are still plain `<StatusPill>`s.

- [ ] **Step 3: Wrap composed chips in `FiltersCard`**

Open `viewer/components/surfaceome/FiltersCard/FiltersCard.tsx`. Add the imports near the top with the other component imports:

```tsx
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
import { ChipJumpButton } from "../_shared/ChipJumpButton/ChipJumpButton";
```

Around line 414, the "Accessibility context" group pills array currently contains three composed chips: `primary`, `contradiction`, and the spread `modCategories.map(...)`. Rewrite the `pills:` array to wrap each in a `<ChipJumpButton>` (leaving the `key`-prop shape unchanged so React reconciliation stays stable):

```tsx
      pills: [
        <ChipJumpButton
          key="primary"
          targetId={chipJumpTargets.primaryCompartment}
          tabId="biology"
          ariaLabel={`Jump to Subcellular localization (primary: ${prettyEnum(
            rec.biological_context.subcellular_localization.primary_compartment,
          )})`}
        >
          <StatusPill tone="teal" size="sm">
            <ChipLabelValue
              label="primary"
              value={prettyEnum(
                rec.biological_context.subcellular_localization
                  .primary_compartment,
              )}
            />
          </StatusPill>
        </ChipJumpButton>,
        (() => {
          const pill = (
            <StatusPill
              tone={contradictionTone(maxContradictionSeverity)}
              size="sm"
              title={
                "Highest severity of contradicting evidence against the surface " +
                "call (from §02 Surface evidence → Contradicting evidence). " +
                "none = no contradictions in the ledger; low / moderate / high = " +
                "the strongest contradiction's impact on the surface-accessibility " +
                "call; unclear = logged but impact not gradable."
              }
            >
              <ChipLabelValue
                label="contradiction"
                value={
                  maxContradictionSeverity === "none"
                    ? "none"
                    : prettyEnum(maxContradictionSeverity)
                }
              />
            </StatusPill>
          );
          if (maxContradictionSeverity === "none") {
            // Nothing to jump to — leave as a static pill.
            return <React.Fragment key="contradiction">{pill}</React.Fragment>;
          }
          return (
            <ChipJumpButton
              key="contradiction"
              targetId={chipJumpTargets.contradictingEvidence}
              tabId="evidence"
              ariaLabel={`Jump to Contradicting evidence (${prettyEnum(
                maxContradictionSeverity,
              )})`}
            >
              {pill}
            </ChipJumpButton>
          );
        })(),
        ...modCategories.map((c) => (
          <ChipJumpButton
            key={`mod-${c}`}
            targetId={chipJumpTargets.modulationCategory(c)}
            tabId="biology"
            ariaLabel={`Jump to Accessibility modulation: ${prettyEnum(c)}`}
          >
            <StatusPill tone="lavender" size="sm">
              {prettyEnum(c)}
            </StatusPill>
          </ChipJumpButton>
        )),
      ],
```

If `React` isn't already imported at the top of `FiltersCard.tsx` (it usually is via JSX transform, but the `React.Fragment` above is explicit), add:

```tsx
import * as React from "react";
```

only if the type-check step in Task 10 flags it missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && npx --yes tsx --import ./tests/helpers/register.mjs --test tests/filters_card_chip_jump.test.tsx`

Expected: PASS (all tests including the five new ones).

- [ ] **Step 5: Commit**

```bash
git add viewer/components/surfaceome/FiltersCard/FiltersCard.tsx viewer/tests/filters_card_chip_jump.test.tsx
git commit -m "feat(viewer): wrap primary / contradiction / modulation chips in ChipJumpButton"
```

---

## Task 10: Wire tests into runner + full verification

**Files:**
- Modify: `viewer/tests/run_render_tests.sh`

- [ ] **Step 1: Append new test files to the runner**

Open `viewer/tests/run_render_tests.sh`. Extend the `tests=(` array to include the three new files added in this plan:

```bash
tests=(
  biological_context_card_rationale.test.tsx
  accessibility_risks_card_rationale.test.tsx
  biological_context_card_sort.test.tsx
  chip_jump_button.test.tsx
  filters_card_chip_jump.test.tsx
  surface_evidence_card_chip_jump.test.tsx
)
```

The unit-style `chip_jump_targets.test.ts` file is a plain `.ts` unit test (no CSS-module resolution needed); it can run independently. Add a parallel `unit_tests=(` block if the script has one; otherwise leave it as a standalone invocation the developer runs by hand.

- [ ] **Step 2: Run every test in this plan's scope**

Run:

```bash
cd viewer && bash tests/run_render_tests.sh && \
  npx --yes tsx --import ./tests/helpers/register.mjs --test tests/chip_jump_targets.test.ts
```

Expected output: all render tests pass; the unit test reports 5/5 pass.

- [ ] **Step 3: TypeScript type-check**

Run: `cd viewer && npx --yes tsc --noEmit`

Expected: 0 errors. If `FiltersCard.tsx` complains about `React.Fragment`, add the explicit `import * as React from "react";` at the top per Task 9 step 3's note.

- [ ] **Step 4: Next build smoke-check**

Run: `cd viewer && npm run build`

Expected: build succeeds. Look specifically for warnings about missing `id` targets or unused imports.

- [ ] **Step 5: Manual QA checklist (dev server)**

Run: `cd viewer && npm run dev`

Then in the browser at `http://localhost:3000/EGFR` (or any gene with rich data):

1. Scroll to §01 Summary metrics.
2. Click the **Known ligand** chip (Biology row). Expected: page switches to Biology tab; scrolls to the ligand rationale row; row briefly flashes background color.
3. Click the **primary** chip (Accessibility context row). Expected: Biology tab; scrolls to "Subcellular localization" block; brief flash.
4. Click a **modulation-category** chip (if any render for the gene). Expected: Biology tab; scrolls to the matching row in the modulation table; brief flash.
5. Click the **contradiction** chip on a gene with severity ≠ none (e.g., a gene with a contradictions block). Expected: Evidence tab; scrolls to Contradicting evidence; brief flash.
6. Confirm the **reason** chip renders but is NOT clickable (no cursor change on hover).
7. Confirm chips with no rationale (e.g. an old record showing "No rationale recorded" on the tab) render as static pills without hover lift.
8. Press Tab through the chip strip. Rationale-bearing chips should be focusable; static ones should not. Pressing Enter/Space on a focused chip should behave identically to a mouse click.
9. Refresh the page after clicking a chip. Expected: the URL hash reflects the destination tab (via `replaceState`) and the page reopens on that tab.
10. Click back-button after a chain of chip clicks. Expected: back navigates to the referrer, not through each chip click (thanks to `replaceState`).

- [ ] **Step 6: Commit**

```bash
git add viewer/tests/run_render_tests.sh
git commit -m "test(viewer): wire chip-jump tests into run_render_tests.sh"
```

---

## Self-Review

Coverage check against the spec:

- Spec: "Clickable ⟺ more info exists to jump to" → Task 5 gates on `nz(m.rationale)`; Task 9 gates `contradiction` on severity ≠ `none`; `reason` chip stays static (Task 9 test asserts this).
- Spec: FeatureRationales row destinations → Tasks 1, 4, 5.
- Spec: `primary` → compartment block → Tasks 1, 6, 9.
- Spec: `contradiction` → contradicting-evidence block → Tasks 1, 7, 9.
- Spec: Modulation category → first row per category → Tasks 1, 8, 9.
- Spec: `<ChipJumpButton>` semantics (button, aria, replaceState + hashchange, RAF, scrollIntoView, flash, focus) → Task 3.
- Spec: `.chip-jump-flash` shared class → Task 2, used by Task 3.
- Spec: `viewer/lib/chipJumpTargets.ts` central id map → Task 1.
- Spec: No back-stack pollution (`replaceState`) → Task 3 step 4.
- Spec: Accessibility (real button, aria-label, tabIndex=-1 on destinations, focus-move) → Tasks 3, 4, 6, 7, 8.
- Spec: `SectionTabs` / `AnchorNav` / `ReasoningDrawer` / record schema untouched → confirmed by not appearing in any Modify list.

Placeholder scan: no TBDs, no "add error handling", no "similar to Task N", no unresolved types.

Type consistency: `chipJumpTargets` shape is defined once (Task 1) and consumed identically in Tasks 4, 5, 6, 7, 8, 9. `ChipJumpButton`'s prop names (`targetId`, `tabId`, `ariaLabel`, `children`) are used verbatim by every caller.
