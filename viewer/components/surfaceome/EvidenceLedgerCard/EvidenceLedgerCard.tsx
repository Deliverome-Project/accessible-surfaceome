import type {
  Evidence,
  EvidenceTier,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
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

function sourceLink(e: Evidence) {
  const s = e.source;
  if (s.url) return { href: s.url, label: s.url };
  if (s.doi) return { href: `https://doi.org/${s.doi}`, label: `doi:${s.doi}` };
  if (s.pmcid) {
    return {
      href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${s.pmcid}/`,
      label: s.pmcid,
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
    if (e.source.pmcid) pmcOa += 1;
  }
  const total = rec.evidence.length;

  return (
    <SectionCard
      n={n}
      eyebrow="Evidence ledger"
      title={
        <>
          The <em>citations</em>
        </>
      }
      meta={`${total} entries · ${primary} primary · ${secondary} secondary · ${tertiary} tertiary · ${pmcOa} PMC OA`}
    >
      {total === 0 ? (
        <p className={styles.empty}>No evidence entries recorded.</p>
      ) : (
        <details className={styles.details}>
          <summary className={styles.summary}>
            Show {total} entr{total === 1 ? "y" : "ies"}
          </summary>
          <ul className={styles.list}>
            {rec.evidence.map((e) => {
              const link = sourceLink(e);
              const firstSpan = e.spans[0]?.text ?? null;
              return (
                <li key={e.evidence_id} className={styles.item}>
                  <div className={styles.head}>
                    <span className={styles.id}>{e.evidence_id}</span>
                    <StatusPill tone={tierTone(e.evidence_tier)} size="sm">
                      {prettyEnum(e.evidence_tier)}
                    </StatusPill>
                    {e.entailment_verified ? (
                      <StatusPill tone="success" size="sm">
                        entailment ✓
                      </StatusPill>
                    ) : null}
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
