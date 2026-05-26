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
}

interface PublicResponse {
  gene: string;
  notes: Note[];
}

interface Props {
  gene: string;
  n: number;
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

  useEffect(() => {
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
    <SectionCard
      n={n}
      eyebrow="Community"
      title="Community notes"
      meta={`${notes.length} ${notes.length === 1 ? "note" : "notes"}`}
    >
      <ul className={styles.list}>
        {notes.map((note) => (
          <li key={note.id} className={styles.note}>
            <p className={styles.comment}>{note.comment}</p>
            <p className={styles.byline}>
              — {note.submitter_name}
              {" · "}
              <time dateTime={note.approved_at}>
                {formatDate(note.approved_at)}
              </time>
            </p>
          </li>
        ))}
      </ul>
    </SectionCard>
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
