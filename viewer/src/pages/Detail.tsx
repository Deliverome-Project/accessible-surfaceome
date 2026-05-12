import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { SurfaceomeRecord } from "../lib/types";
import { GeneHeader } from "../components/GeneHeader";
import { KeyFindings } from "../components/KeyFindings";
import { Modalities } from "../components/Modalities";
import { FieldRow } from "../components/FieldRow";
import { ExportMenu } from "../components/ExportMenu";
import { TweaksPanel, TweakSection, TweakRadio } from "../components/TweaksPanel";
import { useTweaks } from "../hooks/useTweaks";
import { SurfaceBiologyTab } from "../components/tabs/SurfaceBiology";
import { ExpressionTab } from "../components/tabs/Expression";
import { LandscapeTab } from "../components/tabs/Landscape";
import { RiskFlagsTab } from "../components/tabs/RiskFlags";
import { RawRecordTab } from "../components/tabs/RawRecord";

type TabId = "biology" | "expression" | "landscape" | "risks" | "raw";

const TWEAK_DEFAULTS = {
  density: "comfortable" as "comfortable" | "compact",
};

type LoadState =
  | { kind: "loading" }
  | { kind: "missing"; symbol: string }
  | { kind: "error"; symbol: string; message: string }
  | { kind: "ready"; rec: SurfaceomeRecord };

