import type { SurfaceomeRecord } from "../../lib/types";
import { prettyEnum } from "../../lib/formatPretty";
import { FieldRow } from "../FieldRow";
import { DBVotes } from "../DBVotes";

interface Props {
  rec: SurfaceomeRecord;
  isExpanded: (b: string, f: string) => boolean;
  toggleField: (b: string, f: string) => void;
}

function strengthPill(s: string) {
  const color =
    s === "strong" ? "#4f8a3a" :
    s === "moderate" ? "#9c8136" :
    "#9c5b36";
  return (
    <span className="pill" style={{ background: `${color}22`, color }}>
      {s}
    </span>
  );
}

function directionLabel(d: string) {
  if (d === "supports_surface") return "supports";
  if (d === "refutes_surface") return "refutes";
  return d;
}

export function SurfaceBiologyTab({ rec, isExpanded, toggleField }: Props) {
  const sb = rec.surface_biology;
  const induced = sb.induced_presentation ?? [];
  const assays = sb.surface_localization_assays ?? [];

  return (
    <div className="section-grid">
      <div className="col">
        <div className="card">
          <header>
            <h2><span className="num">02</span>Surface biology</h2>
            <span className="header-meta">UniProt · M1 panel · primary assays</span>
          </header>
          <FieldRow
            k="Surface status"
            ids={sb.cited_evidence_ids}
            expanded={isExpanded("surface_biology", "surface_status")}
            onToggle={() => toggleField("surface_biology", "surface_status")}
          >
            <span className={"pill status-" + sb.surface_status}>{prettyEnum(sb.surface_status)}</span>
            {rec.triage_signal && rec.triage_signal !== "unknown" && (
              <span className="pill" style={{ marginLeft: 6, opacity: 0.85 }}>
                triage: {prettyEnum(rec.triage_signal)}
              </span>
            )}
          </FieldRow>
          <FieldRow k="Topology">
            <span className="mono">{prettyEnum(sb.topology)}</span>
          </FieldRow>
          <FieldRow k="Anchor type">
            <span className="mono">{prettyEnum(sb.anchor_type)}</span>
          </FieldRow>
          {sb.exposure_class && sb.exposure_class !== "unknown" && (
            <FieldRow k="Exposure class">
              <span className="mono">{prettyEnum(sb.exposure_class)}</span>
            </FieldRow>
          )}
          <FieldRow k="Extracellular domain">
            <span className="mono">
              {sb.extracellular_domain.size_aa ? `${sb.extracellular_domain.size_aa} aa` : "Not applicable"}
            </span>
            {sb.extracellular_domain.notes && (
              <span className="note">{sb.extracellular_domain.notes}</span>
            )}
          </FieldRow>
        </div>

        {induced.length > 0 && (
          <div className="card">
            <header>
              <h2><span className="num">03</span>Induced / conditional presentation</h2>
              <span className="header-meta">{induced.length} context{induced.length === 1 ? "" : "s"}</span>
            </header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Contexts under which this otherwise-intracellular protein reaches
              the outer leaflet. Required for <code>surface_status="conditional_surface"</code>
              calls; informative for <code>rare_surface</code> too.
            </p>
            {induced.map((ip, i) => (
              <FieldRow
                key={i}
                k={prettyEnum(ip.context_kind_other_label ?? ip.context_kind)}
                ids={ip.cited_evidence_ids}
                expanded={isExpanded("surface_biology", `induced-${i}`)}
                onToggle={() => toggleField("surface_biology", `induced-${i}`)}
              >
                <div className="field-prose">{ip.description}</div>
              </FieldRow>
            ))}
          </div>
        )}

        {assays.length > 0 && (
          <div className="card">
            <header>
              <h2><span className="num">{induced.length ? "04" : "03"}</span>Primary surface assays</h2>
              <span className="header-meta">{assays.length} observation{assays.length === 1 ? "" : "s"}</span>
            </header>
            <p className="field-prose" style={{ opacity: 0.7 }}>
              Direct experimental observations of surface localization indexed
              into <code>evidence_claims</code>. Required (≥1) when the surface
              call is anything other than <code>absent</code>.
            </p>
            {assays.map((a, i) => (
              <FieldRow
                key={i}
                k={
                  <span>
                    {prettyEnum(a.assay_type_other_label ?? a.assay_type)}
                    <span className="sub" style={{ marginLeft: 6 }}>{a.species}</span>
                  </span>
                }
                ids={a.cited_evidence_ids}
                expanded={isExpanded("surface_biology", `assay-${i}`)}
                onToggle={() => toggleField("surface_biology", `assay-${i}`)}
              >
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <span className="pill" style={{
                    background: a.direction === "supports_surface" ? "rgba(120,170,80,0.18)" : a.direction === "refutes_surface" ? "rgba(192,80,80,0.18)" : "rgba(140,140,140,0.18)",
                    color: a.direction === "supports_surface" ? "#5d8a37" : a.direction === "refutes_surface" ? "#a14545" : "var(--neutral)",
                  }}>
                    {directionLabel(a.direction)}
                  </span>
                  {strengthPill(a.strength)}
                </div>
                <div className="field-prose" style={{ marginTop: 8 }}>
                  <span className="sub">on </span>
                  <span>{a.cell_type_or_line}</span>
                </div>
              </FieldRow>
            ))}
          </div>
        )}
      </div>

      <div className="col">
        <div className="card">
          <header>
            <h2><span className="num">{induced.length || assays.length ? "05" : "03"}</span>Database vote</h2>
            <span className="header-meta">8 sources</span>
          </header>
          <DBVotes db={sb.db_comparison} />
        </div>
      </div>
    </div>
  );
}
