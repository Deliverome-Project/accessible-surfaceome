import type {
  Evidence,
  EvidenceTier,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import {
  scrubAgentJargon,
  scrubEvidenceTokens,
  stripInlineHtml,
} from "../../../lib/textScrub";
import { EvidenceChip, defaultEvidenceLabel } from "../EvidenceChip/EvidenceChip";
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
  // Prefer a clean identifier label (PMC* / PMID) over the raw URL.
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
  if (s.url) {
    // No structured id — pull a PMC*/PMID out of the URL itself so the
    // chip reads as the article name, not the whole link. Fall back to
    // the raw URL only when neither is present.
    const url = s.url as string;
    const pmc = url.match(/PMC\d+/i)?.[0];
    if (pmc) return { href: url, label: pmc.toUpperCase() };
    const urlPmid = url.match(/pubmed\.ncbi\.nlm\.nih\.gov\/(\d+)/i)?.[1];
    if (urlPmid) return { href: url, label: `PMID ${urlPmid}` };
    return { href: url, label: url };
  }
  if (s.doi) return { href: `https://doi.org/${s.doi}`, label: `doi:${s.doi}` };
  return null;
}

export function EvidenceLedgerCard({ rec, n }: Props) {
  // Group entries by canonical id so cross-planner duplicates (A1 and
  // A2 both extracted the same paper/span — flagged by the orchestrator
  // with `duplicate_of=<canonical>`) collapse onto ONE card with both
  // planner interpretations stacked underneath. Without this fold the
  // ledger lists what looks like two separate citations of the same
  // source, which confuses the reader.
  const byCanonical: Record<string, { canonical: Evidence; dupes: Evidence[] }> = {};
  // First pass: register canonicals (entries that ARE the canonical,
  // or that don't participate in any cluster).
  for (const e of rec.evidence) {
    if (!e.duplicate_of) {
      byCanonical[e.evidence_id] = { canonical: e, dupes: [] };
    }
  }
  // Second pass: attach duplicates to their canonical's cluster. If
  // a canonical id is missing (pre-dedup record / pathological data),
  // fall back to listing the duplicate as its own card so the entry
  // doesn't vanish.
  for (const e of rec.evidence) {
    if (e.duplicate_of) {
      const cluster = byCanonical[e.duplicate_of];
      if (cluster) {
        cluster.dupes.push(e);
      } else {
        byCanonical[e.evidence_id] = { canonical: e, dupes: [] };
      }
    }
  }
  const clusters = Object.values(byCanonical);

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
  const totalEntries = rec.evidence.length;
  const totalUnique = clusters.length;
  const totalDupes = totalEntries - totalUnique;
  // Meta string adapts to whether dedup actually folded anything —
  // for genes with no cross-planner overlap the old wording stays
  // ("N entries"); for folded ledgers we surface the relationship.
  const headerMeta =
    totalDupes > 0
      ? `${totalUnique} unique sources (${totalEntries} total planner extractions, ${totalDupes} folded as duplicates) · ${primary} primary · ${secondary} secondary · ${tertiary} tertiary · ${pmcOa} PMC OA`
      : `${totalEntries} entries · ${primary} primary · ${secondary} secondary · ${tertiary} tertiary · ${pmcOa} PMC OA`;

  return (
    <SectionCard
      n={n}
      eyebrow="Evidence ledger"
      title="Evidence ledger"
      meta={headerMeta}
    >
      {totalEntries === 0 ? (
        <p className={styles.empty}>No evidence entries recorded.</p>
      ) : (
        <ul className={styles.list}>
            {clusters.map(({ canonical: e, dupes }) => {
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
                      title={`Open evidence ${defaultEvidenceLabel(e.evidence_id)} — ${e.claim.slice(0, 80)}…`}
                    />
                    <StatusPill tone={tierTone(e.evidence_tier)} size="sm">
                      {prettyEnum(e.evidence_tier)}
                    </StatusPill>
                    {/* Surface the cross-planner fold count when this
                     *  cluster has duplicates. Each chip in the list
                     *  still opens the per-id drawer so readers can
                     *  inspect the alternate planner's framing.
                     *  entailment_verified chip removed per UX request. */}
                    {dupes.length > 0 ? (
                      <span className={styles.dupCount}>
                        also cited as{" "}
                        {dupes.map((d, i) => (
                          <span key={d.evidence_id}>
                            {i > 0 ? ", " : null}
                            <EvidenceChip
                              evidenceId={d.evidence_id}
                              title={`Open ${defaultEvidenceLabel(d.evidence_id)} — ${d.claim.slice(0, 80)}…`}
                            />
                          </span>
                        ))}
                      </span>
                    ) : null}
                  </div>
                  {/* Same scrub composer the drawer uses — strip
                   *  internal a1/a2 prose jargon + `aN_evi_NN` annotation
                   *  tokens + JATS-extracted `<i>` / `<b>` tags so the
                   *  ledger preview reads clean too. */}
                  <p className={styles.claim}>
                    {stripInlineHtml(scrubEvidenceTokens(scrubAgentJargon(e.claim)))}
                  </p>
                  {firstSpan ? (
                    <p className={styles.span}>
                      &ldquo;
                      {stripInlineHtml(scrubEvidenceTokens(firstSpan))}
                      &rdquo;
                    </p>
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
                  {/* Alternate planner interpretations for the same
                   *  source span. Shown as compact sub-rows so the
                   *  reader sees "A2 framed this as: ..." without
                   *  flooding the ledger with parallel cards. */}
                  {dupes.length > 0 ? (
                    <ul className={styles.dupList}>
                      {dupes.map((d) => (
                        <li key={d.evidence_id} className={styles.dupItem}>
                          <span className={`label-mono ${styles.dupLabel}`}>
                            {d.evidence_id} interpretation
                          </span>
                          <p className={styles.dupClaim}>{d.claim}</p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              );
            })}
        </ul>
      )}
    </SectionCard>
  );
}
