import type {
  Evidence,
  EvidenceTier,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChip } from "../EvidenceChip/EvidenceChip";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./EvidenceLedgerCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function tierTone(t: EvidenceTier) {
  if (t === "primary") return "success" as const;
  if (t === "secondary") return "teal" as const;
  return "neutral" as const;
}

// Schema-tolerant source extraction.
// v1.0.0 records: evidence[i].spans[j].source carries pmc_id / pmid / doi / url
//   (snake_case, multiple spans per evidence claim).
// Legacy records: evidence[i].source carries pmcid / pmid / doi / url
//   (single, top-level).
function firstSource(e: Evidence): Record<string, unknown> | null {
  type LegacyEvidence = Evidence & { source?: Record<string, unknown> };
  type SpanWithSource = { source?: Record<string, unknown> };
  if (Array.isArray(e.spans) && e.spans.length) {
    for (const sp of e.spans as unknown as SpanWithSource[]) {
      if (sp?.source) return sp.source;
    }
  }
  const legacy = (e as LegacyEvidence).source;
  return legacy ?? null;
}
function pmcIdOf(src: Record<string, unknown> | null): string | null {
  if (!src) return null;
  return (src.pmc_id as string | undefined) ?? (src.pmcid as string | undefined) ?? null;
}
function sourceLink(e: Evidence) {
  const s = firstSource(e);
  if (!s) return null;
  if (s.url) return { href: s.url as string, label: s.url as string };
  if (s.doi) return { href: `https://doi.org/${s.doi}`, label: `doi:${s.doi}` };
  const pmcId = pmcIdOf(s);
  if (pmcId) {
    return {
      href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${pmcId}/`,
      label: pmcId,
    };
  }
  if (s.pmid) {
    return {
      href: `https://pubmed.ncbi.nlm.nih.gov/${s.pmid}/`,
      label: `PMID ${s.pmid}`,
    };
  }
  return null;
}

export function EvidenceLedgerCard({ rec, n }: Props) {
  let primary = 0;
  let secondary = 0;
  let tertiary = 0;
  let pmcOa = 0;
  for (const e of rec.evidence) {
    if (e.evidence_tier === "primary") primary += 1;
    else if (e.evidence_tier === "secondary") secondary += 1;
    else if (e.evidence_tier === "tertiary") tertiary += 1;
    if (pmcIdOf(firstSource(e))) pmcOa += 1;
  }
  const total = rec.evidence.length;

  return (
    <SectionCard
      n={n}
      eyebrow="Evidence ledger"
      title="Evidence ledger"
      meta={`${total} entries · ${primary} primary · ${secondary} secondary · ${tertiary} tertiary · ${pmcOa} PMC OA`}
    >
      {total === 0 ? (
        <p className={styles.empty}>No evidence entries recorded.</p>
      ) : (
        <details className={styles.details} open>
          <summary className={styles.summary}>
            {total} entr{total === 1 ? "y" : "ies"} · click to collapse
          </summary>
          <ul className={styles.list}>
            {rec.evidence.map((e) => {
              const link = sourceLink(e);
              const firstSpan = e.spans[0]?.quote ?? null;
              return (
                <li key={e.evidence_id} className={styles.item}>
                  <div className={styles.head}>
                    {/* The evidence_id pill IS the chip — click to open
                     *  the global EvidenceDrawer with full claim +
                     *  quote + sources, same drawer the per-section
                     *  chip strips open. */}
                    <EvidenceChip
                      evidenceId={e.evidence_id}
                      title={`Open evidence ${e.evidence_id} — ${e.claim.slice(0, 80)}…`}
                    />
                    <StatusPill tone={tierTone(e.evidence_tier)} size="sm">
                      {prettyEnum(e.evidence_tier)}
                    </StatusPill>
                    {/* entailment_verified chip removed per UX request —
                     *  the pipeline still runs the substring check (and
                     *  records the bool on the record for audit), it's
                     *  just not surfaced as a reader-facing badge. */}
                  </div>
                  <p className={styles.claim}>{e.claim}</p>
                  {firstSpan ? (
                    <p className={styles.span}>&ldquo;{firstSpan}&rdquo;</p>
                  ) : null}
                  {link ? (
                    <a
                      className={styles.link}
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {link.label}
                    </a>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </SectionCard>
  );
}
