import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import type { StructureViewerData } from "../../../lib/structure-viewer-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { StatusPill } from "../StatusPill/StatusPill";
import { TopologyLegend } from "../IsoformsCard/TopologyBar";
import { StructureViewer } from "../StructureViewerCard/StructureViewer";
import styles from "./GeneHeader.module.css";

function presentTopologyStates(topology: string): string[] {
  if (!topology) return [];
  const seen = new Set<string>();
  for (const ch of topology) seen.add(ch);
  return ["M", "O", "I", "S", "B"].filter((s) => seen.has(s));
}

interface GeneHeaderProps {
  rec: SurfaceomeRecord;
  /** Descriptive gene name + synonyms from NCBI gene_info. The record
   *  itself doesn't carry the field; the page loads it server-side via
   *  ``loadGeneName(symbol)`` and passes it down. ``null`` when no
   *  entry exists for the symbol. */
  geneName?: { name: string; synonyms: string[] } | null;
  /** DeepTMHMM topology data for the canonical UniProt. Loaded
   *  server-side via ``loadStructureViewerData(uniprot_acc)``;
   *  ``null`` when no JSON exists for the UniProt — header
   *  collapses back to single-column. Membrane-anchored cytoplasmic
   *  proteins (DeepTMHMM type GLOB, e.g. SRC, myristoyl-anchored)
   *  CAN still have a JSON when emitted via the build script's
   *  ``--include-globular`` flag; the viewer paints them uniformly
   *  intracellular and the caption is adjusted to describe the
   *  membrane-anchoring rather than a transmembrane orientation. */
  structureData?: StructureViewerData | null;
}

function tierCounts(rec: SurfaceomeRecord) {
  let primary = 0;
  let secondary = 0;
  let tertiary = 0;
  for (const e of rec.evidence) {
    if (e.evidence_tier === "primary") primary += 1;
    else if (e.evidence_tier === "secondary") secondary += 1;
    else if (e.evidence_tier === "tertiary") tertiary += 1;
  }
  return { primary, secondary, tertiary, total: rec.evidence.length };
}

function accessibilityTone(value: string) {
  if (value === "high") return "success" as const;
  if (value === "moderate") return "teal" as const;
  if (value === "low") return "amber" as const;
  return "neutral" as const;
}

function gradeTone(value: string) {
  if (value === "direct_multi_method") return "success" as const;
  if (value === "direct_single_method") return "teal" as const;
  if (value === "supportive_but_indirect") return "amber" as const;
  if (value === "conflicting") return "danger" as const;
  return "neutral" as const;
}

/**
 * GeneHeader — display-scale gene symbol, executive lede, identifier
 * links, and four vitals. Driven entirely by `executive_summary` +
 * derived counts from the evidence ledger; no v0.x targetability /
 * surface_biology fields.
 */
export function GeneHeader({ rec, geneName, structureData }: GeneHeaderProps) {
  const g = rec.gene;
  const exec = rec.executive_summary;
  const counts = tierCounts(rec);
  const ids = [
    {
      label: "HGNC",
      value: g.hgnc_id,
      href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}`,
    },
    {
      label: "UniProt",
      value: g.uniprot_acc,
      href: `https://www.uniprot.org/uniprotkb/${g.uniprot_acc}`,
    },
    {
      label: "NCBI Gene",
      value: String(g.ncbi_gene_id),
      href: `https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}`,
    },
    {
      label: "Ensembl",
      value: g.ensembl_gene,
      href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}`,
    },
  ];

  return (
    <header className={styles.header}>
      <div className={styles.headerGrid}>
        <div className={styles.headerText}>
          <p className={`label-mono ${styles.eyebrow}`}>Surfaceome record</p>
          <h1 className={`h-gene ${styles.symbol}`}>{g.hgnc_symbol}</h1>
          {geneName?.name ? (
            <p className={styles.geneName}>
              {geneName.name}
              {geneName.synonyms.length > 0 ? (
                <span className={styles.geneSynonyms}>
                  {" · also known as "}
                  {geneName.synonyms.slice(0, 4).join(", ")}
                  {geneName.synonyms.length > 4
                    ? `, +${geneName.synonyms.length - 4}`
                    : ""}
                </span>
              ) : null}
            </p>
          ) : null}
          <p className={`lede ${styles.tldr}`}>{exec.one_paragraph}</p>

          <ul className={styles.ids} aria-label="External identifiers">
            {ids.map((id) => (
              <li key={id.label} className={styles.idItem}>
                <a
                  className={styles.idLink}
                  href={id.href}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className={`label-mono ${styles.idLabel}`}>{id.label}</span>
                  <span className={styles.idValue}>{id.value}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>

        {structureData ? (
          <aside className={styles.structureSlot} aria-label="3D structure">
            <StructureViewer data={structureData} geneSymbol={g.hgnc_symbol} />
            <TopologyLegend
              presentStates={presentTopologyStates(structureData.topology)}
            />
            <p className={styles.structureCaption}>
              <a
                href={`https://alphafold.ebi.ac.uk/entry/${g.uniprot_acc}`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.structureLink}
              >
                AlphaFold DB
              </a>
              {structureData.deeptmhmm_type === "GLOB" ? (
                <>
                  {" "}· soluble cytoplasmic (DeepTMHMM ={" "}
                  <span style={{ fontFamily: "var(--font-mono)" }}>GLOB</span>)
                  · membrane-association via lipid anchor / interaction, not a
                  TM helix
                </>
              ) : (
                <> · DeepTMHMM topology · membrane horizontal, extracellular up</>
              )}
            </p>
          </aside>
        ) : null}
      </div>

      <dl className={styles.vitals}>
        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Accessibility</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone={accessibilityTone(exec.surface_accessibility)}>
              {prettyEnum(exec.surface_accessibility)}
            </StatusPill>
            <span className={styles.vitalSub}>{prettyEnum(exec.subcategory)}</span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Evidence grade</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone={gradeTone(exec.evidence_grade_summary)}>
              {prettyEnum(exec.evidence_grade_summary)}
            </StatusPill>
            <span className={styles.vitalSub}>
              {counts.total} entries
            </span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Confidence</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone="lavender">{prettyEnum(exec.confidence)}</StatusPill>
            <span className={styles.vitalSub}>
              {counts.primary} primary · {counts.secondary} secondary
            </span>
          </dd>
        </div>

        <div className={styles.vital}>
          <dt className={`label-mono ${styles.vitalK}`}>Triage</dt>
          <dd className={styles.vitalV}>
            <StatusPill tone="teal">{prettyEnum(rec.triage_signal)}</StatusPill>
            <span className={styles.vitalSub}>
              {exec.headline_risks.length
                ? `${exec.headline_risks.length} headline risk${
                    exec.headline_risks.length === 1 ? "" : "s"
                  }`
                : "No headline risks"}
            </span>
          </dd>
        </div>
      </dl>
    </header>
  );
}
