import styles from "./CiteCount.module.css";

interface CiteCountProps {
  ids?: string[];
  label?: string;
}

/**
 * CiteCount — static chip showing how many evidence IDs back a
 * field. The full evidence drawer ships when the M3 source corpus
 * lands; until then the count is a citation marker, not a button.
 */
export function CiteCount({ ids, label }: CiteCountProps) {
  if (!ids?.length) return null;
  const n = ids.length;
  return (
    <span
      className={styles.cite}
      aria-label={`${n} citation${n === 1 ? "" : "s"}${label ? ` for ${label}` : ""}`}
      title={ids.join(", ")}
    >
      {n}
    </span>
  );
}
