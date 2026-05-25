"use client";

import { useEffect, useRef, useState } from "react";
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
}

/**
 * AnchorNav — sticky numbered scroll-spy strip rendered just below the
 * topbar on the gene page. Each link shows a small mono "0n" number and
 * the section label; the link nearest to the top of the viewport gets
 * the `.is-active` pill style.
 *
 * Scroll-spy uses IntersectionObserver with a top-rootMargin tuned so
 * the section becomes active when its top edge crosses ~28% of the
 * viewport. That works well for both short and long sections without
 * a custom debounce loop.
 */
export function AnchorNav({ sections }: AnchorNavProps) {
  const [active, setActive] = useState<string | null>(
    sections[0]?.id ?? null,
  );
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (sections.length === 0) return;

    // Track all currently-intersecting section ids; pick the one
    // closest to the top of the viewport as the active link.
    const intersecting = new Map<string, number>();

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.id.replace(/^section-/, "");
          if (entry.isIntersecting) {
            intersecting.set(id, entry.boundingClientRect.top);
          } else {
            intersecting.delete(id);
          }
        }
        if (intersecting.size === 0) return;
        // Smallest |top| wins — section whose top is closest to the
        // scroll-spy line. Negative tops (scrolled past) sort below
        // positive ones, which matches reader intent: once you've
        // scrolled past a section it stops being "current".
        let best: { id: string; top: number } | null = null;
        for (const [id, top] of intersecting) {
          if (best === null || Math.abs(top) < Math.abs(best.top)) {
            best = { id, top };
          }
        }
        if (best) setActive(best.id);
      },
      {
        // Active band: 28% from the top down to the bottom. Anything
        // above that band has been scrolled past; anything below
        // hasn't been reached.
        rootMargin: "-28% 0px -55% 0px",
        threshold: [0, 0.25, 0.5, 0.75, 1],
      },
    );
    observerRef.current = observer;

    for (const s of sections) {
      const el = document.getElementById(`section-${s.id}`);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sections]);

  if (sections.length === 0) return null;

  return (
    <nav className={styles.nav} aria-label="Section anchors">
      <div className={styles.inner}>
        {sections.map((s, i) => {
          const isActive = s.id === active;
          return (
            <a
              key={s.id}
              href={`#section-${s.id}`}
              className={`${styles.link} ${isActive ? styles.linkActive : ""}`}
              aria-current={isActive ? "true" : undefined}
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
