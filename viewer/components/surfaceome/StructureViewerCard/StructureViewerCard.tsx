import { SectionCard } from "../SectionCard/SectionCard";
import {
  TOPOLOGY_COLORS,
  type StructureViewerData,
} from "../../../lib/structure-viewer-types";
import { StructureViewer } from "./StructureViewer";
import styles from "./StructureViewerCard.module.css";

interface StructureViewerCardProps {
  data: StructureViewerData;
  geneSymbol: string;
  n: number;
}

const STATE_LABELS: Record<string, string> = {
  M: "TM helix",
  O: "Extracellular",
  I: "Intracellular",
  S: "Signal peptide",
  B: "β-strand",
};

/**
 * StructureViewerCard — per-gene 3D structure browser.
 *
 * Renders the AlphaFold DB structure for the canonical UniProt
 * (fetched on demand from alphafold.ebi.ac.uk) colored by DeepTMHMM
 * topology (M / O / I / S / B). 3Dmol.js is lazy-loaded inside the
 * client component so the 524 KB library only loads when the user
 * actually opens the viewer.
 *
 * Ported from the deliverome-internal structure-site viewer
 * (cloudflare/surfaceome_structure_site_viewer). Insertion-site and
 * terminal-candidate coloring are intentionally omitted — this card
 * shows topology only.
 */
export function StructureViewerCard({
  data,
  geneSymbol,
  n,
}: StructureViewerCardProps) {
  const presentStates = (["M", "O", "I", "S", "B"] as const).filter(
    (state) => (data.topology_ranges[state] ?? []).length > 0,
  );

  return (
    <SectionCard
      n={n}
      eyebrow="Structure"
      title={
        <>
          The <em>3D</em> view
        </>
      }
      meta={`AlphaFold DB · DeepTMHMM ${data.source_tool} · ${data.deeptmhmm_type} · ${data.sequence_length} aa`}
      lede={
        <>
          AlphaFold structure of {geneSymbol} ({data.uniprot_acc}), colored by
          per-residue DeepTMHMM topology. The membrane plane runs through the
          yellow helices; loops above point extracellular.
        </>
      }
    >
      <StructureViewer data={data} geneSymbol={geneSymbol} />

      <ul className={styles.legend} aria-label="Topology color legend">
        {presentStates.map((state) => (
          <li key={state} className={styles.legendItem}>
            <span
              className={styles.legendSwatch}
              style={{ background: TOPOLOGY_COLORS[state] }}
              aria-hidden="true"
            />
            <span className={styles.legendLabel}>{STATE_LABELS[state]}</span>
            <span className={styles.legendCount}>
              {data.topology_ranges[state].length}
              {state === "M"
                ? " helix segment" + (data.tm_helix_count === 1 ? "" : "s")
                : ` span${data.topology_ranges[state].length === 1 ? "" : "s"}`}
            </span>
          </li>
        ))}
      </ul>

      <p className={styles.attribution}>
        Structure data from{" "}
        <a
          href={`https://alphafold.ebi.ac.uk/entry/${data.uniprot_acc}`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.attributionLink}
        >
          AlphaFold DB
        </a>{" "}
        · © DeepMind / EMBL-EBI · licensed{" "}
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noopener noreferrer"
          className={styles.attributionLink}
        >
          CC BY 4.0
        </a>{" "}
        · cite Jumper <em>et al.</em>, <cite>Nature</cite> 2021; Varadi{" "}
        <em>et al.</em>, <cite>NAR</cite> 2024.
      </p>
    </SectionCard>
  );
}
