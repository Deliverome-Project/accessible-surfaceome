import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { CompareTool } from "../../components/CompareTool/CompareTool";
import { loadCatalog } from "../../lib/surfaceome";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Compare a protein list — Surfaceome",
  description:
    "Paste or upload a list of gene symbols / UniProt accessions and " +
    "compare each against the five source databases, the triage call, and " +
    "the deep-dive filters — with set-level enrichment.",
};

/**
 * /compare/ — bring-your-own-list tool. Bakes the same genome-wide
 * catalog the index page uses (`loadCatalog()` is memoized, so the
 * second SSG call is free) and hands the rows to a client component
 * that resolves a pasted / uploaded protein list against them entirely
 * in-browser. Nothing about the user's list is sent to a server.
 */
export default async function ComparePage() {
  const catalog = await loadCatalog();

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>Compare a protein list</h1>
          <p className={styles.lede}>
            Paste or upload a list of gene symbols or UniProt accessions to
            see how each scores across the five source databases (UniProt,
            GO, SURFY, CSPA, HPA), the triage agent&rsquo;s surface call, and
            — where a deep-dive record exists — the full filter set. A summary
            panel reports which signals are enriched in your list relative to
            the whole catalog. The list is matched in your browser; nothing is
            uploaded.
          </p>
        </header>

        <CompareTool
          rows={catalog.rows}
          nRows={catalog.n_rows}
          nWithDeepDive={catalog.n_with_deep_dive}
        />
      </section>
    </Shell>
  );
}
