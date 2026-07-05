# Clickable §01 Summary metrics chips — jump to matching rationale

**Date:** 2026-07-01
**Scope:** Viewer, `viewer/components/surfaceome/FiltersCard` +
`viewer/components/surfaceome/FeatureChips`.

## Problem

The gene page's §01 "Summary metrics" panel (`FiltersCard`) renders
compact LLM-driven chips grouped into Biology / Accessibility context /
Expression / Risks. Each chip's supporting rationale — the "why this
value?" prose the synthesizer emitted — already exists on the page but
lives on a *different* tab (Biology / Expression / Risks) via
`<FeatureRationales>`, or inside a detail block on those tabs (the
subcellular-localization block, the contradicting-evidence list, the
accessibility-modulation table).

A reader who sees an interesting chip in §01 has no shortcut. They have
to know that (a) a rationale exists somewhere, (b) which tab hosts it,
and (c) scroll to find it. That's several ratchets of friction between
"I see a signal I want to understand" and "I'm reading the answer."

## Goal

Make each §01 chip that has more information available act as a
one-click shortcut to that information: switch to the matching tab and
scroll to the specific row / block, with a brief highlight so the
reader's eye lands on the right entry.

Non-goals:

- No new drawer, popover, or inline reveal — the destination content
  already exists on tabs; we're a navigation surface, not a duplicator.
- No changes to what the chip itself displays.
- No changes to the record schema; the fields we need
  (`filters.*_rationale`, `filters.*_cited_evidence_ids`,
  `biological_context.accessibility_modulation`,
  `surface_evidence.contradicting_evidence`,
  `subcellular_localization.primary_compartment`) already exist.
- Not touching the deterministic chips (topology / orthologs / family /
  candidate sites / …). Separate design conversation.
- Not touching the `GeneHeader` vitals (`ReasoningDrawer` chips for
  Confidence / Experimental evidence / State dependence). Those already
  have their own "click for reasoning" surface.

## Rule

**A chip is clickable if and only if more information exists to jump
to.** No-op clicks are worse than a static chip: they teach the reader
that the chip is *sometimes* meaningful, which erodes the affordance
everywhere.

## Scope — which chips become clickable

### Chips from `buildFeatureChips` (Biology / Expression / Risks)

`buildFeatureChips(category, rec)` returns a `FeatureChipModel[]` where
each entry has `key`, `label`, `pill`, `rationale`, `citedEvidenceIds?`.

- **Clickable when** `nz(m.rationale) !== null` (the existing `nz()`
  helper in `FeatureChips.tsx` normalizes empty / `"None"` to `null`).
  Jumps to the matching row in `<FeatureRationales>` on the category's
  tab.
- **Static when** `nz(m.rationale) === null`. Legacy pre-rationale
  records show "No rationale recorded" on the tab — there's nothing to
  see, so no shortcut.

Chip destinations, keyed on `m.key`:

| Row | Chip `m.key` values | Destination tab |
|---|---|---|
| Biology | `ligand`, `spec`, `co-receptor`, `restricted`, `orphan`, `homo-oligomer` | Biology tab, `<FeatureRationales category="biology">` |
| Expression | `expression-level`, `expression-breadth`, `oe-observed`, `low-endog` | Expression tab, `<FeatureRationales category="expression">` |
| Risks | `shed`, `secreted`, `epitope-masked`, `isoform-decoy`, `no-ecd` | Risks tab, `<FeatureRationales category="risks">` |

(Chip keys are illustrative; the source of truth is the `buildFeatureChips` return.)

### Composed non-model chips (`FiltersCard.tsx` directly)

Three of the four composed chips in the Biology + Accessibility-context
rows have a real destination block on an existing tab:

| Chip | Row (§01) | Value source | Destination |
|---|---|---|---|
| `primary` | Accessibility context | `subcellular_localization.primary_compartment` | Biology tab, subcellular-localization block in `BiologicalContextCard` |
| `contradiction` | Accessibility context | max severity of `surface_evidence.contradicting_evidence` | Evidence tab, "Contradicting evidence" list in `SurfaceEvidenceCard` |
| Modulation category (`{category}`) | Accessibility context | distinct categories from `biological_context.accessibility_modulation` | Biology tab, matching row(s) in `AccessibilityModulationTable` (in `BiologicalContextCard`) |

Rules:

