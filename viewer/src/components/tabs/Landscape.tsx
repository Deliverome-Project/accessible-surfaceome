import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function LandscapeTab({ rec, isExpanded, toggleField }: Props) {
  const tl = rec.therapeutic_landscape;
  return (
    <div className="section-grid">
      <div className="col">
        {tl.patent_disclosures.length > 0 && (
          <div className="card">
            <header><h2><span className="num">02</span>Patent disclosures</h2></header>
            {tl.patent_disclosures.map((p, i) => (
              <FieldRow
                key={i}
                k={p.wo_number}
                ids={p.cited_evidence_ids}
                expanded={isExpanded("landscape", "patents")}
                onToggle={() => toggleField("landscape", "patents")}
              >
                <div className="lh-title">{p.title}</div>
                <div className="lh-meta mono">{p.applicant} · priority {p.priority_year} · {prettyEnum(p.modality)}</div>
                <div className="field-prose">{p.summary}</div>
              </FieldRow>
            ))}
          </div>
        )}
        {tl.preclinical_evidence.length > 0 && (
          <div className="card">
            <header><h2><span className="num">03</span>Preclinical evidence</h2></header>
            {tl.preclinical_evidence.map((p, i) => (
              <FieldRow
                key={i}
                k={p.citation}
                ids={p.cited_evidence_ids}
                expanded={isExpanded("landscape", "preclinical")}
                onToggle={() => toggleField("landscape", "preclinical")}
              >
                <div className="lh-meta mono">{prettyEnum(p.modality)}</div>
                <div className="field-prose">{p.finding_summary}</div>
              </FieldRow>
            ))}
          </div>
        )}
        {tl.patent_disclosures.length === 0 && tl.preclinical_evidence.length === 0 && (
          <div className="card">
            <header><h2><span className="num">02</span>Therapeutic landscape</h2></header>
            <div className="empty">No approved drugs, trials, patents, or preclinical evidence on file.</div>
          </div>
        )}
      </div>
    </div>
  );
}
