import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { L1Review } from "../../components/L1Review/L1Review";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "L1 library review — Surfaceome",
  description:
    "Review the Deliverome L1 library member by member: each protein's rung, tag sites with the rationale behind each pick, folded models and contact sites.",
  robots: { index: false, follow: false },
};

/**
 * /l1-review/ — the L1 library review page (dev viewer). Browse the library by rung
 * and membrane-protein class, step through members, and record "looks good / no" or
 * an alternative tag site. The design data comes from /v1/l1-design; reviews go to
 * the token-gated /v1/l1-review endpoints (private database).
 */
export default function L1ReviewPage() {
  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>L1 library review</h1>
          <p className={styles.lede}>
            Every member of the L1 library with the tag site we plan to use and why it was chosen: the rung logic,
            scores, gate and refold results, who decided it and the alternative it beat. Agent sessions now make these
            calls under delegation; <strong>Looks good / No</strong> and <strong>Suggest an alternative tag</strong>{" "}
            are how a reviewer overturns one. Residue numbers are the member&rsquo;s own (an isoform or ortholog is not
            numbered like the canonical). Membrane class is rule-based, for browsing only.
          </p>
        </header>
        <L1Review />
      </section>
    </Shell>
  );
}
