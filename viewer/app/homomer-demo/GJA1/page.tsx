import { Shell } from "../../../components/Shell/Shell";
import { HomoOligomerViewerCard } from "../../../components/surfaceome/HomoOligomerViewerCard/HomoOligomerViewerCard";
import { DEMO_TOPOLOGIES } from "../_demo-topologies";
import styles from "../homomer-demo.module.css";

export const metadata = {
  title: "GJA1 — predicted Homo-Heptamer (c7) · surfaceome",
  description:
    "Demo of the Schweke 2024 AF2 homo-oligomer prediction for GJA1 (P17302, connexin-43) — a 4-TM multi-pass membrane homomer; Schweke's AnAnaS reconstruction picks c7 cyclic symmetry. Use this as a multi-pass-TM example to verify the topology + chain-darken coloring renders the membrane-embedded helices correctly.",
};

export default function GJA1DemoPage() {
  const topo = DEMO_TOPOLOGIES.GJA1;
  return (
    <Shell>
      <main className={`${styles.page} page-width`}>
        <header className={styles.eyebrow}>
          <span className={styles.eyebrowText}>
            Deep-dive · homo-oligomer demo (multi-pass TM)
          </span>
          <h1 className="h-display">GJA1 / connexin-43</h1>
          <p className={styles.lede}>
            Gap-junction subunit, 4 TM helices per chain. Schweke et al.
            2024 predict a <strong>7-mer connexon</strong> — the
            classical hemichannel of a gap junction. All four TMs are
            retained in the Schweke model (unlike single-pass cases
            where the <code>nodiso3</code> filter clips the TM as a
            disconnected cluster), so the cartoon shows the membrane-
            embedded TM bundle directly. TM helices render as yellow on
            even-indexed chains (A, C, E, G) and at 70% darken on
            odd-indexed chains (B, D, F) — the alternation forces each
            chain's TMs to read at maximum contrast against its
            neighbors, so the 7-fold ring symmetry of the connexon is
            visually obvious.
          </p>
        </header>

        <section className={styles.section}>
          <HomoOligomerViewerCard
            geneSymbol="GJA1"
            uniprotAcc="P17302"
            modelLabel="P17302_V1_2_c7 (AnAnaS-reconstructed)"
            stoichiometry={7}
            pdbUrl="/data/structures/schweke/P17302_V1_2_c7.pdb"
            topology={topo.topology}
            deeptmhmmType={topo.deeptmhmm_type}
            blurb="Plasma-membrane connexon (4-TM multi-pass) · TMs at residues 24–44, 77–97, 156–176, 208–228"
          />
        </section>
      </main>
    </Shell>
  );
}
