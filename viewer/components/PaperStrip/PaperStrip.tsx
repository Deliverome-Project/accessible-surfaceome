"use client";

import { useEffect, useId, useRef, useState } from "react";
import styles from "./PaperStrip.module.css";

/**
 * Home-page strip linking the preprint, its code and its data, with a
 * "Cite" toggle at the end of the link row that opens a copyable
 * citation panel underneath. The HTML copy on the Deliverome site is
 * the primary link; bioRxiv is the version of record. Data is the
 * Zenodo concept DOI (all releases); /reproducibility lists the
 * per-version handles. Citation text mirrors `preferred-citation` in
 * the repo's CITATION.cff — keep the two in step.
 */
const PAPER_HTML_URL = "https://deliverome.org/paper/accessible-surfaceome/";

const PAPER_LINKS: { label: string; ariaLabel: string; href: string }[] = [
  {
    label: "PDF",
    ariaLabel: "Paper PDF",
    href: "https://deliverome.org/paper/accessible-surfaceome/accessible-human-surfaceome.pdf",
  },
  {
    label: "bioRxiv",
    ariaLabel: "Preprint on bioRxiv",
    href: "https://www.biorxiv.org/content/10.64898/2026.10.18.759859v1",
  },
  {
    label: "Code",
    ariaLabel: "Source code on GitHub",
    href: "https://github.com/Deliverome-Project/accessible-surfaceome",
  },
  {
    label: "Data",
    ariaLabel: "Data deposit on Zenodo",
    href: "https://doi.org/10.5281/zenodo.20805383",
  },
];

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

export function PaperStrip() {
  const [citeOpen, setCiteOpen] = useState(false);
  // Which format the panel shows; a copy switches it to what was copied.
  const [shown, setShown] = useState<Format>("citation");
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const textRef = useRef<HTMLPreElement>(null);
  const panelId = useId();

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
    <aside className={styles.paper} aria-label="The paper">
      <div className={styles.row}>
        <p className={styles.citationLine}>
          <cite className={styles.title}>The accessible human surfaceome</cite>
          <span className={styles.meta}>
            Carlson, Hollingsworth &amp; Smallegan · bioRxiv, 2026
          </span>
        </p>
        <div className={styles.actions}>
          <a
            href={PAPER_HTML_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.read}
            aria-label="Read the paper (opens in a new tab)"
          >
            Read the paper
            <span aria-hidden="true">→</span>
          </a>
          <ul className={styles.links}>
            {PAPER_LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.link}
                  aria-label={`${link.ariaLabel} (opens in a new tab)`}
                >
                  {link.label}
                </a>
              </li>
            ))}
            <li>
              <button
                type="button"
                className={styles.citeToggle}
                aria-expanded={citeOpen}
                aria-controls={panelId}
                onClick={() => setCiteOpen((o) => !o)}
              >
                Cite
              </button>
            </li>
          </ul>
        </div>
      </div>
      <div id={panelId} className={styles.panel} hidden={!citeOpen}>
        <pre
          ref={textRef}
          className={
            shown === "bibtex"
              ? `${styles.citeText} ${styles.bibtex}`
              : styles.citeText
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
    </aside>
  );
}
