import { type ReactNode } from "react";

// Typed tokens used inside finding claims. HLA alleles and peptide sequences
// are not prose — they're structured identifiers, and rendering them as flat
// bold text loses the fields the immunology reader needs to parse at a glance.

function HlaAllele({ value }: { value: string }) {
  const m = /^(HLA-[A-Z]\d?)(?:\*([\d:]+))?$/.exec(value);
  if (!m) return <span className="tok tok-allele">{value}</span>;
  const [, locus, rest] = m;
  const fields = rest ? rest.split(":") : [];
  return (
    <span className="tok tok-allele" title={`HLA class I allele ${value}`}>
      <span className="tok-tag">allele</span>
      <span className="tok-body">
        <span className="tok-locus">{locus}</span>
        {fields.length > 0 && <span className="tok-sep">*</span>}
        {fields.map((f, i) => (
          <span key={i} style={{ display: "contents" }}>
            {i > 0 && <span className="tok-sep">:</span>}
            <span className="tok-field">{f}</span>
          </span>
        ))}
      </span>
    </span>
  );
}

function Peptide({ seq }: { seq: string }) {
  return (
    <span className="tok tok-peptide" title={`${seq.length}-mer peptide`}>
      <span className="tok-tag">{seq.length}-mer</span>
      <span className="tok-body tok-seq">{seq}</span>
    </span>
  );
}

interface Finding {
  id: string;
  claim: ReactNode;
  meta: { label: string; tone?: "info" | "warn" | "danger" | "muted" }[];
  bucket: string;
  field: string;
  ids: string[];
}

// KAAG1-specific findings. When other genes get full records, this list
// will be derived from the SurfaceomeRecord (e.g., one finding per
// load-bearing risk + the tier rationale) — for now we ship the prototype's
// hand-written set so the demo matches.
const KAAG1_FINDINGS: Finding[] = [
  {
    id: "not_surface",
    claim: <>KAAG1 is <em>not</em> a surface protein. UniProt records 84 aa with no signal peptide, transmembrane, or GPI anchor.</>,
    meta: [{ label: "0 / 8 surface vote", tone: "danger" }, { label: "blocking risk", tone: "danger" }],
    bucket: "surface_biology",
    field: "surface_status",
    ids: ["evi_001", "evi_006"],
  },
  {
    id: "mhc_handle",
    claim: <>The therapeutic handle is a <Peptide seq="LPRWPPPQL" /> presented on <HlaAllele value="HLA-B*07" />, encoded by the antisense transcript RU2AS — not by canonical KAAG1 mRNA.</>,
    meta: [{ label: "MHC-I peptide", tone: "info" }, { label: "antisense origin", tone: "muted" }],
    bucket: "targetability",
    field: "tldr",
    ids: ["evi_001"],
  },
  {
    id: "kidney_liability",
    claim: <>Normal renal proximal tubule cells express RU2AS and are <em>lysed</em> by the same CTL clones that kill RCC lines — a real on-target nephrotoxicity risk.</>,
    meta: [{ label: "high severity", tone: "warn" }, { label: "PMID:10601354", tone: "muted" }],
    bucket: "expression",
    field: "summary",
    ids: ["evi_002", "evi_004"],
  },
  {
    id: "modality_gating",
    claim: <>Only <em>TCR-mimic mAbs</em> and <em>TCR-T</em> are mechanistically valid. ADC, naked mAb, bispecific, and radioligand modalities don't apply — there's no ECD to engage.</>,
    meta: [{ label: "TCR-mimic primary", tone: "info" }, { label: "5 modalities ruled out", tone: "muted" }],
    bucket: "targetability",
    field: "tldr",
    ids: ["evi_001"],
  },
  {
    id: "haplotype_gating",
    claim: <>Patient eligibility is gated to <HlaAllele value="HLA-B*07:02" /> — roughly 10–15% of European populations, lower elsewhere. Cross-allele presentation is unproven.</>,
    meta: [{ label: "polymorphism dependent", tone: "warn" }],
    bucket: "targetability",
    field: "tldr",
    ids: ["evi_001"],
  },
];

interface Props {
  symbol: string;
  isExpanded: (bucket: string, field: string) => boolean;
  toggleField: (bucket: string, field: string) => void;
}

export function KeyFindings({ symbol, isExpanded, toggleField }: Props) {
  const findings = symbol === "KAAG1" ? KAAG1_FINDINGS : [];
  if (!findings.length) return null;
  return (
    <div className="card findings-card" style={{ marginBottom: 24 }}>
      <header>
        <h2><span className="num">01</span>Key findings</h2>
        <span className="header-meta">Click a finding to drill into its evidence and sources</span>
      </header>
      {findings.map((f, i) => {
        const open = isExpanded(f.bucket, f.field);
        return (
          <div key={f.id} className="finding-row" data-open={open}>
            <button
              type="button"
              className="finding-head"
              aria-expanded={open}
              onClick={() => toggleField(f.bucket, f.field)}
            >
              <span className="finding-num">{String(i + 1).padStart(2, "0")}</span>
              <div className="finding-claim">{f.claim}</div>
              <span className="finding-toggle" aria-hidden="true">+</span>
            </button>
            <div className="finding-meta">
              {f.meta.map((m, j) => (
                <span key={j} className={"finding-pip " + (m.tone || "")}>
                  <span className="dot" />
                  {m.label}
                </span>
              ))}
            </div>
            {open && (
              <div className="finding-drill">
                Cited evidence: <code style={{ fontFamily: "var(--font-mono)" }}>{f.ids.join(", ")}</code>
                {" — full source detail lands with the M3 evidence corpus."}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
