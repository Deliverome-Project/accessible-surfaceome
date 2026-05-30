"use client";

import type { MouseEvent } from "react";
import styles from "./FeedbackButton.module.css";

interface FeedbackButtonProps {
  gene: string;
  uniprotAcc?: string | null;
  /** Optional className override so the button can sit inside the
   *  breadcrumb actions row and inherit the existing crumbAction
   *  styles (border-bottom underline + hover color). When provided,
   *  the local accent style is dropped. */
  variant?: "crumb" | "standalone";
}

/**
 * FeedbackButton — opens the global <FeedbackModal> via a CustomEvent.
 *
 * Why CustomEvent instead of prop-drilling: the modal lives at the page
 * root (next to <EvidenceDrawer>) so it persists across section scrolls
 * and is mounted exactly once. The button lives inside the breadcrumb
 * actions row. Passing open-state through props would require wiring a
 * provider through three component boundaries; an event is the standard
 * lightweight pattern already used by EvidenceChip → EvidenceDrawer in
 * this same codebase ("surfaceome:open-evidence").
 */
export function FeedbackButton({
  gene,
  uniprotAcc,
  variant = "crumb",
}: FeedbackButtonProps) {
  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    window.dispatchEvent(
      new CustomEvent("surfaceome:open-feedback", {
        detail: { gene, uniprotAcc: uniprotAcc ?? null },
      }),
    );
  };
  return (
    <button
      type="button"
      className={variant === "crumb" ? styles.crumb : styles.standalone}
      onClick={handleClick}
    >
      Submit feedback
    </button>
  );
}
