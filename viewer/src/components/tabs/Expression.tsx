import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum, tissueLabel } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function ExpressionTab({ rec, isExpanded, toggleField }: Props) {
  const ex = rec.expression;
  return (
    <div className="section-grid">
      <div className="col">
        <div className="card">
          <header><h2><span className="num">02</span>Expression profile</h2></header>
          <FieldRow k="Tumor specificity">
            <span className="tag spec">{prettyEnum(ex.tumor_specificity)}</span>
          </FieldRow>
          <FieldRow k="Tumor indications">
            <div className="tag-list">
              {ex.tumor_indications.map((x) => <span key={x} className="tag">{tissueLabel(x)}</span>)}
            </div>
          </FieldRow>
          <FieldRow k="Top normal tissues">
            <div className="tag-list">
              {ex.normal_tissue_top.map((x) => <span key={x} className="tag">{tissueLabel(x)}</span>)}
            </div>
          </FieldRow>
          <FieldRow k="Concerns">
            <div className="tag-list">
              {ex.normal_tissue_concerns.map((x) => (
                <span key={x} className="tag" style={{ color: "var(--warn)", borderColor: "rgba(192,120,48,0.35)" }}>
                  {tissueLabel(x)}
                </span>
              ))}
            </div>
          </FieldRow>
          <hr className="hr" />
          <FieldRow
            k="Summary"
            ids={ex.cited_evidence_ids}
            expanded={isExpanded("expression", "summary")}
            onToggle={() => toggleField("expression", "summary")}
          >
            <div className="field-prose">{ex.summary}</div>
          </FieldRow>
        </div>
      </div>
    </div>
  );
}
