"use client";

import { useEffect } from "react";

/**
 * EvidenceClickDelegator — page-level event delegator that lets
 * `<EvidenceChip>` stay a pure server component while still firing
 * the global `surfaceome:open-evidence` CustomEvent on click.
 *
 * Why delegate: a typical gene page renders 100+ EvidenceChips
 * (Surface evidence per-method strips + per-observation rows +
 * inline-linkified prose refs + contradictions + Evidence ledger).
 * Before delegation each chip was a `"use client"` boundary in
 * Next.js 16 RSC, so the page emitted ~100 separate hydration
 * islands — each with its own RSC stream chunk + hydration
 * metadata. The Surface evidence tab in particular got slow.
 *
 * After delegation: chips render as plain `<button data-evidence-id=
 * "...">` markup with no React handlers attached. This single
 * component mounts one `document.addEventListener("click", ...)`,
 * walks `closest("[data-evidence-id]")`, and dispatches the same
 * `surfaceome:open-evidence` CustomEvent that the EvidenceDrawer
 * already subscribes to. Net effect: ~100 hydration boundaries → 1.
 *
 * Mount once at the page level, alongside `<EvidenceDrawer>`. Order
 * doesn't matter — the delegator dispatches on `window`, the drawer
 * subscribes on `window`, they don't know about each other.
 */
export function EvidenceClickDelegator() {
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Element | null;
      if (!target || typeof target.closest !== "function") return;
      const chip = target.closest<HTMLElement>("[data-evidence-id]");
      if (!chip) return;
      const evidenceId = chip.dataset.evidenceId;
      if (!evidenceId) return;
      // Preempt the browser's default <button> behavior (none for
      // type="button", but defensive against future changes).
      e.preventDefault();
      window.dispatchEvent(
        new CustomEvent("surfaceome:open-evidence", {
          detail: { evidenceId },
        }),
      );
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  return null;
}
