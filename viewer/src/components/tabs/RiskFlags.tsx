import type { SurfaceomeRecord } from "../../lib/types";
import { titleCase } from "../../lib/formatPretty";
import { CiteChip, EvidenceStub } from "../CiteChip";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function RiskFlagsTab({ rec, isExpanded, toggleField }: Props) {
  return (
    <div className="section-grid">
      <div className="col">
        <div className="card">
          <header><h2><span className="num">02</span>Risk flags</h2></header>
          <div className="risk-list">
            {rec.risk_flags.map((r, i) => (
              <div key={i} className="risk">
                <span className={"severity severity-" + r.severity}>{r.severity}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="kind">{r.kind_other_label || titleCase(r.kind)}</div>
                  <div className="desc">{r.description}</div>
                  {r.cited_evidence_ids?.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <CiteChip
                        ids={r.cited_evidence_ids}
                        expanded={isExpanded("risk_flags", String(i))}
                        onToggle={() => toggleField("risk_flags", String(i))}
                        label={r.kind}
                      />
                      {isExpanded("risk_flags", String(i)) && <EvidenceStub />}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
