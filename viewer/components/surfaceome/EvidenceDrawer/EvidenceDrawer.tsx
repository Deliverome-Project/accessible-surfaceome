"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  Evidence,
  PaperMetadata,
  PaperMetadataMap,
} from "../../../lib/surfaceome-types";
import {
  scrubAgentJargon,
  scrubEvidenceTokens,
  stripInlineHtml,
} from "../../../lib/textScrub";
import { bylineOf } from "../../../lib/paperCitation";
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

/** Reader-facing label for an evidence id. Mirrors the EvidenceChip
 *  helper — strip the ``evi_`` (or legacy ``a[12]_evi_``) prefix so
 *  the drawer's eyebrow shows just the bare number. */
function prettyEvidenceLabel(evidenceId: string): string {
  const newForm = /^evi_(\d+)$/.exec(evidenceId);
  if (newForm) return newForm[1];
  const legacyForm = /^a[12]_evi_(\d+)$/.exec(evidenceId);
  if (legacyForm) return legacyForm[1];
  return evidenceId;
}

/** Compose the two viewer-side scrubbers — strip ``aN_evi_NN`` annotation
 *  tokens AND rewrite "A1 ledger" / "the merged A1+A2 evidence" / etc.
 *  prose jargon — so reader-facing strings in the drawer never carry
 *  internal pipeline namespace. Used on the agent's claim + verbatim
 *  quote where the chip-linkify path isn't appropriate (the
 *  ``cited_evidence_ids`` strip below the prose is the right surface
 *  for that). */
function cleanDrawerProse(text: string | null | undefined): string {
  return stripInlineHtml(scrubEvidenceTokens(scrubAgentJargon(text)));
}
import styles from "./EvidenceDrawer.module.css";

