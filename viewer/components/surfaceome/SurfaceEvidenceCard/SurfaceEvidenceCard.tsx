import type {
  AccessibilityRelevance,
  AntibodyRef,
  ExpressionLevel,
  MethodFamily,
  MethodObservation,
  Severity,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { tooltips } from "../../../lib/tooltips";
import { antibodyLink } from "../../../lib/antibody-links";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
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

/** Identifier key for a "detailed" antibody — one carrying a clone /
 *  vendor / catalog / RRID. Returns `null` for a bare AntibodyRef with no
 *  identifier (those render "(reagent details not found)" and aren't
 *  counted). Two AntibodyRefs sharing the same identifier tuple collapse to
 *  one key, so counts reflect UNIQUE detailed antibodies, not raw rows. */
function detailedAntibodyKey(ab: AntibodyRef): string | null {
  if (!(ab.clone || ab.vendor || ab.catalog || ab.rrid)) return null;
  return [ab.name, ab.clone, ab.vendor, ab.catalog, ab.rrid]
    .map((x) => (x ?? "").toLowerCase().trim())
    .join("|");
}

/** Per-group finding counts: method blocks, unique detailed antibodies,
 *  and unique cited-evidence ids. `antibodies` counts only antibodies with
 *  reagent identifiers, deduped across the group's methods. */
function groupCounts(methods: MethodObservation[]): {
  blocks: number;
  antibodies: number;
  citations: number;
} {
  const cites = new Set<string>();
  const abKeys = new Set<string>();
  for (const m of methods) {
    for (const ab of m.antibodies) {
      const k = detailedAntibodyKey(ab);
      if (k) abKeys.add(k);
    }
    for (const id of m.cited_evidence_ids) cites.add(id);
    // Also fold in the per-observation citations so the count reflects all
    // distinct evidence backing this assay type (AntibodyRef itself
    // carries no cited_evidence_ids — the citation lives on the method
    // block + its observations).
    for (const o of m.expression_observations)
      for (const id of o.cited_evidence_ids) cites.add(id);
  }
  return { blocks: methods.length, antibodies: abKeys.size, citations: cites.size };
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

/** One method-observation block (the assay panel + its antibodies +
 *  observations). Extracted so the assay-type groups can each render their
 *  methods without duplicating the body. `geneSymbol` seeds the antibody
 *  link-out search. */
function MethodBlock({
  m,
  geneSymbol,
}: {
  m: MethodObservation;
  geneSymbol: string;
}) {
  // Collapsed-by-default: each method block shows only its headline pills
  // in the <summary>; antibodies + observations + citations live in the
  // body and expand on click. Native <details> keeps this SSG-friendly
  // (no client state) — the assay-type groups can stay long without
  // forcing the reader to scroll past every reagent table.
  // Count UNIQUE antibodies that carry real reagent identifiers (clone /
  // vendor / catalog / RRID) — detail-less ones render "(reagent details
  // not found)" and aren't counted; duplicates (same identifier tuple)
  // collapse to one. The "with details" label makes explicit that the
  // count is reference-bearing antibodies, not every AntibodyRef row.
  const abKeys = new Set<string>();
  for (const ab of m.antibodies) {
    const k = detailedAntibodyKey(ab);
    if (k) abKeys.add(k);
  }
  const nAb = abKeys.size;
  const nObs = m.expression_observations.length;
  const hiddenSummary = [
    nAb > 0 ? `${nAb} antibod${nAb === 1 ? "y" : "ies"} with details` : null,
    nObs > 0 ? `${nObs} observation${nObs === 1 ? "" : "s"}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <details className={styles.method}>
      <summary className={styles.methodHead}>
        {/* method_subclass already encodes the live-cell / permeabilization
            qualifier (e.g. "live_cell_flow", "nonpermeabilized_IF"), so a
            separate permeabilization pill was redundant — dropped. */}
        <StatusPill tone="teal" size="sm">
          {prettyEnum(m.method_subclass)}
        </StatusPill>
        {/* Expression system. "mixed" is split into two explicit chips
            (endogenous + overexpression) so the reader sees both pools
            named rather than a vague "mixed". Each carries the shared
            hover tooltip (what endogenous / overexpression / knock-in
            mean) via StatusPill's `title`, so hovering explains it without
            a click toggling the <details>. */}
        {(m.expression_system === "mixed"
          ? (["endogenous", "overexpression"] as const)
          : [m.expression_system]
        ).map((sys) => (
          <StatusPill
            key={sys}
            tone="lavender"
            size="sm"
            title={tooltips.expression_system}
          >
            {prettyEnum(sys)}
          </StatusPill>
        ))}
        <StatusPill tone={relevanceTone(m.accessibility_relevance)} size="sm">
          {prettyEnum(m.accessibility_relevance)}
        </StatusPill>
        {hiddenSummary ? (
          <span className={styles.methodSummaryMeta}>{hiddenSummary}</span>
        ) : null}
      </summary>
      <div className={styles.methodBody}>
        <EvidenceChipList ids={m.cited_evidence_ids} label="Cites" />

      {m.antibodies.length > 0 ? (
        <div className={styles.antibodies}>
          <p className={`label-mono ${styles.subLabel}`}>Antibodies</p>
          <ul className={styles.abList}>
            {m.antibodies.map((ab, j) => {
              // Reagent identifiers from the source. When ALL are absent we
              // show "(reagent details not found)" AND suppress the
              // link — a bare gene-symbol search with no clone / vendor /
              // catalog isn't specific enough to be useful, and pairing it
              // with "details not in source" reads as contradictory.
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
                      : "(reagent details not found)"}
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
                    <StatusPill
                      tone="neutral"
                      size="sm"
                      title="Monoclonal vs polyclonal antibody. Unknown = the source paper didn't specify."
                    >
                      <ChipLabelValue
                        label="clonality"
                        value={prettyEnum(ab.monoclonal_or_polyclonal)}
                      />
                    </StatusPill>
                    <StatusPill
                      tone="teal"
                      size="sm"
                      title="Which region of the protein the antibody's epitope sits in. Extracellular = it binds the surface-accessible domain (the region that matters for surface targeting); an intracellular epitope isn't reachable on an intact cell. Unknown = not stated."
                    >
                      <ChipLabelValue
                        label="epitope"
                        value={prettyEnum(ab.antibody_epitope_region)}
                      />
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
                      <ChipLabelValue
                        label="validation"
                        value={prettyEnum(ab.validation_strength)}
                        // none / unknown isn't a verdict — render it in the
                        // muted (non-bold) style so it reads as "no data".
                        muted={
                          ab.validation_strength === "none" ||
                          ab.validation_strength === "unknown"
                        }
                      />
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
    </details>
  );
}

export function SurfaceEvidenceCard({ rec, n }: Props) {
  const se = rec.surface_evidence;
  const geneSymbol = rec.gene.hgnc_symbol;
  const familyGroups = groupByFamily(se.methods);
  return (
    <SectionCard
      n={n}
      eyebrow="Surface evidence"
      title="Plasma-membrane evidence"
      meta={`${se.methods.length} method block${se.methods.length === 1 ? "" : "s"}`}
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

      {se.methods.length === 0 ? (
        <p className={styles.empty}>No method observations recorded.</p>
      ) : (
        <>
          {/* Top-line assay-type composition — one count chip per method
              family so the reader sees the evidence mix at a glance before
              scrolling the grouped blocks below. */}
          <div className={styles.summary}>
            {familyGroups.map(({ family, methods }) => (
              <StatusPill key={family} tone="teal" size="sm">
                {FAMILY_SHORT[family]} · {methods.length}
              </StatusPill>
            ))}
          </div>

          {/* Method blocks grouped by assay type (flow / IF-IHC / surface
              mass spec / biochemical / functional / …), each under a
              labeled header carrying its finding count. */}
          <div className={styles.familyGroups}>
            {familyGroups.map(({ family, methods }) => {
              const c = groupCounts(methods);
              return (
                <div key={family} className={styles.familyGroup}>
                  <div className={styles.familyHead}>
                    <span className={styles.familyName}>
                      {FAMILY_LABEL[family]}
                    </span>
                    <span className={styles.familyMeta}>
                      {c.blocks} finding{c.blocks === 1 ? "" : "s"}
                      {c.antibodies > 0
                        ? ` · ${c.antibodies} antibod${
                            c.antibodies === 1 ? "y" : "ies"
                          } with details`
                        : ""}
                      {c.citations > 0
                        ? ` · ${c.citations} citation${
                            c.citations === 1 ? "" : "s"
                          }`
                        : ""}
                    </span>
                  </div>
                  <div className={styles.methods}>
                    {methods.map((m, i) => (
                      <MethodBlock key={i} m={m} geneSymbol={geneSymbol} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
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

      {se.therapeutic_engagement ? (
        <div className={styles.therapeutic}>
          <p className={`label-mono ${styles.subhead}`}>Therapeutic engagement</p>
          <StatusPill tone="maroon" size="md">
            {prettyEnum(se.therapeutic_engagement.highest_stage)}
          </StatusPill>
          <p className={styles.therapeuticProse}>
            {se.therapeutic_engagement.description}
          </p>
          {/* div, not p — `<EvidenceChipList>` renders a flex `<div>`
              which can't legally nest inside `<p>`. The CSS class
              still applies and the visual treatment is identical. */}
          <div className={styles.therapeuticRationale}>
            <span className={`label-mono ${styles.subLabel}`}>
              Surface-form rationale
            </span>
            <span>{linkifyEvidenceRefs(se.therapeutic_engagement.surface_form_rationale)}</span>
            <EvidenceChipList
              ids={se.therapeutic_engagement.cited_evidence_ids}
              label="Cites"
            />
          </div>
        </div>
      ) : null}

      {se.contradicting_evidence.length > 0 ? (
        <div className={styles.subsection}>
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
