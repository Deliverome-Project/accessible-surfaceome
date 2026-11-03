import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import styles from "../reproducibility/page.module.css";

export const metadata: Metadata = {
  title: "Privacy — Surfaceome",
  description:
    "What the Surfaceome viewer and API collect: no cookies or cross-site " +
    "tracking, aggregate Cloudflare analytics, anonymous click counts, a " +
    "daily unique-visitor count, and the details you choose to send with " +
    "feedback.",
};

/**
 * /privacy/ — deliberately minimal notice. Keep it true to what the
 * site actually does: if analytics, logging or the feedback form change
 * (e.g. a cookie, an identifier, a new processor), update this page in
 * the same change.
 */
export default function PrivacyPage() {
  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>Privacy</h1>
          <p className={styles.lede}>Last updated 3 November 2026.</p>
        </header>

        <section className={styles.section}>
          <p className={styles.body}>
            We don&rsquo;t use cookies, ads, or cross-site tracking, we
            don&rsquo;t follow you from one day to the next, and we
            don&rsquo;t sell data.
          </p>
          <p className={styles.body}>
            The site and API run on Cloudflare, which processes standard
            request data (IP address, browser, and the network a request
            comes from) to serve and protect them. We use Cloudflare&rsquo;s
            cookie-free analytics and this request data to understand how
            the catalog is used.
          </p>
          <p className={styles.body}>
            We also count clicks on the site&rsquo;s links and buttons. Each
            click records only the page, the kind of control and its label
            (for example, &ldquo;gene page, JSON download&rdquo;). It carries
            no cookie, identifier, IP address or browser details, so clicks
            can&rsquo;t be linked to each other or to you.
          </p>
          <p className={styles.body}>
            To count how many different people visit each day, each page
            view records the page and a one-way hash of your IP address and
            browser, mixed with a random value that is replaced every day and
            deleted after two days. We never store the IP address or browser
            itself, and once that day&rsquo;s value is deleted the hash
            can&rsquo;t be traced back to you. It also changes every day, so
            your visits on different days can&rsquo;t be linked.
          </p>
          <p className={styles.body}>
            If your browser sends Global Privacy Control or Do Not Track, we
            don&rsquo;t record your clicks or page views at all.
          </p>
          <p className={styles.body}>
            If you send feedback, we keep the name, e-mail, and comment you
            enter. Your e-mail is used only to reply; your name and comment
            are shown publicly only if we approve them for the gene page.
          </p>
          <p className={styles.body}>
            Questions or deletion requests:{" "}
            <a href="mailto:surfaceome-viewer@deliverome.org">
              surfaceome-viewer@deliverome.org
            </a>
            .
          </p>
        </section>
      </section>
    </Shell>
  );
}