export default function Detail() {
  const { symbol = "" } = useParams<{ symbol: string }>();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [tab, setTab] = useState<TabId>("biology");
  const [expandedField, setExpandedField] = useState<{ bucket: string; field: string } | null>(null);
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  useEffect(() => {
    document.documentElement.setAttribute("data-density", t.density);
  }, [t.density]);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    (async () => {
      try {
        const r = await fetch(`/data/genes/${symbol}.json`);
        if (cancelled) return;
        if (r.status === 404) { setState({ kind: "missing", symbol }); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        // Both Vite's dev server and Cloudflare Pages can fall back to
        // index.html for unknown paths. If we get HTML instead of JSON,
        // treat it as "missing" rather than a parse error.
        const ct = r.headers.get("content-type") || "";
        if (!ct.includes("json")) { setState({ kind: "missing", symbol }); return; }
        const rec = (await r.json()) as SurfaceomeRecord;
        if (cancelled) return;
        setState({ kind: "ready", rec });
      } catch (e) {
        if (!cancelled) setState({ kind: "error", symbol, message: (e as Error).message });
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  const rec = state.kind === "ready" ? state.rec : null;

  const tabs: { id: TabId; label: string; count?: number }[] = useMemo(() => {
    if (!rec) return [];
    // v0.4.0 dropped therapeutic_landscape; the new bucket
    // surface_engagement_validation only carries preclinical_evidence.
    // Legacy v0.3.2 records still expose therapeutic_landscape with
    // patent_disclosures + preclinical_evidence + clinical_trials.
    const legacyPatents = rec.therapeutic_landscape?.patent_disclosures?.length ?? 0;
    const legacyPreclinical = rec.therapeutic_landscape?.preclinical_evidence?.length ?? 0;
    const newPreclinical = rec.surface_engagement_validation?.preclinical_evidence?.length ?? 0;
    const landscapeCount = legacyPatents + legacyPreclinical + newPreclinical;
    return [
      { id: "biology", label: "Surface biology" },
      { id: "expression", label: "Expression" },
      { id: "landscape", label: "Therapeutic landscape", count: landscapeCount },
      { id: "risks", label: "Risk flags", count: rec.risk_flags.length },
      { id: "raw", label: "Raw record" },
    ];
  }, [rec]);

  function isExpanded(bucket: string, field: string) {
    return !!expandedField && expandedField.bucket === bucket && expandedField.field === field;
  }
  function toggleField(bucket: string, field: string) {
    setExpandedField((cur) => (cur && cur.bucket === bucket && cur.field === field ? null : { bucket, field }));
  }

  if (state.kind === "loading") {
    return <Shell><div className="empty">Loading {symbol}…</div></Shell>;
  }
  if (state.kind === "missing") {
    return (
      <Shell symbol={symbol}>
        <div className="card" style={{ marginTop: 24 }}>
          <header><h2><span className="num">—</span>Record not found</h2></header>
          <p className="field-prose">
            No record for <strong>{symbol}</strong> has been ingested yet. Only{" "}
            <Link to="/gene/KAAG1" style={{ borderBottom: "1px dotted" }}>KAAG1</Link>{" "}
            has a full record so far — the rest will land as the M2 annotation pipeline
            populates per-gene <code>SurfaceomeRecord</code> JSONs.
          </p>
        </div>
      </Shell>
    );
  }
  if (state.kind === "error") {
    return (
      <Shell symbol={symbol}>
        <div className="card" style={{ marginTop: 24 }}>
          <header><h2><span className="num">!</span>Error</h2></header>
          <p className="field-prose">Couldn't load <strong>{symbol}</strong>: {state.message}</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell symbol={rec!.gene.hgnc_symbol} rec={rec!}>
      <GeneHeader rec={rec!} />

      <KeyFindings symbol={rec!.gene.hgnc_symbol} isExpanded={isExpanded} toggleField={toggleField} />

      <div className="card" style={{ marginBottom: 24 }}>
        <header>
          <h2><span className="num">02</span>Recommendation</h2>
          <span className="header-meta">Click a row to inspect provenance</span>
        </header>
        <FieldRow
          k="tl;dr"
          ids={rec!.targetability.cited_evidence_ids}
          expanded={isExpanded("targetability", "tldr")}
          onToggle={() => toggleField("targetability", "tldr")}
        >
          <div className="field-prose">{rec!.targetability.tldr}</div>
        </FieldRow>
        <Modalities list={rec!.targetability.recommended_modalities ?? []} />
      </div>

      <div className="tabs" role="tablist">
        {tabs.map((x) => (
          <button
            key={x.id}
            className="tab"
            role="tab"
            aria-selected={tab === x.id}
            onClick={() => setTab(x.id)}
          >
            {x.label}
            {x.count != null && <span className="count">{x.count}</span>}
          </button>
        ))}
      </div>

      {tab === "biology" && <SurfaceBiologyTab rec={rec!} isExpanded={isExpanded} toggleField={toggleField} />}
      {tab === "expression" && <ExpressionTab rec={rec!} isExpanded={isExpanded} toggleField={toggleField} />}
      {tab === "landscape" && <LandscapeTab rec={rec!} isExpanded={isExpanded} toggleField={toggleField} />}
      {tab === "risks" && <RiskFlagsTab rec={rec!} isExpanded={isExpanded} toggleField={toggleField} />}
      {tab === "raw" && <RawRecordTab rec={rec!} />}

      <TweaksPanel title="Tweaks">
        <TweakSection title="Display">
          <TweakRadio
            label="Density"
            value={t.density}
            onChange={(v) => setTweak("density", v)}
            options={[
              { label: "Compact", value: "compact" },
              { label: "Comfortable", value: "comfortable" },
            ]}
          />
        </TweakSection>
      </TweaksPanel>
    </Shell>
  );
}

function Shell({
  symbol,
  rec,
  children,
}: {
  symbol?: string;
  rec?: SurfaceomeRecord;
  children: React.ReactNode;
}) {
  return (
    <div className="app">
      <div className="topbar">
        <div className="crumbs">
          <span><Link to="/">Surfaceome</Link></span>
          <span className="sep">/</span>
          <span><Link to="/">Targets</Link></span>
          <span className="sep">/</span>
          <span className="here">{symbol || "—"}</span>
        </div>
        <div className="detail-nav">
          {rec && <ExportMenu rec={rec} />}
        </div>
      </div>
      {children}
    </div>
  );
}
