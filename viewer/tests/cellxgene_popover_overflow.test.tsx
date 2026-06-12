/*
 * Tests for the CellxGene chart popover overflow clamp. The chart
 * renders a hover/focus popover above each bar; for bars near the
 * right or left edge of the viewport, a naive `transform:
 * translateX(-50%)` lets the popover spill off-screen. The user
 * caught this on the EGFR embryo bar — the popover ran past the
 * viewport edge and was unreadable.
 *
 * `computePopoverTransform` is the pure-logic function the runtime
 * uses to keep popovers inside `[edgeMargin, viewportWidth -
 * edgeMargin]`. These tests assert the branching directly without a
 * real browser — extracting the math out of the DOM wrapper means we
 * can confidently lock in the no-overflow contract.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       tests/cellxgene_popover_overflow.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  EDGE_MARGIN,
  computePopoverTransform,
} from "../components/surfaceome/CellxGeneCard/CellxGeneChart";

const VIEWPORT_WIDTH = 1280;

test("centered when popover fits within viewport with margin", () => {
  const rect = { left: 400, right: 720 };
  assert.equal(
    computePopoverTransform(rect, VIEWPORT_WIDTH),
    "translateX(-50%)",
  );
});

test("shifts LEFT when the popover overflows the right edge", () => {
  // Popover ends at 1290, viewport is 1280, so overflow = 1290 - (1280 - 8) = 18 px.
  const rect = { left: 970, right: 1290 };
  const t = computePopoverTransform(rect, VIEWPORT_WIDTH);
  assert.equal(t, "translateX(calc(-50% - 18px))");
});

test("shifts RIGHT when the popover overflows the left edge", () => {
  // Popover starts at 2, edge margin is 8, so underflow = 6 px.
  const rect = { left: 2, right: 322 };
  const t = computePopoverTransform(rect, VIEWPORT_WIDTH);
  assert.equal(t, "translateX(calc(-50% + 6px))");
});

test("respects exactly-touching the edge — no shift", () => {
  // Popover ends precisely at viewportWidth - edgeMargin, not over.
  const rect = { left: 952, right: VIEWPORT_WIDTH - EDGE_MARGIN };
  const t = computePopoverTransform(rect, VIEWPORT_WIDTH);
  assert.equal(t, "translateX(-50%)");
});

test("custom edgeMargin parameter is respected", () => {
  // With a 32-px margin, a popover ending at 1260 (within 1280-32=1248)
  // would overflow by 12.
  const rect = { left: 940, right: 1260 };
  const t = computePopoverTransform(rect, VIEWPORT_WIDTH, 32);
  assert.equal(t, "translateX(calc(-50% - 12px))");
});

test("the EGFR-embryo case — far-right bar, wide popover", () => {
  // Emulate the actual symptom the user reported: a 320-px popover
  // centered on a bar at x ≈ 1180 (near the right of a 1280-px
  // viewport) overflows by ~ (1180 + 160) - (1280 - 8) = 68 px.
  const barCenter = 1180;
  const popoverWidth = 320;
  const rect = {
    left: barCenter - popoverWidth / 2,
    right: barCenter + popoverWidth / 2,
  };
  const t = computePopoverTransform(rect, VIEWPORT_WIDTH);
  assert.equal(t, "translateX(calc(-50% - 68px))");
});

test("does not over-shift when the bar is exactly centered", () => {
  // The bar at the viewport center should produce no shift even if
  // the popover is wide.
  const rect = { left: 480, right: 800 };
  assert.equal(
    computePopoverTransform(rect, VIEWPORT_WIDTH),
    "translateX(-50%)",
  );
});
