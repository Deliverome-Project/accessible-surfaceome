import type {
  AccessibilityRelevance,
  ExpressionLevel,
  MethodFamily,
  MethodObservation,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { tooltips } from "../../../lib/tooltips";
import { antibodyLink } from "../../../lib/antibody-links";
import { chipJumpTargets } from "../../../lib/chipJumpTargets";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { InfoTip } from "../../InfoTip/InfoTip";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./SurfaceEvidenceCard.module.css";

// Assay-type grouping for the method blocks. Order = how a target-
// discovery reader scans evidence: antibody-based direct surface assays
// first (flow → IF → IHC), then surface mass spec + its biochemical
// cousins (biotinylation / glycoproteomics / proximity labeling /
// fractionation), then functional engagement, then the catch-all.
// `method_family` is the schema's coarse axis; we group on it and show a
// per-type finding count.
const FAMILY_ORDER: MethodFamily[] = [
  "flow_cytometry",
  "immunofluorescence",
  "immunohistochemistry",
  "mass_spec",
  "biotinylation",
  "glycoproteomics",
  "proximity_labeling",
  "fractionation",
  "functional_surface_assay",
  "other",
];

const FAMILY_LABEL: Record<MethodFamily, string> = {
  flow_cytometry: "Flow cytometry",
  immunofluorescence: "Immunofluorescence",
  immunohistochemistry: "Immunohistochemistry",
  mass_spec: "Surface mass spec",
  biotinylation: "Surface biotinylation",
  glycoproteomics: "Glycoproteomics",
  proximity_labeling: "Proximity labeling",
  fractionation: "Membrane fractionation",
  functional_surface_assay: "Functional surface assay",
  other: "Other",
};

// Short label for the top-line summary chips (tighter than the full
// group-header label).
const FAMILY_SHORT: Record<MethodFamily, string> = {
  flow_cytometry: "Flow",
  immunofluorescence: "IF",
  immunohistochemistry: "IHC",
  mass_spec: "Surface MS",
  biotinylation: "Biotin",
  glycoproteomics: "Glyco-MS",
  proximity_labeling: "Prox-label",
  fractionation: "Fractionation",
  functional_surface_assay: "Functional",
  other: "Other",
};

/** Group method observations by `method_family`, preserving FAMILY_ORDER
 *  and dropping families with no findings. */
function groupByFamily(
  methods: MethodObservation[],
): { family: MethodFamily; methods: MethodObservation[] }[] {
  const buckets = new Map<MethodFamily, MethodObservation[]>();
  for (const m of methods) {
    const fam: MethodFamily = m.method_family ?? "other";
    const list = buckets.get(fam);
    if (list) list.push(m);
    else buckets.set(fam, [m]);
  }
  return FAMILY_ORDER.filter((f) => buckets.has(f)).map((family) => ({
    family,
    methods: buckets.get(family) as MethodObservation[],
  }));
}

// Membrane-localization / colocalization surface_claim_types. A
// permeabilized "expression_only" assay (which measures total protein,
// not surface accessibility) is still worth showing on the surface card
// when it demonstrates one of these — e.g. PM co-localization with a
// membrane marker, junctional localization — because that's real
// localization signal even though the assay can't prove ACCESSIBILITY.
const MEMBRANE_LOCALIZATION_CLAIMS = new Set([
  "plasma_membrane_localized",
  "cell_junction_localized",
  "membrane_fraction_enriched",
  "apical_or_luminal",
]);

/** Whether a method block earns a place on the surface-evidence card.
 *  Drops "expression_only" blocks (permeabilized total-protein reads that
 *  say nothing about surface accessibility) UNLESS they still show
 *  membrane / PM localization or colocalization — those carry localization
 *  signal worth keeping. Every non-expression_only block is kept. */
function isSurfaceRelevant(m: MethodObservation): boolean {
  if (m.accessibility_relevance !== "expression_only") return true;
  return MEMBRANE_LOCALIZATION_CLAIMS.has(m.surface_claim_type);
}

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

// (gradeTone removed alongside the banner pill it tinted — the
// GeneHeader's "Surface evidence" vital is the only place that needs
// the tone-from-grade mapping now.)

function relevanceTone(v: AccessibilityRelevance) {
  if (v === "direct_surface_accessibility") return "success" as const;
  if (v === "supports_surface_localization") return "teal" as const;
  if (v === "supports_membrane_association") return "lavender" as const;
  if (v === "expression_only") return "amber" as const;
  return "neutral" as const;
}

function levelTone(v: ExpressionLevel) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  if (v === "absent") return "neutral" as const;
  return "neutral" as const;
}