- `primary` — always clickable when the chip renders (the compartment
  block always exists when the record has a primary compartment).
- `contradiction` — clickable **only when severity ≠ `none`**. When the
  ledger has no contradictions there's nothing on the Evidence tab to
  jump to.
- Modulation-category chips — clickable when the destination row for
  that category exists in the modulation table. This is guaranteed by
  the same source-of-truth data (`accessibility_modulation`); a chip
  only renders because a row exists.

### Stays static

- **`reason` chip** (Biology row, `surface_call_reason`) — no
  dedicated per-value block on any tab. The value is shown as prose in
  the exec-summary lede on the top-of-page `GeneHeader`, which is
  always visible; jumping there is redundant. Leave as a plain
  `<StatusPill>`.
- **All deterministic chips** — out of scope for this design.

## Behavior

Click, keyboard-activate (Enter / Space), or touch on a clickable chip:

1. **If the destination tab isn't currently active:** update the URL
   hash via `history.replaceState({}, "", "#section-" + tabId)`, then
   manually `window.dispatchEvent(new HashChangeEvent("hashchange"))`.
   `SectionTabs`'s existing `hashchange` listener swaps the active
   section; `AnchorNav` updates in step. `replaceState` (not
   `pushState`, not raw `location.hash = ...`) avoids polluting the
   back-button stack with an entry per chip click, while still letting
   share/refresh restore the reader's current tab.
   If the destination tab IS already active, skip this step entirely —
   no hash change, no `hashchange` event.
2. **In the next `requestAnimationFrame`:** find the destination
   element by id. Call
   `el.scrollIntoView({ behavior: "smooth", block: "start" })`, then
   apply the `.chipJumpFlash` class (see Styling) and remove it ~1.2s
   later. The RAF gap gives `SectionTabs` a chance to toggle
   `data-active` so the destination is measurable when we scroll.
3. **Move keyboard focus to the destination:** the destination element
   has `tabIndex={-1}` and receives `.focus({ preventScroll: true })`
   so a keyboard-only user's focus follows the visual jump.

## Destination ids

Stable ids assigned at the destination — the source of truth is a
constant map, `viewer/lib/chipJumpTargets.ts`:

```ts
// One export per destination family.
export const chipJumpTargets = {
  featureRationale: (category, key) => `chip-jump-${category}-${key}`,
  primaryCompartment: "chip-jump-primary-compartment",
  contradictingEvidence: "chip-jump-contradicting-evidence",
  modulationCategory: (category) => `chip-jump-modulation-${category}`,
} as const;
```

Producers and consumers both import from this file, so the id string is
never hard-coded in two places.

Producers (add `id` + `tabIndex={-1}`):

- `<FeatureRationales>` — each `<div className={styles.rationaleRow}>`
  gets `id={chipJumpTargets.featureRationale(category, m.key)}`.
- `BiologicalContextCard` — subcellular-localization block gets
  `id={chipJumpTargets.primaryCompartment}`.
- `SurfaceEvidenceCard` — contradicting-evidence list container gets
  `id={chipJumpTargets.contradictingEvidence}`.
- `AccessibilityModulationTable` — each observation row gets
  `id={chipJumpTargets.modulationCategory(row.category)}`. If multiple
  observations share a category, the FIRST row wins; the reader lands
  on the top of that category's group.

Consumers (import + wrap chips):

- `FeatureChips.tsx` `<FeatureChips>` — wraps each chip whose model has
  a rationale in a `<ChipJumpButton>` targeting
  `chipJumpTargets.featureRationale(category, m.key)`.
- `FiltersCard.tsx` — wraps the `primary`, `contradiction` (when
  applicable), and modulation-category chips in `<ChipJumpButton>`
  targeting the corresponding constants.

## New component — `<ChipJumpButton>`

`viewer/components/surfaceome/_shared/ChipJumpButton.tsx`:

```tsx
interface ChipJumpButtonProps {
  /** DOM id of the destination element. */
  targetId: string;
  /** SectionTabs section id whose hash we set — e.g. "biology". */
  tabId: string;
  /** aria-label text describing where the reader is jumping to. */
  ariaLabel: string;
  /** The chip content — typically a <StatusPill>. */
  children: ReactNode;
}
```

Implementation:

- Renders a `<button type="button" className={styles.jumpTrigger}>`
  wrapping `children`.
