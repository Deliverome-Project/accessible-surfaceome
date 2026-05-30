"use client";

import { useCallback, useRef, type KeyboardEvent } from "react";
import styles from "./AnchorNav.module.css";

export interface AnchorSection {
  /** Anchor target — the section in the page is expected to carry
   *  `id={"section-" + id}` so the link's hash resolves. */
  id: string;
  /** Reader-facing label, e.g. "Surface evidence". */
  label: string;
  /** Optional decoration count. When present, the tab label renders
   *  as `Label (N)` and (for N >= 1) the tab picks up the
   *  `linkAccent` style — a green left-border to draw attention.
   *  Used today for the Community-notes tab, where the count is
   *  fetched client-side and merged in by `<SectionTabs>`. */
  count?: number;
}

interface AnchorNavProps {
  sections: AnchorSection[];
  /** ID of the currently-displayed section. Driven by the parent
   *  `<SectionTabs>`. */
  active: string;
  /** Called when the user clicks a section tab. The parent updates
   *  the active id, which hides all other section slots via CSS. */
  onSelect: (id: string) => void;
}

/**
 * AnchorNav — sticky numbered TAB STRIP rendered just below the
 * topbar on the gene page. Was previously a scroll-spy with anchor
 * links; now it's the tab control that drives which section is
 * displayed (one at a time, no scrolling between sections).
 *
 * Stays a `<nav>` of `<a href="#section-...">` so deep links + the
 * native browser back/forward continue to work — the click handler
 * intercepts to update the active state without scrolling, but the
 * hash still updates so a refresh restores the same tab.
 */
export function AnchorNav({ sections, active, onSelect }: AnchorNavProps) {
  const linkRefs = useRef<Array<HTMLAnchorElement | null>>([]);

  // Keyboard navigation: ArrowLeft / ArrowRight cycle the focused tab
  // and select it inline (the tab list is also the section selector,
  // so moving focus and selecting are the same action — matches the
  // WAI-ARIA "Tabs with Automatic Activation" pattern). Home / End
  // jump to the first / last tab.
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLAnchorElement>, idx: number) => {
      const last = sections.length - 1;
      let next: number | null = null;
      if (e.key === "ArrowRight") next = idx === last ? 0 : idx + 1;
      else if (e.key === "ArrowLeft") next = idx === 0 ? last : idx - 1;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = last;
      if (next === null) return;
      e.preventDefault();
      const targetId = sections[next]?.id;
      if (targetId === undefined) return;
      onSelect(targetId);
      if (typeof window !== "undefined") {
        window.history.pushState(null, "", `#section-${targetId}`);
      }
      linkRefs.current[next]?.focus();
    },
    [sections, onSelect],
  );

  if (sections.length === 0) return null;

  return (
    <nav className={styles.nav} aria-label="Section tabs">
      <div className={styles.inner} role="tablist">
        {sections.map((s, i) => {
          const isActive = s.id === active;
          const hasNotes = typeof s.count === "number" && s.count >= 1;
          // tabindex policy: the active tab is the only one in the
          // tab sequence (tabIndex=0); the rest are reachable via
          // arrow keys (tabIndex=-1). Mirrors the WAI-ARIA tabs
          // pattern, keeps Tab/Shift+Tab moving in and out of the
          // tablist as a single stop.
          const tabIndex = isActive ? 0 : -1;
          return (
            <a
              key={s.id}
              ref={(el) => { linkRefs.current[i] = el; }}
              href={`#section-${s.id}`}
              role="tab"
              tabIndex={tabIndex}
              aria-selected={isActive ? "true" : "false"}
              aria-current={isActive ? "true" : undefined}
              className={[
                styles.link,
                isActive ? styles.linkActive : "",
                hasNotes ? styles.linkAccent : "",
              ].filter(Boolean).join(" ")}
              onClick={(e) => {
                e.preventDefault();
                onSelect(s.id);
                if (typeof window !== "undefined") {
                  window.history.pushState(null, "", `#section-${s.id}`);
                }
              }}
              onKeyDown={(e) => onKeyDown(e, i)}
            >
              <span className={styles.num}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className={styles.label}>
                {s.label}
                {typeof s.count === "number" && s.count >= 1 ? (
                  <span className={styles.count}> ({s.count})</span>
                ) : null}
              </span>
            </a>
          );
        })}
      </div>
    </nav>
  );
}
