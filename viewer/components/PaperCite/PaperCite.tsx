"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./PaperCite.module.css";

/**
 * "Cite this paper" disclosure for the home-page paper card. A native
 * <details> so it opens without JS; the copy buttons are the only
 * client behaviour. Text mirrors `preferred-citation` in the repo's
 * CITATION.cff — keep the two in step.
 */
const FORMATS = {
  citation:
    "Carlson RJ, Hollingsworth LR, Smallegan MJ. The accessible human " +
    "surfaceome. bioRxiv (2026). doi:10.64898/2026.10.18.759859",
  bibtex: `@article{carlson2026surfaceome,
  title   = {The accessible human surfaceome},
  author  = {Carlson, Rebecca J. and Hollingsworth, L. Robert and Smallegan, Michael J.},
  journal = {bioRxiv},
  year    = {2026},
  doi     = {10.64898/2026.10.18.759859},
  url     = {https://doi.org/10.64898/2026.10.18.759859}
}`,
};

type Format = keyof typeof FORMATS;

/** Pre-Clipboard-API copy, for browsers that deny `writeText`. */
function copyViaTextarea(text: string): boolean {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  ta.remove();
  return ok;
}

export function PaperCite() {
  // Which format the box shows; a copy switches it to what was copied.
  const [shown, setShown] = useState<Format>("citation");
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const textRef = useRef<HTMLPreElement>(null);

  // When every copy route failed, select the text so the reader can
  // copy it by hand. Runs after render so the selection covers the
  // format just swapped in.
  useEffect(() => {
    if (status === "failed" && textRef.current) {
      window.getSelection()?.selectAllChildren(textRef.current);
    }
  }, [status, shown]);

  function copy(format: Format) {
    const text = FORMATS[format];
    setShown(format);
    const succeed = () => {
      setStatus("copied");
      setTimeout(() => setStatus("idle"), 1800);
    };
    const fallback = () =>
      copyViaTextarea(text) ? succeed() : setStatus("failed");
    if (!navigator.clipboard) return fallback();
    navigator.clipboard.writeText(text).then(succeed, fallback);
  }

  function label(format: Format, idle: string) {
    return status === "copied" && shown === format ? "Copied" : idle;
  }

  return (
    <details className={styles.cite}>
      <summary className={styles.summary}>Cite this paper</summary>
      <div className={styles.body}>
        <pre
          ref={textRef}
          className={
            shown === "bibtex"
              ? `${styles.citation} ${styles.bibtex}`
              : styles.citation
          }
        >
          {FORMATS[shown]}
        </pre>
        <div className={styles.buttons}>
          <button
            type="button"
            className={styles.copy}
            onClick={() => copy("citation")}
          >
            {label("citation", "Copy citation")}
          </button>
          <button
            type="button"
            className={styles.copy}
            onClick={() => copy("bibtex")}
          >
            {label("bibtex", "Copy BibTeX")}
          </button>
          <span role="status" aria-live="polite" className={styles.status}>
            {status === "copied" && "Copied to clipboard"}
            {status === "failed" &&
              "Couldn't copy automatically — the text is selected; press ⌘C or Ctrl+C."}
          </span>
        </div>
        <p className={styles.note}>
          Using the data or code? Cite their Zenodo DOIs too — versioned handles
          are on the{" "}
          <a href="/reproducibility/" className={styles.noteLink}>
            Reproducibility
          </a>{" "}
          page.
        </p>
      </div>
    </details>
  );
}
