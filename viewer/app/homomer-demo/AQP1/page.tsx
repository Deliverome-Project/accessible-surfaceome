import { Shell } from "../../../components/Shell/Shell";
import { HomoOligomerViewerCard } from "../../../components/surfaceome/HomoOligomerViewerCard/HomoOligomerViewerCard";
import { DEMO_TOPOLOGIES } from "../_demo-topologies";
import styles from "../homomer-demo.module.css";

export const metadata = {
  title: "AQP1 — predicted homo-dimer · surfaceome",
  description:
    "Demo of the Schweke 2024 AF2 homo-oligomer prediction for AQP1 (P29972, aquaporin-1) — the simplest multi-pass-TM case in the demo set: 6-TM hourglass-fold water channel forming a Schweke dimer interface. Use to verify the two-chain topology-darken contrast at small N.",
};

export default function AQP1DemoPage() {
  const topo = DEMO_TOPOLOGIES.AQP1;
  return (
    <Shell>
      <main className={`${styles.page} page-width`}>
        <header className={styles.eyebrow}>
          <span className={styles.eyebrowText}>
            Deep-dive · homo-oligomer demo (multi-pass TM dimer)
          </span>
          <h1 className="h-display">AQP1 / aquaporin-1</h1>
          <p className={styles.lede}>
            Water-channel subunit, 6 TM helices per chain in an
            hourglass fold. Schweke et al. 2024 predict a{" "}
            <strong>homo-dimer</strong> — the AQP1 tetramer's
            assembly-unit dimer. With only 2 chains the darken contrast
            is maximal: chain A renders at the full DeepTMHMM palette,
            chain B at ~95% black (near-monochrome). The membrane band
            of yellow TM helices in chain A is visible at the
            chain-chain interface, with the chain-B equivalents echoing
            them as dark silhouettes.
          </p>
        </header>

        <section className={styles.section}>
          <HomoOligomerViewerCard
            geneSymbol="AQP1"
            uniprotAcc="P29972"
            modelLabel="P29972_V1_1 (AF_dimer_models_core)"
            stoichiometry={2}
            pdbUrl="/data/structures/schweke/P29972_V1_1.pdb"
            topology={topo.topology}
            deeptmhmmType={topo.deeptmhmm_type}
            blurb="Plasma-membrane water channel (6-TM multi-pass) · TMs at residues 12–29, 47–65, 91–109, 134–153, 164–181, 207–224"
          />
        </section>
      </main>
    </Shell>
  );
}
