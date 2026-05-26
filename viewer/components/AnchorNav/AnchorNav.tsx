"use client";

import styles from "./AnchorNav.module.css";

export interface AnchorSection {
  /** Anchor target — the section in the page is expected to carry
   *  `id={"section-" + id}` so the link's hash resolves. */
  id: string;
  /** Reader-facing label, e.g. "Surface evidence". */
  label: string;
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
  if (sections.length === 0) return null;

  return (
    <nav className={styles.nav} aria-label="Section tabs">
      <div className={styles.inner}>
        {sections.map((s, i) => {
          const isActive = s.id === active;
          return (
            <a
              key={s.id}
              href={`#section-${s.id}`}
              className={`${styles.link} ${isActive ? styles.linkActive : ""}`}
              aria-current={isActive ? "true" : undefined}
              onClick={(e) => {
                e.preventDefault();
                onSelect(s.id);
                // Update the URL hash without scrolling so a refresh
                // restores the same tab. `history.pushState` doesn't
                // trigger the browser's hash-scroll behavior.
                if (typeof window !== "undefined") {
                  window.history.pushState(null, "", `#section-${s.id}`);
                }
              }}
            >
              <span className={styles.num}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className={styles.label}>{s.label}</span>
            </a>
          );
        })}
      </div>
    </nav>
  );
}
