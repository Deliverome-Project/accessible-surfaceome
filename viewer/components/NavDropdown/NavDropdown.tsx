"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import styles from "./NavDropdown.module.css";

interface NavDropdownItem {
  label: string;
  /** Absolute href — these links exit the subdomain back to deliverome.org. */
  href: string;
}

interface NavDropdownProps {
  label: string;
  items: NavDropdownItem[];
  panelAlign?: "left" | "right";
}

const CLOSE_DELAY_MS = 140;

/**
 * NavDropdown — hover + keyboard-navigable menu for the parent-site strip.
 * Ported from deliverome-internal:site/components/nav-dropdown.tsx so the
 * subdomain header behaves identically to the main site's SiteShell when
 * users hover Platform/Company. Differences from the source:
 *
 *   - CSS module instead of global ``.nav-dropdown__*`` classes (the
 *     surfaceome viewer convention is one ``.module.css`` per component
 *     dir; the parent's globals.css isn't shared across subdomain).
 *   - Items use ``<a>`` (not ``<Link>``) because the targets are absolute
 *     URLs back to deliverome.org, not in-app routes.
 */
export function NavDropdown({ label, items, panelAlign = "left" }: NavDropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);

  function cancelClose() {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }

  function scheduleClose() {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  }

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => {
        const first = rootRef.current?.querySelector<HTMLAnchorElement>(
          `.${styles.panel} a`,
        );
        first?.focus();
      });
    }
  }

  useEffect(() => {
    return () => cancelClose();
  }, []);

  return (
    <div
      ref={rootRef}
      className={styles.root}
      data-panel-align={panelAlign}
      onMouseEnter={() => {
        cancelClose();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
      onFocus={() => {
        cancelClose();
        setOpen(true);
      }}
      onBlur={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget as Node)) {
          scheduleClose();
        }
      }}
    >
      <button
        type="button"
        className={styles.trigger}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        onKeyDown={handleTriggerKeyDown}
      >
        {label}
        <span className={styles.caret} aria-hidden="true">
          ▾
        </span>
      </button>
      <ul
        className={styles.panel}
        role="menu"
        data-open={open ? "true" : "false"}
      >
        {items.map((item) => (
          <li key={item.href} role="none">
            <a
              href={item.href}
              role="menuitem"
              className={styles.item}
              onClick={() => setOpen(false)}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
