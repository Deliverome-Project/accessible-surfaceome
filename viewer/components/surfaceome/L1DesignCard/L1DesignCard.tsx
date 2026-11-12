"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import {
  fetchL1Design,
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

const STATUS_TITLE: Record<L1Site["status"], string> = {
  built: "A tagged construct has been designed and checked for this site.",
  proposed: "A site (or leader) is chosen; the construct is not built yet.",
  held: "Held, refused or flagged by the design review; see the detail.",
};

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
      {m.sites.length ? (
        <div className={styles.tablewrap}>
          <table className={styles.table}>
            <thead>
              <tr><th>Site</th><th>Insertion</th><th>Leader</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {m.sites.map((s) => (
                <tr key={s.site_id}>
                  <td className={styles.mono}>{s.rank != null ? `#${s.rank} ` : ""}{s.site_id}</td>
                  <td>{l1SiteLabel(s, m.ordered_length_aa)}</td>
                  <td>{s.leader === "igk" ? "Igκ" : "—"}</td>
                  <td><span className={`${styles.pill} ${styles["s_" + s.status]}`} title={STATUS_TITLE[s.status]}>{s.status}</span></td>
                  <td><Provenance site={s} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={styles.muted}>No tag site suggested for this member yet.</p>
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

export function L1DesignCard({ symbol, n }: { symbol: string; n: number }) {
  const [data, setData] = useState<L1DesignFile | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "none">("loading");
  useEffect(() => {
    let live = true;
    setState("loading");
    fetchL1Design(symbol, API_BASE).then((d) => {
      if (!live) return;
      setData(d);
      setState(d && d.members.length ? "ok" : "none");
    });
    return () => {
      live = false;
    };
  }, [symbol]);

  return (
    <SectionCard
      n={n}
      eyebrow="Library design"
      title="L1 library design"
      meta="Suggested tag sites and folded models for each L1 member. Residues are in the member's own numbering."
    >
      <div className={styles.root}>
        {state === "loading" && <p className={styles.muted}>Loading…</p>}
        {state === "none" && <p className={styles.muted}>No L1 design is published for {symbol} yet.</p>}
        {state === "ok" && data && (
          <>
            {data.members.map((m) => <L1MemberBlock key={m.member_id} m={m} />)}
            {data.load ? (
              <p className={`${styles.muted} ${styles.mono}`}>load {data.load.load_version} · {data.load.created_at}</p>
            ) : null}
          </>
        )}
      </div>
    </SectionCard>
  );
}
