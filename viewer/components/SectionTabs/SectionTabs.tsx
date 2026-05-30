"use client";

import { Children, isValidElement, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AnchorNav, type AnchorSection } from "../AnchorNav/AnchorNav";
import styles from "./SectionTabs.module.css";

interface SectionTabsProps {
  sections: AnchorSection[];
  /** Expects one child element per section, each carrying a
   *  ``data-section-id`` attribute matching the section's
   *  ``id``. Children are pre-rendered server-side; this component
   *  just toggles which one is visible. */
  children: ReactNode;
}

interface CommunityCountDetail {
  count: number;
}

/**
 * `<SectionTabs>` — replaces the previous scroll-through-everything
 * layout with a tab-style page where exactly one section is
 * displayed at a time and the AnchorNav drives the selection.
 *
 * Why this shape:
 *
 * * The reader sees the section they asked for, full-page, without
 *   the visual noise of every other section stacked underneath.
 * * Page scroll position doesn't jump when switching sections —
 *   clicking a tab just swaps the body, the header stays put.
 * * All section JSX is server-rendered up front (passed in as
 *   children), so the only client-side work is hiding/showing.
 *   Non-JS readers see whichever section was rendered with
 *   ``data-active="true"`` initially (defaults to ``sections[0]``).
 *
 * Deep-link compatibility: a URL like ``/EGFR#section-evidence``
 * opens the page with that section already selected. Clicking a
 * tab updates the URL hash via ``history.pushState`` so a refresh
 * restores the same tab, and browser back/forward also work.
 */
export function SectionTabs({ sections, children }: SectionTabsProps) {
  const initial = sections[0]?.id ?? "";
  const [active, setActive] = useState<string>(initial);

  // Community-notes count, dispatched by <CommunityNotesCard> after
  // it resolves its `/v1/feedback/public` fetch. We decorate the
  // matching tab with `(N)` + green accent so the reader notices new
  // community content without scrolling. `null` means "haven't heard
  // yet" — render the tab undecorated until we know.
  const [communityCount, setCommunityCount] = useState<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<CommunityCountDetail>).detail;
      if (detail && typeof detail.count === "number") {
        setCommunityCount(detail.count);
      }
    };
    window.addEventListener("surfaceome:community-notes-count", handler);
    return () => {
      window.removeEventListener(
        "surfaceome:community-notes-count",
        handler,
      );
    };
  }, []);

  // Merge the community count into the sections list passed to
  // <AnchorNav>. Keeps the AnchorNav generic — it just consumes
  // `count?: number` per section and decorates when >= 1.
  const decoratedSections = useMemo(
    () =>
      sections.map((s) =>
        s.id === "community" && communityCount !== null
          ? { ...s, count: communityCount }
          : s,
      ),
    [sections, communityCount],
  );

  // Restore the active tab from the URL hash on mount (so a deep
  // link like ``/EGFR#section-evidence`` works) and on
  // browser-history navigation (back / forward).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromHash = () => {
      const hash = window.location.hash.replace(/^#section-/, "");
      if (hash && sections.some((s) => s.id === hash)) setActive(hash);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    window.addEventListener("popstate", fromHash);
    return () => {
      window.removeEventListener("hashchange", fromHash);
      window.removeEventListener("popstate", fromHash);
    };
  }, [sections]);

  return (
    <>
      <AnchorNav
        sections={decoratedSections}
        active={active}
        onSelect={setActive}
      />
      <div className={styles.body}>
        {Children.map(children, (child) => {
          if (!isValidElement(child)) return child;
          const props = child.props as { "data-section-id"?: string };
          const id = props["data-section-id"];
          if (!id) return child;
          const isActive = id === active;
          return (
            <div
              className={styles.slot}
              data-active={isActive ? "true" : "false"}
              aria-hidden={!isActive}
            >
              {child}
            </div>
          );
        })}
      </div>
    </>
  );
}
