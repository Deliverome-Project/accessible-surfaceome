"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./CommunityNotesCard.module.css";

const API_BASE =
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
  ?? "https://api.deliverome.org/surfaceome";

interface Note {
  id: string;
  submitter_name: string;
  comment: string;
  approved_at: string;
  /** Optional author affiliation. Renders as a subtle byline detail. */
  affiliation?: string;
  /** Optional ORCID for credibility — renders as a small ↗ link. */
  orcid?: string;
}

interface PublicResponse {
  gene: string;
  notes: Note[];
}

interface Props {
  gene: string;
  n: number;
}

/** Mock notes used when the page is loaded with ``?mock=notes``.
 *  Three representative shapes:
 *    1. A targeting-strategy correction with citation
 *    2. A reagent-validation tip (positive, short)
 *    3. A longer clinical-context comment from a named affiliation
 *  Used for visual review only — the URL query is the dev-only
 *  trigger; production loads strip the params before hitting the
 *  API, so this code path never fires for real readers. */
const MOCK_NOTES: Note[] = [
  {
    id: "mock-1",
    submitter_name: "Dr. Priya Anand",
    affiliation: "Genentech, oncology biologics",
    orcid: "0000-0001-2345-6789",
    comment:
      "The IC sites flagged on the kinase domain (R743, R764) line up with the activation-loop pocket we routinely target with small molecules — agree these aren't antibody-accessible. We do see surface EGFR shedding under EGF stimulation in our HCC827 model though; worth flagging the secreted-form risk more prominently in the headline summary.",
    approved_at: "2026-05-10 14:22:00",
  },
  {
    id: "mock-2",
    submitter_name: "Jordan Reyes",
    affiliation: "MIT, Wittrup lab",
    comment:
      "Clone D11 from Cell Signaling (#2645) is mAb528-equivalent for the EGFR ECD and is paralog-discrimination validated against ErbB2 / ErbB3 / ErbB4 — useful add to the antibody table.",
    approved_at: "2026-05-06 09:11:00",
  },
  {
    id: "mock-3",
    submitter_name: "Anonymous",
    comment:
      "Minor: the catalog says n_sources=5/5 but the HPA tissue-IHC link sometimes 404s for newly added genes. Not a data issue here — just a heads-up for anyone scripting against the Worker.",
    approved_at: "2026-04-28 17:48:00",
  },
];

/** Pull ``?mock=notes`` from the URL (client-only). Returns ``true``
 *  when the dev-only mock trigger is active. */
function usingMock(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  return params.get("mock") === "notes";
}

/**
 * CommunityNotesCard — bottom-of-page section displaying approved
 * reader-submitted notes for a gene. Returns null when there are no
 * approved notes so the section + AnchorNav link disappear entirely.
 *
 * Why client-side fetch (not SSG): notes can be approved mid-day after
 * the static build. The Worker route is open and unauthenticated;
 * fetching at view time means readers see the latest notes without a
 * site rebuild.
 */
export function CommunityNotesCard({ gene, n }: Props) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [errored, setErrored] = useState(false);
  const [mock, setMock] = useState(false);

  useEffect(() => {
    // Mock branch — when ``?mock=notes`` is in the URL, skip the
    // fetch entirely and render synthetic notes for design review.
    if (usingMock()) {
      setMock(true);
      setNotes(MOCK_NOTES);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch(
          `${API_BASE}/v1/feedback/public?gene=${encodeURIComponent(gene)}`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setErrored(true);
          return;
        }
        const j: PublicResponse = await r.json();
        if (!cancelled) setNotes(Array.isArray(j.notes) ? j.notes : []);
      } catch {
        if (!cancelled) setErrored(true);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [gene]);

  // Hide the entire section when the list is empty (or before load,
  // or on transient fetch error). The AnchorNav strip will skip
  // through to the next available section. Approved notes are rare
  // enough that always-rendering an empty box would be noise.
  if (notes === null || notes.length === 0 || errored) return null;

  return (
    <div className={styles.accent}>
      <SectionCard
        n={n}
        eyebrow={mock ? "Community · MOCK" : "Community"}
        title={`Community notes (${notes.length})`}
        meta={
          mock
            ? `${notes.length} synthetic notes for design review (URL ?mock=notes)`
            : `${notes.length} ${notes.length === 1 ? "note" : "notes"}`
        }
      >
      {mock ? (
        <p className={styles.mockBanner}>
          Preview only — these notes don&apos;t exist in production.
          Triggered by <code>?mock=notes</code> in the URL.
        </p>
      ) : null}
      <ul className={styles.list}>
        {notes.map((note) => (
          <li key={note.id} className={styles.note}>
            <p className={styles.comment}>{note.comment}</p>
            <p className={styles.byline}>
              <span className={styles.bylineName}>{note.submitter_name}</span>
              {note.affiliation ? (
                <>
                  <span className={styles.bylineSep} aria-hidden="true">·</span>
                  <span className={styles.bylineAffil}>{note.affiliation}</span>
                </>
              ) : null}
              {note.orcid ? (
                <>
                  <span className={styles.bylineSep} aria-hidden="true">·</span>
                  <a
                    className={styles.bylineLink}
                    href={`https://orcid.org/${note.orcid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`ORCID: ${note.orcid}`}
                  >
                    ORCID ↗
                  </a>
                </>
              ) : null}
              <span className={styles.bylineSep} aria-hidden="true">·</span>
              <time className={styles.bylineDate} dateTime={note.approved_at}>
                {formatDate(note.approved_at)}
              </time>
            </p>
          </li>
        ))}
      </ul>
      </SectionCard>
    </div>
  );
}

function formatDate(iso: string): string {
  // Accept "YYYY-MM-DD HH:MM:SS" (sqlite default) or any ISO-8601.
  // Render as "MMM d, YYYY" — short enough to sit at the end of a
  // byline without dominating it.
  const d = new Date(iso.replace(" ", "T") + "Z");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}
