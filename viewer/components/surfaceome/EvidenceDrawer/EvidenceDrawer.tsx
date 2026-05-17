"use client";

import { useEffect, useMemo, useState } from "react";
import type { Evidence } from "../../../lib/surfaceome-types";
import { StatusPill } from "../StatusPill/StatusPill";

// Local minimal prettyEnum — the canonical one in lib/surfaceome.ts
// pulls in node:fs / node:path (it co-locates SSG helpers), which
// webpack can't tree-shake out of a "use client" boundary. The values
// the drawer renders are all snake_case enums (evidence_tier,
// evidence_type, direction, confidence), so a simple replace + title-
// case is sufficient. Keep in sync with lib/surfaceome.ts ENUM_MAP for
// any enum values that have curated display strings.
function prettyEnum(s: string | null | undefined): string {
  if (!s) return "—";
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
import styles from "./EvidenceDrawer.module.css";

interface EvidenceDrawerProps {
  evidence: readonly Evidence[];
}

/**
 * EvidenceDrawer — global per-page drawer that displays one Evidence
 * record when an EvidenceChip anywhere in the tree fires the
 * ``surfaceome:open-evidence`` custom event. Mirrors the v2 sample's
 * "evidence-card" detail (id, badges, agent's claim, verbatim quote,
 * source link, assay context) but in a slide-in drawer instead of a
 * scroll-target so the reader doesn't lose their place in the prose.
 *
 * Close affordances (same UX grammar as BenchmarkTable's drawer):
 *   • ESC key
 *   • close button (×)
 *   • click on the backdrop layer
 */
export function EvidenceDrawer({ evidence }: EvidenceDrawerProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  const evidenceById = useMemo(() => {
    const map = new Map<string, Evidence>();
    for (const e of evidence) map.set(e.evidence_id, e);
    return map;
  }, [evidence]);

  // Listen for chip clicks anywhere in the tree.
  useEffect(() => {
    function onOpen(e: Event) {
      const ev = e as CustomEvent<{ evidenceId: string }>;
      if (ev.detail?.evidenceId) setOpenId(ev.detail.evidenceId);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenId(null);
    }
    window.addEventListener("surfaceome:open-evidence", onOpen);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("surfaceome:open-evidence", onOpen);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const data = openId ? evidenceById.get(openId) ?? null : null;
  const isOpen = data != null;

  return (
    <>
      <div
        className={`${styles.backdrop} ${isOpen ? styles.backdropOpen : ""}`}
        aria-hidden="true"
        onClick={() => setOpenId(null)}
      />
      <aside
        className={`${styles.drawer} ${isOpen ? styles.drawerOpen : ""}`}
        role="region"
        aria-label={data ? `Evidence ${data.evidence_id}` : "Evidence panel"}
        aria-hidden={!isOpen}
      >
        {data ? <EvidenceCard ev={data} onClose={() => setOpenId(null)} /> : null}
      </aside>
    </>
  );
}

function EvidenceCard({ ev, onClose }: { ev: Evidence; onClose: () => void }) {
  // The v1 schema carries verbatim quotes + source per *span* (each
  // evidence claim can be anchored to multiple spans across one or
  // more sources). Surface the head span's quote + walk the spans for
  // distinct sources to show all citation links.
  type SpanWithSource = {
    text?: string;
    source?: {
      pmc_id?: string;
      pmid?: string;
      doi?: string;
      url?: string;
      title?: string;
      source_type?: string;
    };
  };
  const spans = (ev.spans as SpanWithSource[]) ?? [];
  const headSpan = spans.length ? spans[0] : null;
  // Dedupe source links across spans by pmcid|pmid|doi|url.
  const seenKeys = new Set<string>();
  const sources: Array<{
    href: string;
    label: string;
    title?: string;
  }> = [];
  for (const sp of spans) {
    const s = sp?.source;
    if (!s) continue;
    if (s.pmc_id && !seenKeys.has(`pmc:${s.pmc_id}`)) {
      seenKeys.add(`pmc:${s.pmc_id}`);
      sources.push({
        href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${s.pmc_id}/`,
        label: s.pmc_id,
        title: s.title,
      });
    } else if (s.pmid && !seenKeys.has(`pmid:${s.pmid}`)) {
      seenKeys.add(`pmid:${s.pmid}`);
      sources.push({
        href: `https://pubmed.ncbi.nlm.nih.gov/${s.pmid}/`,
        label: `PMID ${s.pmid}`,
        title: s.title,
      });
    } else if (s.doi && !seenKeys.has(`doi:${s.doi}`)) {
      seenKeys.add(`doi:${s.doi}`);
      sources.push({
        href: `https://doi.org/${s.doi}`,
        label: `doi:${s.doi}`,
        title: s.title,
      });
    } else if (s.url && !seenKeys.has(`url:${s.url}`)) {
      seenKeys.add(`url:${s.url}`);
      sources.push({
        href: s.url,
        label: s.url.replace(/^https?:\/\//, "").slice(0, 48),
        title: s.title ?? s.url,
      });
    }
  }

  type EvidenceLite = Evidence & {
    evidence_type?: string;
    claim_type?: string;
    direction?: string;
    confidence?: string;
    entailment_verified?: boolean;
    entailment_audit_passed?: boolean | null;
    validation_warnings?: readonly string[];
    assay_context?: {
      species?: string;
      cell_type_or_line?: string;
      permeabilized?: boolean;
      fixation?: string;
    };
  };
  const e = ev as EvidenceLite;
  const warnings = e.validation_warnings ?? [];

  // The agent emits the source PMC even when the entailment auditor
  // rejects the verbatim quote (and so the span gets dropped). Pull
  // PMC IDs out of any validation_warning so the drawer still shows
  // *which paper* the claim is anchored to, even without a verifiable
  // quote — otherwise the reader sees a bare claim with no source.
  if (!sources.length && warnings.length) {
    for (const w of warnings) {
      const matches = w.match(/PMC\d{4,}/g);
      if (!matches) continue;
      for (const pmcId of matches) {
        if (seenKeys.has(`pmc:${pmcId}`)) continue;
        seenKeys.add(`pmc:${pmcId}`);
        sources.push({
          href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${pmcId}/`,
          label: pmcId,
          title: "Recovered from validation warning (quote not verifiable)",
        });
      }
    }
  }

  return (
    <div className={styles.drawerCard}>
      <button
        type="button"
        className={styles.closeBtn}
        onClick={onClose}
        aria-label="Close evidence panel"
      >
        ×
      </button>
      <p className={`label-mono ${styles.eyebrow}`}>{ev.evidence_id}</p>
      <div className={styles.badges}>
        <StatusPill tone={tierTone(ev.evidence_tier)} size="sm">
          {prettyEnum(ev.evidence_tier)}
        </StatusPill>
        {e.evidence_type ? (
          <StatusPill tone="teal" size="sm">
            {prettyEnum(e.evidence_type)}
          </StatusPill>
        ) : null}
        {e.direction ? (
          <StatusPill
            tone={e.direction === "supports" ? "success" : "neutral"}
            size="sm"
          >
            {e.direction}
          </StatusPill>
        ) : null}
        {e.confidence ? (
          <StatusPill tone="lavender" size="sm">
            conf · {e.confidence}
          </StatusPill>
        ) : null}
        {e.entailment_verified ? (
          <StatusPill tone="success" size="sm">
            entailment ✓
          </StatusPill>
        ) : warnings.length || e.entailment_audit_passed === false ? (
          <StatusPill tone="amber" size="sm">
            quote unverified
          </StatusPill>
        ) : null}
      </div>
      <h2 className={styles.title}>Agent&apos;s claim</h2>
      <p className={styles.claim}>{ev.claim}</p>
      {headSpan?.text ? (
        <>
          <h3 className={styles.subhead}>Verbatim quote</h3>
          <blockquote className={styles.quote}>{headSpan.text}</blockquote>
        </>
      ) : warnings.length ? (
        <>
          <h3 className={styles.subhead}>Verbatim quote</h3>
          <p className={styles.warningNote}>
            The agent&apos;s quoted text could not be re-located in the source
            after normalization, so the span was dropped by the entailment
            auditor. The claim is shown above; the source paper is linked
            below — verify against the source directly.
          </p>
          <ul className={styles.warningList}>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </>
      ) : null}
      {e.assay_context ? (
        <>
          <h3 className={styles.subhead}>Assay context</h3>
          <dl className={styles.meta}>
            {e.assay_context.species ? (
              <div className={styles.metaItem}>
                <dt className="label-mono">Species</dt>
                <dd>{e.assay_context.species}</dd>
              </div>
            ) : null}
            {e.assay_context.cell_type_or_line ? (
              <div className={styles.metaItem}>
                <dt className="label-mono">Cell type / line</dt>
                <dd>{e.assay_context.cell_type_or_line}</dd>
              </div>
            ) : null}
            {e.assay_context.permeabilized != null ? (
              <div className={styles.metaItem}>
                <dt className="label-mono">Permeabilized</dt>
                <dd>{e.assay_context.permeabilized ? "yes" : "no"}</dd>
              </div>
            ) : null}
            {e.assay_context.fixation ? (
              <div className={styles.metaItem}>
                <dt className="label-mono">Fixation</dt>
                <dd>{e.assay_context.fixation}</dd>
              </div>
            ) : null}
          </dl>
        </>
      ) : null}
      {sources.length ? (
        <>
          <h3 className={styles.subhead}>Source{sources.length > 1 ? "s" : ""}</h3>
          <ul className={styles.sources}>
            {sources.map((s) => (
              <li key={s.href}>
                <a
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.sourceLink}
                  title={s.title}
                >
                  {s.label} ↗
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function tierTone(t: string) {
  if (t === "primary") return "success" as const;
  if (t === "secondary") return "teal" as const;
  return "neutral" as const;
}
