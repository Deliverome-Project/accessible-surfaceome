import { Shell } from "../../../components/Shell/Shell";
import { HomoOligomerViewerCard } from "../../../components/surfaceome/HomoOligomerViewerCard/HomoOligomerViewerCard";
import { DEMO_TOPOLOGIES } from "../_demo-topologies";
import styles from "../homomer-demo.module.css";

export const metadata = {
  title: "BSCL2 — predicted Homo-13-Mer (c13) · surfaceome",
  description:
    "Demo of the Schweke 2024 AF2 homo-oligomer prediction for BSCL2 (Q96G97, seipin) — the largest cyclic complex in the surfaceome × Schweke intersection (c13, 13 subunits).",
};

export default function BSCL2DemoPage() {
  const topo = DEMO_TOPOLOGIES.BSCL2;
  return (
    <Shell>
      <main className={`${styles.page} page-width`}>
        <header className={styles.eyebrow}>
          <span className={styles.eyebrowText}>
            Deep-dive · homo-oligomer demo
          </span>
          <h1 className="h-display">BSCL2 / seipin</h1>
          <p className={styles.lede}>
            ER membrane protein, regulator of lipid-droplet biogenesis.
            Schweke et al. 2024 predict a <strong>13-mer ring</strong> —
            the largest cyclic complex in the 1,205-gene surfaceome ∩
            Schweke intersection. Even-indexed chains (A, C, E, G, I,
            K, M) render at the canonical DeepTMHMM topology palette
            (TM yellow / extracellular lavender / intracellular green);
            odd-indexed chains (B, D, F, H, J, L) render at a strong
            70% darken so every spatial neighbor stays maximally
            distinct in the ring.
          </p>
        </header>

        <section className={styles.section}>
          <HomoOligomerViewerCard
            geneSymbol="BSCL2"
            uniprotAcc="Q96G97"
            modelLabel="Q96G97_V1_3_c13 (AnAnaS-reconstructed)"
            stoichiometry={13}
            pdbUrl="/data/structures/schweke/Q96G97_V1_3_c13.pdb"
            topology={topo.topology}
            deeptmhmmType={topo.deeptmhmm_type}
            blurb="ER membrane homomer · 2 TMs per subunit (residues 27–47, 243–263) · both termini cytoplasmic"
          />
        </section>
      </main>
    </Shell>
  );
}