interface EvidenceDrawerProps {
  evidence: readonly Evidence[];
  /** `source_id` → NCBI citation metadata, from the evidence endpoint's
   *  `papers` map. Omitted on the offline-snapshot path (the committed
   *  JSON carries identifiers only), in which case each source falls back
   *  to the bare accession link. */
  papers?: PaperMetadataMap;
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
export function EvidenceDrawer({ evidence, papers }: EvidenceDrawerProps) {
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
    // Explicit collapse signal. Fired by the ReasoningDrawer when the
    // reader clicks anywhere inside it that *isn't* an evidence chip —
    // so an expanded evidence panel auto-collapses instead of lingering
    // over the prose the reader has moved on to.
    function onCloseEvt() {
      setOpenId(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenId(null);
    }
    window.addEventListener("surfaceome:open-evidence", onOpen);
    window.addEventListener("surfaceome:close-evidence", onCloseEvt);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("surfaceome:open-evidence", onOpen);
      window.removeEventListener("surfaceome:close-evidence", onCloseEvt);
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
        {data ? (
          <EvidenceCard
            ev={data}
            papers={papers}
            onClose={() => setOpenId(null)}
          />
        ) : null}
      </aside>
    </>
  );
}

/** One deduped citation the drawer can link to. `meta` is present only
 *  when the evidence endpoint carried NCBI metadata for this source_id. */
export interface SourceEntry {
  href: string;
  label: string;
  /** Tooltip text, for the cases where the label alone is opaque (a raw
   *  URL) or the source was recovered from a validation warning. */
  title?: string;
  meta?: PaperMetadata;
}

/** The drawer's citation list. With metadata the title leads and the
 *  accession trails as a secondary marker; without it the accession stays
 *  the link text exactly as it did before this metadata path existed — so
 *  a paper missing from `paper_metadata`, or the whole offline-snapshot
 *  path, degrades to the previous rendering rather than to a blank.
 *
 *  Exported for the render test: the card it lives in only mounts in
 *  response to a window event, so this is the seam the citation rendering
 *  is asserted through. */
export function SourceList({ sources }: { sources: readonly SourceEntry[] }) {
  return (
    <ul className={styles.sources}>
      {sources.map((s) => (
        <li key={s.href}>
          {s.meta?.title ? (
            <div className={styles.sourceCite}>
              <a
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.sourceTitle}
              >
                {s.meta.title}
              </a>
              <p className={styles.sourceByline}>
                {bylineOf(s.meta) ? <>{bylineOf(s.meta)} · </> : null}
                <span className={styles.sourceAccession}>{s.label} ↗</span>
              </p>
            </div>
          ) : (
            <a
              href={s.href}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.sourceLink}
              title={s.title}
            >
              {s.label} ↗
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

function EvidenceCard({
  ev,
  papers,
  onClose,
}: {
  ev: Evidence;
  papers?: PaperMetadataMap;
  onClose: () => void;
}) {
  // The v1 schema carries verbatim quotes + source per *span* (each
  // evidence claim can be anchored to multiple spans across one or
  // more sources). Surface the head span's quote + walk the spans for
  // distinct sources to show all citation links. Pydantic field name
  // is ``quote`` (the older TS interface said ``text`` — that's been
  // corrected in surfaceome-types.ts).
  type SpanWithSource = {
    quote?: string;
    source?: {
      source_id?: string;
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
  const sources: SourceEntry[] = [];
  for (const sp of spans) {
    const s = sp?.source;
    if (!s) continue;
    // Pydantic ``SourceRef`` carries the PMID inside ``source_id`` as
    // a string like ``"PMID:41818370"``; the dedicated ``pmid`` field
    // may or may not be set. Same for PMC. Parse defensively.
    const sid = s.source_id ?? "";
    const pmidFromSid = sid.startsWith("PMID:") ? sid.slice(5) : null;
    const pmcFromSid = sid.startsWith("PMC:") ? sid.slice(4) : null;
    const pmcId = s.pmc_id ?? pmcFromSid;
    const pmid = s.pmid ?? pmidFromSid;
    // Citation metadata is keyed on the VERBATIM ``source_id`` — the same
    // string the Worker looked up in ``paper_metadata`` — so no
    // normalization step can mis-key it. Undefined whenever the paper
    // isn't in the table or the whole map is absent (snapshot path).
    const meta = sid ? papers?.[sid] : undefined;
    if (pmcId && !seenKeys.has(`pmc:${pmcId}`)) {
      seenKeys.add(`pmc:${pmcId}`);
      sources.push({
        href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${pmcId}/`,
        label: pmcId,
        meta,
      });
    } else if (pmid && !seenKeys.has(`pmid:${pmid}`)) {
      seenKeys.add(`pmid:${pmid}`);
      sources.push({
        href: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
        label: `PMID ${pmid}`,
        meta,
      });
    } else if (s.doi && !seenKeys.has(`doi:${s.doi}`)) {
      seenKeys.add(`doi:${s.doi}`);
      sources.push({
        href: `https://doi.org/${s.doi}`,
        label: `doi:${s.doi}`,
        meta,
      });
    } else if (s.url && !seenKeys.has(`url:${s.url}`)) {
      seenKeys.add(`url:${s.url}`);
      sources.push({
        href: s.url,
        label: s.url.replace(/^https?:\/\//, "").slice(0, 48),
        title: s.url,
        meta,
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
          // The warning yields a bare accession; `paper_metadata` is keyed
          // on the `SourceRef.source_id` form, which for PMC is always the
          // accession behind a `PMC:` scheme. Reconstructing it means an
          // entailment-failed claim still names its paper in full.
          meta: papers?.[`PMC:${pmcId}`],
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
      <p className={`label-mono ${styles.eyebrow}`}>
        {prettyEvidenceLabel(ev.evidence_id)}
      </p>
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
        {/* entailment_verified / audit_passed / validation_warnings
         *  chips removed per UX request — the substring check still
         *  runs in the pipeline and the result lands on the record
         *  for audit, but the reader-facing chip strip stays clean.
         *  PMC ID recovery from validation_warnings (above) still
         *  fires so entailment-failed claims still get a source link. */}
      </div>
      <h2 className={styles.title}>Agent&apos;s claim</h2>
      <p className={styles.claim}>{cleanDrawerProse(ev.claim)}</p>
      {headSpan?.quote ? (
        <>
          {/* Source sits right above the verbatim it anchors so the
              reader can confirm "this quote came from THAT paper" in
              one glance. */}
          {sources.length ? (
            <>
              <h3 className={styles.subhead}>
                Source{sources.length > 1 ? "s" : ""}
              </h3>
              <SourceList sources={sources} />
            </>
          ) : null}
          <h3 className={styles.subhead}>Verbatim quote</h3>
          <blockquote className={styles.quote}>
            {cleanDrawerProse(headSpan.quote)}
          </blockquote>
        </>
      ) : sources.length ? (
        // No verbatim quote — surface the source on its own so the
        // reader still has the "which paper?" anchor.
        <>
          <h3 className={styles.subhead}>
            Source{sources.length > 1 ? "s" : ""}
          </h3>
          <SourceList sources={sources} />
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
    </div>
  );
}

function tierTone(t: string) {
  if (t === "primary") return "success" as const;
  if (t === "secondary") return "teal" as const;
  return "neutral" as const;
}
