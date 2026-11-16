"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import { ChipLabelValue } from "../ChipLabelValue/ChipLabelValue";
import { EvidenceChipList, linkifyEvidenceRefs } from "../EvidenceChip/EvidenceChip";
import { prettyEnum } from "../../../lib/enums";
import type { CoReceptorRequirements } from "../../../lib/surfaceome-types";
import {
  STATUS_HELP,
  STATUS_LABEL,
  sortSites,
  fetchL1DesignResult,
  l1AbsenceReason,
  l1SiteLabel,
  l1StructureUrl,
  type L1DesignFile,
  type L1Member,
  type L1Site,
  type L1Structure,
} from "../../../lib/l1-design";
import styles from "./L1DesignCard.module.css";

// Same Worker base the other client-fetched cards use. NEXT_PUBLIC_L1_DESIGN_API_BASE
// points only this card elsewhere (a local `wrangler dev` holding a candidate load),
// so a load can be previewed on real gene pages before it reaches production D1.
const API_BASE =
  process.env.NEXT_PUBLIC_L1_DESIGN_API_BASE ??
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ??
  "https://api.deliverome.org/surfaceome";


function setLabel(m: L1Member): string {
  const set = (m.candidate_set ?? "").replace(/_/g, " ");
  return m.species && m.species !== "human" ? `${m.species} ${set}` : set;
}

function Provenance({ site }: { site: L1Site }) {
  return (
    <details className={styles.prov}>
      <summary>why · who</summary>
      <dl>
        {site.status_detail ? (<><dt>detail</dt><dd>{site.status_detail}</dd></>) : null}
        {site.reason ? (<><dt>reason</dt><dd>{site.reason}</dd></>) : null}
        {site.rejected_alternative ? (<><dt>rejected alternative</dt><dd>{site.rejected_alternative}</dd></>) : null}
        <dt>decided by</dt><dd>{site.decided_by}</dd>
        <dt>implemented by</dt><dd>{site.implemented_by}</dd>
        <dt>source</dt>
        <dd className={styles.mono}>
          {site.source.pr != null ? `PR ${site.source.pr}${site.source.pr_state ? ` (${site.source.pr_state})` : ""} · ` : ""}
          {site.source.commit.slice(0, 8)} · {site.source.path}
        </dd>
      </dl>
    </details>
  );
}

function modelLabel(s: L1Structure): string {
  const src = s.source === "alphafold_db" ? "AlphaFold DB" : s.source === "colabfold" ? "ColabFold" : "ColabFold (tagged)";
  const plddt = s.mean_plddt != null ? `, pLDDT ${s.mean_plddt.toFixed(0)}` : "";
  if (s.kind === "tagged") {
    const span = s.cassette_first_model_residue != null && s.cassette_last_model_residue != null
      ? `, cassette ${s.cassette_first_model_residue}–${s.cassette_last_model_residue}` : "";
    return `Tagged refold${s.site_id ? ` (${s.site_id})` : ""}: ${src}${plddt}${span}`;
  }
  return `${s.is_chosen ? "Native model" : "Alternate (not used)"}: ${src}${plddt}`;
}

