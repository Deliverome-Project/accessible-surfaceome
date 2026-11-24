import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { L1Review } from "../../components/L1Review/L1Review";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "v1 library review — Surfaceome",
  description:
    "Review the Deliverome surfaceome library v1 member by member: each protein's rung, tag sites with the rationale behind each pick, folded models and contact sites.",
  robots: { index: false, follow: false },
};

/**
 * /l1-review/ — backward-compatible alias for /v1-review/ (v1 library review page).
 * Browse the library by rung and membrane-protein class, step through members, and record
 * "looks good / no" or an alternative tag site. The design data comes from /v1/l1-design;
 * reviews go to /v1/l1-review (construct IDs remain l1-p…).
 */
export default function L1ReviewPage() {
  return (
    <Shell>
      <section className={styles.page}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>v1 library review</h1>
          <p className={styles.lede}>
            <strong>Residue numbers are each member&rsquo;s own</strong> (isoforms/orthologs differ from canonical).
          </p>
        </header>
        <L1Review />
      </section>
    </Shell>
  );
}
