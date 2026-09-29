import type { Revisions, RevisionChange } from "../../../lib/revisions";
import styles from "./RevisionStrip.module.css";

/** Plain-language label per `changed` entry, combined with " + " when a
 *  revision touched more than one part (e.g. "record updated + Markdown
 *  refreshed"). `"first_archived"` always stands alone — a gene's first
 *  revision has nothing to diff against. */
const CHANGED_LABELS: Record<Exclude<RevisionChange, "first_archived">, string> = {
  record: "record updated",
  evidence: "evidence updated",
  markdown: "Markdown refreshed",
};

function changedLabel(changed: RevisionChange[] | undefined): string | null {
  if (!changed || !changed.length) return null;
  if (changed.includes("first_archived")) return "first archived version";
  return changed.map((c) => CHANGED_LABELS[c as Exclude<RevisionChange, "first_archived">] ?? c).join(" + ");
}

/** One-line "cite this version" strip for the gene page (record history).
 *  Renders the currently-served revision, what changed vs. the previous
 *  revision, its publish date, the numbered data release it landed in
 *  (when any), a permanent link to this exact revision, and a link to the
 *  full revision history. Omitted entirely by the caller when
 *  `/v1/genes/{sym}/revisions` hasn't resolved yet or the gene has no
 *  revision history (see `parseRevisions`). */
export function RevisionStrip({ revisions }: { revisions: Revisions }) {
  const { current, listUrl } = revisions;
  const release = current.releases[0];
  const label = changedLabel(current.changed);
  return (
    <p className={styles.strip}>
      <span>{`Revision ${current.revision}`}</span>
      {label ? (
        <>
          <span aria-hidden="true"> · </span>
          <span>{label}</span>
        </>
      ) : null}
      <span aria-hidden="true"> · </span>
      <span>{`published ${current.published_at.slice(0, 10)}`}</span>
      {release ? (
        <>
          <span aria-hidden="true"> · </span>
          <span>{`in release v${release.version}`}</span>
        </>
      ) : null}
      <span aria-hidden="true"> · </span>
      <a
        className={styles.link}
        href={current.url}
        target="_blank"
        rel="noopener noreferrer"
        data-hint="Permanent link to exactly this version of the record. It never changes, even after the record is updated."
      >
        Cite this version
      </a>
      {release?.zenodo_version_doi ? (
        <>
          {" ("}
          <a
            className={styles.link}
            href={`https://doi.org/${release.zenodo_version_doi}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {release.zenodo_version_doi}
          </a>
          {")"}
        </>
      ) : null}
      <span aria-hidden="true"> · </span>
      <a
        className={styles.link}
        href={listUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        All revisions
      </a>
    </p>
  );
}