export function L1MemberBlock({ m }: { m: L1Member }) {
  const models = m.structures.filter((s) => s.is_chosen || s.kind === "native");
  return (
    <div className={styles.member}>
      <div className={styles.memberHead}>
        <span className={styles.memberId}>{m.member_id}</span>
        {m.design_id ? <span className={`${styles.mono} ${styles.muted}`}>{m.design_id}</span> : null}
        <span className={styles.badge}>{setLabel(m)}</span>
        <span className={styles.badge}>{m.rung}</span>
        {m.ordered_length_aa != null ? <span className={styles.muted}>{m.ordered_length_aa} aa</span> : null}
      </div>
      {m.sites.some((s) => s.is_primary !== false) ? (
        <div className={styles.tablewrap}>
          <table className={styles.table}>
            <thead>
              <tr><th>Site</th><th>Insertion</th><th>Leader</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {sortSites(m.sites).filter((s) => s.is_primary !== false).map((s) => (
                <tr key={s.site_id}>
                  <td className={styles.mono}>{s.rank != null ? `#${s.rank} ` : ""}{s.site_id}</td>
                  <td>{l1SiteLabel(s, m.ordered_length_aa)}</td>
                  <td>{s.leader === "igk" ? "Igκ" : "—"}</td>
                  <td><span className={`${styles.pill} ${styles["s_" + s.status]}`} title={STATUS_HELP[s.status]}>{STATUS_LABEL[s.status]}</span></td>
                  <td><Provenance site={s} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={styles.muted}>No tag site recorded for this member yet.</p>
      )}
      {models.length ? (
        <div className={styles.models}>
          {models.map((s) => {
            const url = l1StructureUrl(s);
            return url ? (
              <a key={s.structure_id} href={url} target="_blank" rel="noreferrer">{modelLabel(s)}</a>
            ) : (
              <span key={s.structure_id} className={styles.muted}>{modelLabel(s)}</span>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Why the gene has no L1 design — the obligate-partner case.
 *
 * Reads the gene record the page already holds; there is no L1-side table of
 * exclusions to query. Says what the record says (dependency, partners,
 * rationale, references) and names the criterion the L1 cohort filter applies,
 * without claiming to have re-run the filter: the record does not carry the
 * partner's cell-line expression, which is what the gate actually tests.
 */
export function ObligatePartnerAbsence({
  symbol,
  cr,
}: {
  symbol: string;
  cr: CoReceptorRequirements;
}) {
  const partners = (cr.partners ?? []).filter((x) => x.trim());
  return (
    <div className={styles.absence}>
      <p className={styles.absenceLede}>
        <strong>{symbol} is not an L1 library member</strong>, so no tag site or folded
        model was designed for it.
      </p>
      <div className={styles.absenceChips}>
        <StatusPill tone="danger" size="sm">
          <ChipLabelValue label="partner for expression" value={prettyEnum(cr.surface_expression_dependency)} />
        </StatusPill>
        <StatusPill tone="lavender" size="sm">
          <ChipLabelValue label="evidence basis" value={prettyEnum(cr.evidence_basis)} />
        </StatusPill>
        <EvidenceChipList ids={cr.cited_evidence_ids ?? []} label="References" />
      </div>
      {partners.length ? (
        <p>
          <span className={`label-mono ${styles.muted}`}>Obligate partners</span>{" "}
          {partners.join(", ")}
        </p>
      ) : null}
      <p className={styles.muted}>
        The library leaves out a gene whose obligate partner the host cell line does not
        express: the ORF delivered on its own would not be surface-displayed. Check the
        partners above against the host line before reading this as a gap in the design
        work.
      </p>
      {cr.rationale ? <p>{linkifyEvidenceRefs(cr.rationale)}</p> : null}
    </div>
  );
}

export function L1DesignCard({
  symbol,
  n,
  inFgLibrary = true,
  coReceptor = null,
}: {
  symbol: string;
  n: number;
  /** Library membership, from the page's FG-library overlay. A non-member has
   *  no design by construction, which is a different statement from a member
   *  whose design has not been published yet. */
  inFgLibrary?: boolean;
  /** ``accessibility_risks.co_receptor_requirements`` — the canonical home of
   *  the dependency (``filters.co_receptor_dependency`` is only a mirror, and
   *  is absent on pre-mirror records). */
  coReceptor?: CoReceptorRequirements | null;
}) {
  const [data, setData] = useState<L1DesignFile | null>(null);
  // "error" is deliberately distinct from "empty": a failed fetch must never
  // render as "no design is published", which is what the single `none` state
  // used to do for every miss, outage and shape change alike.
  const [state, setState] = useState<"loading" | "ok" | "empty" | "error">("loading");
  useEffect(() => {
    let live = true;
    setState("loading");
    fetchL1DesignResult(symbol, API_BASE).then((r) => {
      if (!live) return;
      setData(r.kind === "ok" ? r.file : null);
      setState(r.kind);
    });
    return () => {
      live = false;
    };
  }, [symbol]);

  const absence = l1AbsenceReason({ inFgLibrary, coReceptor });
  const excluded = state !== "loading" && state !== "ok" && absence === "obligate_partner";

  return (
    <SectionCard
      n={n}
      eyebrow="Library design"
      title="L1 library design"
      meta={
        excluded
          ? "Why this gene has no L1 design."
          : "Suggested tag sites and folded models for each L1 member. Residues are in the member's own numbering."
      }
    >
      <div className={styles.root}>
        {state === "loading" && <p className={styles.muted}>Loading…</p>}
        {excluded && coReceptor && <ObligatePartnerAbsence symbol={symbol} cr={coReceptor} />}
        {state === "error" && (
          <p className={styles.fetchFailed}>
            The L1 design load could not be fetched. This is a failure of the design API,
            not a statement about {symbol} — reload to try again.
          </p>
        )}
        {state === "empty" && !excluded && (
          <p className={styles.muted}>
            No L1 design is published for {symbol} yet.
            {inFgLibrary
              ? " It is an L1 library member, so this is a gap in the published load rather than an exclusion."
              : " It is not an L1 library member, and its record gives no reason that explains the absence."}
          </p>
        )}
        {state === "ok" && data && (
          <>
            {data.members.map((m) => <L1MemberBlock key={m.member_id} m={m} />)}
            <p className={styles.muted}>
              Alternatives, scores and contact sites:{" "}
              <a href={`/l1-review/?q=${encodeURIComponent(symbol)}&m=${encodeURIComponent(data.members[0]?.design_id ?? "")}`}>L1 review page</a>
            </p>
            {data.load ? (
              <p className={`${styles.muted} ${styles.mono}`}>load {data.load.load_version} · {data.load.created_at}</p>
            ) : null}
          </>
        )}
      </div>
    </SectionCard>
  );
}
