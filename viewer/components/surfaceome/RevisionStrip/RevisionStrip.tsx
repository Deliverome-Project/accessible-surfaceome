import type { Revisions } from "../../../lib/revisions";
import styles from "./RevisionStrip.module.css";

/** One-line "cite this version" strip for the gene page (record history).
 *  Renders the currently-served revision, its publish date, the numbered
 *  data release it landed in (when any), a permanent link to this exact
 *  revision, and a link to the full revision history. Omitted entirely by
 *  the caller when `/v1/genes/{sym}/revisions` hasn't resolved yet or the
 *  gene has no revision history (see `parseRevisions`). */
export function RevisionStrip({ revisions }: { revisions: Revisions }) {
  const { current, listUrl } = revisions;
  const release = current.releases[0];
  return (
    <p className={styles.strip}>
      <span>{`Revision ${current.revision}`}</span>
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
