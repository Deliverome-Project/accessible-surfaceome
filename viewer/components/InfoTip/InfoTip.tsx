"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import styles from "./InfoTip.module.css";

interface InfoTipProps {
  /** Tooltip body. Plain text or small inline JSX (e.g. an `<a>` for
   *  a doi link). Renders inside an aria-described popover. */
  children: ReactNode;
  /** Glyph shown to the reader. Defaults to a small `ⓘ`. */
  glyph?: string;
  /** Aria-label for the trigger button. Defaults to "About this field". */
  label?: string;
  /** Additional class names for the trigger (e.g. for inline alignment
   *  inside a label-mono row). */
  triggerClassName?: string;
}

/**
 * InfoTip — small, accessible provenance popover.
 *
 * Behavior:
 * - Click / Enter / Space on the trigger toggles the popover.
 * - Hover opens it (mouse only); blur / mouseleave closes it.
 * - Escape closes it.
 * - Click outside closes it.
 *
 * Why a button trigger (not a hover-only span): keyboard users + touch
 * users need a click target. The trigger is a real <button> so Tab
 * reaches it and Enter/Space activates it.
 */
export function InfoTip({
  children,
  glyph = "ⓘ", // ⓘ
  label = "About this field",
  triggerClassName,
}: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const popoverId = useId();

  // Outside-click + Escape closes the popover.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      const t = e.target as Node | null;
      if (t === null) return;
      if (triggerRef.current?.contains(t)) return;
      if (popoverRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const onKeyDown = useCallback((e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen((v) => !v);
    }
  }, []);

  return (
    <span className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={`${styles.trigger} ${triggerClassName ?? ""}`.trim()}
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? popoverId : undefined}
        onClick={(e) => {
          // Stop the click bubbling so parent labels (often clickable for
          // sort / focus) don't react to the info-tip activation.
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onKeyDown={onKeyDown}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <span aria-hidden="true">{glyph}</span>
      </button>
      {open ? (
        <div
          ref={popoverRef}
          id={popoverId}
          role="tooltip"
          className={styles.popover}
          // Don't let the popover swallow the trigger's hover-out:
          // moving from trigger → popover bridges via a tiny gap that
          // we suppress with `pointer-events` so the mouse still
          // resolves to the trigger's mouseleave.
          onMouseEnter={() => setOpen(true)}
        >
          {children}
        </div>
      ) : null}
    </span>
  );
}