- On click: read the current hash. If it doesn't already point to the
  destination tab, set `window.location.hash = "#section-" + tabId`.
  In a `requestAnimationFrame`, look up `document.getElementById(targetId)`
  and — when found — `scrollIntoView`, toggle the flash class, and move
  focus.
- Missing destination is a no-op with a `console.warn` in dev builds so
  drift between chip and destination fails loudly during development
  but silently in production.
- `aria-label={ariaLabel}`, focus ring via existing `--focus-ring`
  token, `cursor: pointer`, subtle hover lift (borrowed from the
  `ReasoningDrawer.trigger` styling grammar so "click for more" reads
  consistently across the page).

## Styling

- `.jumpTrigger` — resets default button styling, transparent
  background, no border; inherits the pill's own dimensions. Hover
  applies a subtle `translateY(-1px)` + `box-shadow` lift and slight
  opacity bump; focus applies the standard focus ring.
- `.chipJumpFlash` — one shared utility class (declared in
  `viewer/app/globals.css` so both rationale rows and detail-block
  containers can pick it up). One `@keyframes` fades a
  `background-color` from `var(--accent-soft)` (a semi-transparent
  brand color, safe on both the page and the block backgrounds) to
  transparent over 1.2s. No transform (would shift the reader's scroll
  position mid-animation).
- Static chips keep today's flat appearance — cursor: default, no
  hover state.

## Accessibility

- Real `<button>` (not `<a>`); Enter / Space activate.
- `aria-label` on each button explains the jump, e.g. `"Jump to
  rationale: Known ligand"` or `"Jump to Contradicting evidence"`.
- Destination element gets `tabIndex={-1}` and receives programmatic
  focus so keyboard-only readers land at the destination — otherwise
  the visual jump would leave focus on the trigger up in §01.
- Flash animation uses `background-color` only — no motion; respects
  `prefers-reduced-motion` implicitly.

## Testing

- **`viewer/tests/verify_feature_tabs.py`** — extended to assert every
  chip whose model has a rationale is a `<button>` and every rationale
  row on the tab has the expected `id={chipJumpTargets.featureRationale(...)}`.
- **RTL** (`FeatureChips.test.tsx` / new
  `FiltersCard.chipJump.test.tsx`):
  - Chip with rationale renders as `<button>`; chip without rationale
    renders as `<span>`.
  - Clicking a Biology chip sets `location.hash = "#section-biology"`
    (mocked) and calls `scrollIntoView` on the expected id (jsdom
    `Element.prototype.scrollIntoView` mocked).
  - `contradiction === "none"` chip is a `<span>` (not clickable).
  - `contradiction === "moderate"` chip is a `<button>` targeting the
    Evidence tab's contradicting-evidence id.
  - Modulation-category chip targets the row id for its category.
- **Playwright (nice-to-have)** — click a chip on a known gene, assert
  the correct tab becomes visible and the destination row is in view.

## Non-goals restated

- No changes to `SectionTabs` / `AnchorNav` — they already listen for
  `hashchange`.
- No changes to `ReasoningDrawer` or the `GeneHeader` vitals.
- No new record fields, no server-side or D1 changes.
- No visual redesign of the chips themselves — the pill tone remains
  the tone contract.

## Risks and mitigations

- **Chip destination drift** — a chip key exists in `buildFeatureChips`
  but the corresponding rationale row doesn't render on the tab (or
  vice versa). Mitigation: the `data-feature-chips` /
  `data-feature-rationales` pairing test already guards this shape;
  extending it to assert `id` presence keeps CI honest.
- **Category modulation collisions** — two observations share a
  category, so two rows have the same id. Mitigation: only apply the
  id to the *first* row for that category; subsequent rows are
  reachable by continued scrolling. Jump lands the reader at the top
  of the category's group, which is what a "jump to modulation
  category X" would mean.
- **Reduced motion** — `scrollIntoView({ behavior: "smooth" })` is
  ignored by browsers when `prefers-reduced-motion: reduce` is set;
  the jump becomes instantaneous, which is the correct behavior.
- **Hash pollution in browser history** — mitigated by the
  `replaceState` + manual `hashchange` dispatch pattern in Behavior
  step 1. The URL still reflects the current tab (so refresh / share
  work), but a chain of chip clicks doesn't grow the back stack.
