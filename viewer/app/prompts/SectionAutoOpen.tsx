"use client";

import { useEffect } from "react";

/**
 * Opens + scrolls the collapsed `<details>` section a TOC link points at.
 *
 * The /prompts page renders each top-level prompt section as a
 * `<details data-section-anchor="…">` collapsed by default, so the page
 * opens as a compact list of section headings. The flat side TOC links to
 * `#<sectionId>`. Native `<details>` does NOT open when its id (or a child's
 * id) becomes the `:target`, so this single document-level listener bridges
 * that gap: on load-with-hash and on every in-page hash change, it finds the
 * targeted element, opens the enclosing `<details>`, and scrolls it into
 * view.
 *
 * One listener for the whole page (mounted once at the page root), so it's
 * cheap regardless of how many sections render — same delegation philosophy
 * as the EvidenceClickDelegator.
 */
export function SectionAutoOpen() {
  useEffect(() => {
    function openTarget(hash: string) {
      if (!hash || hash.length < 2) return;
      let el: Element | null = null;
      try {
        el = document.getElementById(decodeURIComponent(hash.slice(1)));
      } catch {
        el = document.getElementById(hash.slice(1));
      }
      if (!el) return;
      const details = el.closest("details");
      if (details && !(details as HTMLDetailsElement).open) {
        (details as HTMLDetailsElement).open = true;
      }
      // Defer the scroll one frame so it lands after the <details> expands
      // (its height changes when opened, which would otherwise offset the
      // scroll target).
      requestAnimationFrame(() => {
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    // Intercept same-page anchor clicks so re-clicking the SAME section link
    // still re-opens + re-scrolls (hashchange doesn't fire when the hash is
    // unchanged).
    function onClick(e: MouseEvent) {
      const a = (e.target as Element | null)?.closest?.(
        'a[href*="#"]',
      ) as HTMLAnchorElement | null;
      if (!a) return;
      const url = new URL(a.href, window.location.href);
      if (url.pathname !== window.location.pathname || !url.hash) return;
      openTarget(url.hash);
    }

    function onHashChange() {
      openTarget(window.location.hash);
    }

    document.addEventListener("click", onClick);
    window.addEventListener("hashchange", onHashChange);
    // Open the section if the page loaded with a hash already set.
    if (window.location.hash) openTarget(window.location.hash);

    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);

  return null;
}
