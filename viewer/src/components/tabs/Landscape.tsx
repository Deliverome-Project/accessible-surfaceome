import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function LandscapeTab({ rec, isExpanded, toggleField }: Props) {
  // v0.4.0: surface_engagement_validation.preclinical_evidence — the only
  // bucket that survived the refocus. No approved_drugs / clinical_trials /
  // patent_disclosures.
  const newPreclinical =
    rec.surface_engagement_validation?.preclinical_evidence ?? [];
  // v0.3.2 legacy: therapeutic_landscape.{patent_disclosures, preclinical_evidence}.
  const legacyTL = rec.therapeutic_landscape;
  const legacyPatents = legacyTL?.patent_disclosures ?? [];
  const legacyPreclinical = legacyTL?.preclinical_evidence ?? [];

  const hasContent =
    newPreclinical.length + legacyPatents.length + legacyPreclinical.length > 0;

  return (
    <div className="section-grid">
      <div className="col">
        {newPreclinical.length > 0 && (
          <div className="card">
            <header>
              <h2>
                <span className="num">01</span>Surface engagement validation
              </h2>
            </header>
            <p className="field-prose">
              Preclinical studies that demonstrate the protein is engaged by an
              extracellular binder on live cells. Not a therapeutic-precedent
              catalog — surface-accessibility evidence.
            </p>
            {newPreclinical.map((p, i) => (
              <FieldRow
                key={`sev-${i}`}
                k={p.citation}
                ids={p.cited_evidence_ids}
                expanded={isExpanded("landscape", `sev-${i}`)}
                onToggle={() => toggleField("landscape", `sev-${i}`)}
              >
                <div className="field-prose">{p.finding_summary}</div>
              </FieldRow>
            ))}
          </div>
        )}

        {legacyPatents.length > 0 && (
          <div className="card">
            <header>
              <h2>
                <span className="num">02</span>Patent disclosures
                <span className="legacy-pill"> · v0.3.2</span>
              </h2>
            </header>
            {legacyPatents.map((p, i) => (
              <FieldRow
                key={`pat-${i}`}
                k={p.wo_number}
                ids={p.cited_evidence_ids}
                expanded={isExpanded("landscape", `pat-${i}`)}
                onToggle={() => toggleField("landscape", `pat-${i}`)}
              >
                <div className="lh-title">{p.title}</div>
                <div className="lh-meta mono">
                  {p.applicant} · priority {p.priority_year} ·{" "}
                  {prettyEnum(p.modality)}
                </div>
                <div className="field-prose">{p.summary}</div>
              </FieldRow>
            ))}
          </div>
        )}

        {legacyPreclinical.length > 0 && (
          <div className="card">
            <header>
              <h2>
                <span className="num">03</span>Preclinical evidence
                <span className="legacy-pill"> · v0.3.2</span>
              </h2>
            </header>
            {legacyPreclinical.map((p, i) => (
              <FieldRow
                key={`leg-pre-${i}`}
                k={p.citation}
                ids={p.cited_evidence_ids}
                expanded={isExpanded("landscape", `leg-pre-${i}`)}
                onToggle={() => toggleField("landscape", `leg-pre-${i}`)}
              >
                {p.modality && (
                  <div className="lh-meta mono">{prettyEnum(p.modality)}</div>
                )}
                <div className="field-prose">{p.finding_summary}</div>
              </FieldRow>
            ))}
          </div>
        )}

        {!hasContent && (
          <div className="card">
            <header>
              <h2>
                <span className="num">01</span>Surface engagement validation
              </h2>
            </header>
            <div className="empty">
              No preclinical-engagement studies on file for this record.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
