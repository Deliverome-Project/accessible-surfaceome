import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";
import { DBVotes } from "../DBVotes";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

export function SurfaceBiologyTab({ rec, isExpanded, toggleField }: Props) {
  const sb = rec.surface_biology;
  return (
    <div className="section-grid">
      <div className="col">
        <div className="card">
          <header><h2><span className="num">02</span>Surface biology</h2><span className="header-meta">UniProt · DeepTMHMM · M1 panel</span></header>
          <FieldRow
            k="Surface status"
            ids={sb.cited_evidence_ids}
            expanded={isExpanded("surface_biology", "surface_status")}
            onToggle={() => toggleField("surface_biology", "surface_status")}
          >
            <span className={"pill status-" + sb.surface_status}>{prettyEnum(sb.surface_status)}</span>
          </FieldRow>
          <FieldRow k="Topology">
            <span className="mono">{prettyEnum(sb.topology)}</span>
          </FieldRow>
          <FieldRow k="Anchor type">
            <span className="mono">{prettyEnum(sb.anchor_type)}</span>
          </FieldRow>
          <FieldRow k="Extracellular domain">
            <span className="mono">
              {sb.extracellular_domain.size_aa ? `${sb.extracellular_domain.size_aa} aa` : "Not applicable"}
            </span>
            <span className="note">{sb.extracellular_domain.notes}</span>
          </FieldRow>
        </div>
      </div>
      <div className="col">
        <div className="card">
          <header><h2><span className="num">03</span>Database vote</h2><span className="header-meta">8 sources</span></header>
          <DBVotes db={sb.db_comparison} />
        </div>
      </div>
    </div>
  );
}