function severityTone(v: Severity | "high" | "moderate" | "low" | "unclear") {
  if (v === "high") return "danger" as const;
  if (v === "moderate") return "amber" as const;
  if (v === "low") return "success" as const;
  return "neutral" as const;
}

export function SurfaceEvidenceCard({ rec, n }: Props) {
  const se = rec.surface_evidence;
  const geneSymbol = rec.gene.hgnc_symbol;
  // Filter out non-surface "expression_only" blocks before grouping (keep
  // the membrane-localization exceptions). nHidden powers an honest
  // footnote so the drop isn't silent.
  const shownMethods = se.methods.filter(isSurfaceRelevant);
  const nHidden = se.methods.length - shownMethods.length;
  const familyGroups = groupByFamily(shownMethods);
  return (
    <SectionCard
      n={n}
      eyebrow="Surface evidence"
      title="Plasma-membrane evidence"
      meta={`${shownMethods.length} method block${shownMethods.length === 1 ? "" : "s"}`}
    >
      {/* Evidence-grade value (Conflicting / Direct multi-method / etc.)
          was removed from the eyebrow meta — the same value is already
          shown as the "Surface evidence" vital up in the GeneHeader,
          and surfacing it twice (here + above) just split attention.
          The eyebrow now carries only the method-block count, which
          isn't shown anywhere else. The synthesizer's narrative
          rationale stays in the banner; that's the piece that doesn't
          appear elsewhere on the page. */}
      <div className={styles.banner}>
        {/* grade_rationale prose often cites evidence inline as
         *  ``(a1_evi_06, high-weight)`` or ``(a1_evi_09, a1_evi_15,
         *  moderate)``. linkifyEvidenceRefs wraps each ``aN_evi_NN``
         *  occurrence in a clickable EvidenceChip so the reader can
         *  open the global EvidenceDrawer without mentally cross-
         *  referencing the §Evidence ledger. */}
        <p className={styles.bannerProse}>
          {linkifyEvidenceRefs(se.grade_rationale)}
        </p>
      </div>

      {shownMethods.length === 0 ? (
        <p className={styles.empty}>
          {se.methods.length === 0
            ? "No method observations recorded."
            : "Only expression-level (non-surface) findings recorded — no surface-accessibility assays to show."}
        </p>
      ) : (
        <div className={styles.methods}>
          {se.methods.map((m, i) => (
            <div key={i} className={styles.method}>
              <div className={styles.methodHead}>
                <StatusPill tone="teal" size="sm">
                  {prettyEnum(m.method_subclass)}
                </StatusPill>
                <StatusPill tone="neutral" size="sm">
                  {prettyEnum(m.permeabilization)}
                </StatusPill>
                <StatusPill tone="lavender" size="sm">
                  {prettyEnum(m.expression_system)}
                </StatusPill>
                <StatusPill tone={relevanceTone(m.accessibility_relevance)} size="sm">
                  {prettyEnum(m.accessibility_relevance)}
                </StatusPill>
                <EvidenceChipList ids={m.cited_evidence_ids} label="Cites" />
              </div>

              {m.antibodies.length > 0 ? (
                <div className={styles.antibodies}>
                  <p className={`label-mono ${styles.subLabel}`}>Antibodies</p>
                  <ul className={styles.abList}>
                    {m.antibodies.map((ab, j) => {
                      const reagentParts = [
                        ab.clone,
                        ab.vendor,
                        ab.catalog,
                        ab.rrid,
                      ].filter((x): x is string => Boolean(x));
                      const hasReagentDetails = reagentParts.length > 0;
                      const link = hasReagentDetails
                        ? antibodyLink(geneSymbol, ab)
                        : null;
                      return (
                        <li key={j} className={styles.abItem}>
                          <span className={styles.abName}>{ab.name}</span>
                          <span className={styles.abMeta}>
                            {hasReagentDetails
                              ? reagentParts.join(" · ")
                              : "(reagent details not in source)"}
                            {link ? (
                              <a
                                className={styles.abLink}
                                href={link.href}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={
                                  link.kind === "rrid"
                                    ? "Open this antibody on the Antibody Registry (resolved via RRID)"
                                    : "Search the web for this antibody (gene symbol + clone / vendor / catalog)"
                                }
                              >
                                {link.label}
                              </a>
                            ) : null}
                          </span>
                          <span className={styles.abPills}>
                            <StatusPill tone="neutral" size="sm">
                              {prettyEnum(ab.monoclonal_or_polyclonal)}
                            </StatusPill>
                            <StatusPill tone="teal" size="sm">
                              {prettyEnum(ab.antibody_epitope_region)}
                            </StatusPill>
                            <StatusPill
                              tone={
                                ab.validation_strength === "strong"
                                  ? "success"
                                  : ab.validation_strength === "moderate"
                                  ? "amber"
                                  : "neutral"
                              }
                              size="sm"
                            >
                              {ab.validation_strength === "none"
                                ? "no validation"
                                : `${prettyEnum(ab.validation_strength)} validation`}
                            </StatusPill>
                            <InfoTip label="About validation strength">
                              {tooltips.antibody_validation_strength}
                            </InfoTip>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : null}

              {m.expression_observations.length > 0 ? (
                <div className={styles.obsBlock}>
                  <p className={`label-mono ${styles.subLabel}`}>Observations</p>
                  <table className={styles.obsTable}>
                    <thead>
                      <tr>
                        <th scope="col">Context</th>
                        <th scope="col">Sample</th>
                        <th scope="col">
                          Level
                          <InfoTip label="About expression level">
                            {tooltips.expression_observation_level}
                          </InfoTip>
                        </th>
                        <th scope="col">Cites</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.expression_observations.map((o, k) => (
                        <tr key={k}>
                          <td>{o.context}</td>
                          <td>{prettyEnum(o.sample_type)}</td>
                          <td>
                            <StatusPill tone={levelTone(o.level)} size="sm">
                              {prettyEnum(o.level)}
                            </StatusPill>
                          </td>
                          <td>
                            <EvidenceChipList ids={o.cited_evidence_ids} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {se.non_surface_expression.length > 0 ? (
        <div className={styles.subsection}>
          <p className={`label-mono ${styles.subhead}`}>
            Non-surface expression (RNA / bulk protein)
          </p>
          <table className={styles.obsTable}>
            <thead>
              <tr>
                <th scope="col">Context</th>
                <th scope="col">Sample</th>
                <th scope="col">Measurement</th>
                <th scope="col">Level</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {se.non_surface_expression.map((o, i) => (
                <tr key={i}>
                  <td>{o.context}</td>
                  <td>{prettyEnum(o.sample_type)}</td>
                  <td>{prettyEnum(o.measurement_type)}</td>
                  <td>
                    <StatusPill tone={levelTone(o.level)} size="sm">
                      {prettyEnum(o.level)}
                    </StatusPill>
                  </td>
                  <td>
                    <EvidenceChipList ids={o.cited_evidence_ids} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {se.contradicting_evidence.length > 0 ? (
        <div
          id={chipJumpTargets.contradictingEvidence}
          tabIndex={-1}
          className={styles.subsection}
        >
          <p className={`label-mono ${styles.subhead}`}>Contradicting evidence</p>
          <ul className={styles.contradictions}>
            {se.contradicting_evidence.map((c, i) => (
              <li key={i} className={styles.contradiction}>
                <div className={styles.contradictionHead}>
                  <StatusPill
                    tone={severityTone(c.severity_for_surface_accessibility)}
                    size="sm"
                  >
                    {prettyEnum(c.contradiction_type)}
                  </StatusPill>
                  <span className={styles.contradictionSeverity}>
                    severity · {prettyEnum(c.severity_for_surface_accessibility)}
                  </span>
                  <EvidenceChipList ids={c.cited_evidence_ids} label="Cites" />
                </div>
                <p className={styles.contradictionClaim}>
                  {linkifyEvidenceRefs(c.claim)}
                </p>
                {c.likely_explanation ? (
                  <p className={styles.contradictionExplain}>
                    <span className={`label-mono ${styles.subLabel}`}>
                      Likely explanation
                    </span>{" "}
                    {linkifyEvidenceRefs(c.likely_explanation)}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </SectionCard>
  );
}
