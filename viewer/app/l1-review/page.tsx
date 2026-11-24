import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { L1Review } from "../../components/L1Review/L1Review";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "L1 library review — Surfaceome",
  description:
    "Review the Deliverome L1 library member by member: each protein's rung, tag sites with the rationale behind each pick, folded models and contact sites.",
};

/**
 * /l1-review/ — the L1 library review page. Browse the library by rung
 * and membrane-protein class, step through members, and record "looks good / no" or
 * an alternative tag site. The design data comes from /v1/l1-design; reviews go to
 * /v1/l1-review (private database, name + Turnstile or token).
 *
 * The header is deliberately two lines. A reviewer is here to go through 2,710 members
 * and sees this page tens of times a day; the paragraph that explained the whole scheme
 * cost most of a 1280x800 viewport on every one of those visits, which pushed the
 * filters, the list and the detail panel below the fold. What a reviewer needs every
 * visit stays; the rest is one disclosure away.
 */
export default function L1ReviewPage() {
  return (
    <Shell>
      <section className={styles.page}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>L1 library review</h1>
          <p className={styles.lede}>
            <strong>Residue numbers are each member&rsquo;s own</strong> (isoforms/orthologs differ from canonical).
          </p>
        </header>
        <L1Review />
      </section>
    </Shell>
  );
}
