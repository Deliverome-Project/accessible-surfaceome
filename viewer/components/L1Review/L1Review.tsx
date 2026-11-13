"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  PLACEMENT_LABEL,
  SOURCE_LABEL,
  STATUS_HELP,
  STATUS_LABEL,
  countBy,
  fetchL1Design,
  fetchL1Index,
  fetchL1Reviews,
  filterIndex,
  l1SiteLabel,
  l1StructureUrl,
  latestVerdicts,
  modelToMemberResidue,
  sortSites,
  submitL1Review,
  visibleContacts,
  type L1Contact,
  type L1DesignFile,
  type L1Index,
  type L1IndexMember,
  type L1Member,
  type L1Placement,
  type L1Reviews,
  type L1Site,
  type L1Structure,
} from "../../lib/l1-design";
import { L1Structure3D, type L1Mark } from "./L1Structure3D";
import { curatedContactsAlign, fetchCuratedContacts, type CuratedContacts as CuratedContactsData } from "../../lib/l1-design";
import styles from "./L1Review.module.css";

// Same Worker base the other client-fetched pages use; NEXT_PUBLIC_L1_DESIGN_API_BASE
// points only the L1 surfaces at another Worker (a local `wrangler dev`) for previews.
const API_BASE =
  process.env.NEXT_PUBLIC_L1_DESIGN_API_BASE ??
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ??
  "https://api.deliverome.org/surfaceome";

export const COLORS = {
  pick: "#B3243B",
  ranker: "#E0A100",
  agent: "#3F7FBF",
  litHigh: "#14967F",
  litLower: "#7CC9BA",
  uniprot: "#6B7280",
  suggestion: "#FF1F8F",
  curated: "#E8590C",
};

const store = {
  get(k: string): string {
    try {
      return window.localStorage.getItem(k) ?? "";
    } catch {
      return "";
    }
  },
  set(k: string, v: string) {
    try {
      window.localStorage.setItem(k, v);
    } catch {
      /* private window: keep it in memory only */
    }
  },
};

function readUrl(): { m: string; rung: string; cls: string; status: string; q: string } {
  if (typeof window === "undefined") return { m: "", rung: "", cls: "", status: "", q: "" };
  const p = new URLSearchParams(window.location.search);
  return { m: p.get("m") ?? "", rung: p.get("rung") ?? "", cls: p.get("class") ?? "", status: p.get("status") ?? "", q: p.get("q") ?? "" };
}

function writeUrl(s: { m: string; rung: string; cls: string; status: string; q: string }) {
  const p = new URLSearchParams();
  if (s.m) p.set("m", s.m);
  if (s.rung) p.set("rung", s.rung);
  if (s.cls) p.set("class", s.cls);
  if (s.status) p.set("status", s.status);
  if (s.q) p.set("q", s.q);
  const qs = p.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
}

function StatusPill({ status }: { status: L1Site["status"] }) {
  return (
    <span className={`${styles.pill} ${styles[`s_${status}`]}`} title={STATUS_HELP[status]}>
      {STATUS_LABEL[status]}
    </span>
  );
}

function siteColor(s: L1Site): string {
  if (s.is_primary !== false) return COLORS.pick;
  return s.site_source === "agent_proposer" ? COLORS.agent : COLORS.ranker;
}

function contactColor(c: L1Contact): string {
  if (c.source === "uniprot_binding") return COLORS.uniprot;
  return c.confidence_tier === "high" ? COLORS.litHigh : COLORS.litLower;
}

function fmt(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Rationale({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className={styles.kv}>
      {Object.entries(value).map(([k, v]) =>
        v && typeof v === "object" && !Array.isArray(v) ? (
          <div key={k} className={styles.kvNested}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd>
              <Rationale value={v as Record<string, unknown>} />
            </dd>
          </div>
        ) : (
          <div key={k}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd>{fmt(v)}</dd>
          </div>
        ),
      )}
    </dl>
  );
}

export function SiteCard({ site, length }: { site: L1Site; length: number | null }) {
  const primary = site.is_primary !== false;
  return (
    <div className={`${styles.site} ${primary ? styles.sitePrimary : ""}`}>
      <div className={styles.siteHead}>
        <span className={styles.swatch} style={{ background: siteColor(site) }} />
        <strong>{primary ? "Current pick" : "Alternative"}</strong>
        <span>{l1SiteLabel(site, length)}</span>
        {site.leader === "igk" ? <span className={styles.badge}>Igκ leader</span> : null}
        <StatusPill status={site.status} />
        <span className={styles.muted}>
          {SOURCE_LABEL[site.site_source ?? "rung_builder"]}
          {site.rank != null ? ` · rank ${site.rank}` : ""}
          {site.confidence ? ` · ${site.confidence} confidence` : ""}
        </span>
      </div>
      <dl className={styles.why}>
        <dt>decided by</dt>
        <dd>{site.decided_by}</dd>
        {site.reason ? (<><dt>reason</dt><dd>{site.reason}</dd></>) : null}
        {site.rejected_alternative ? (<><dt>rejected alternative</dt><dd>{site.rejected_alternative}</dd></>) : null}
        {site.decision ? (<><dt>decision</dt><dd>{site.decision}</dd></>) : null}
        {site.status_detail ? (<><dt>detail</dt><dd>{site.status_detail}</dd></>) : null}
      </dl>
      <details className={styles.more}>
        <summary>rationale, scores and source</summary>
        {site.rationale ? <Rationale value={site.rationale} /> : <p className={styles.muted}>No scores recorded for this pick.</p>}
        <dl className={styles.why}>
          <dt>implemented by</dt>
          <dd>{site.implemented_by}</dd>
          <dt>cassette</dt>
          <dd>{site.cassette ?? "—"}{site.cassette_aa != null ? ` (${site.cassette_aa} aa inserted)` : ""}</dd>
          <dt>source</dt>
          <dd className={styles.mono}>
            {site.source.pr != null ? `design PR ${site.source.pr} (${site.source.pr_state ?? "?"}) · ` : ""}
            {site.source.commit.slice(0, 8)} · {site.source.path}
          </dd>
          <dt>site id</dt>
          <dd className={styles.mono}>{site.site_id}</dd>
        </dl>
      </details>
    </div>
  );
}

function ReviewPanel({
  member,
  loadVersion,
  reviews,
  token,
  reviewer,
  pickedResidue,
  onSaved,
}: {
  member: L1Member;
  loadVersion: string;
  reviews: L1Reviews | null;
  token: string;
  reviewer: string;
  pickedResidue: number | null;
  onSaved: () => void;
}) {
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");
  const [alt, setAlt] = useState<{ residue: string; placement: L1Placement; cassette: string; reason: string }>({
    residue: "", placement: "internal", cassette: "", reason: "",
  });
  useEffect(() => {
    setReason("");
    setMsg("");
    setAlt({ residue: "", placement: "internal", cassette: "", reason: "" });
  }, [member.member_id]);
  useEffect(() => {
    if (pickedResidue != null) setAlt((a) => ({ ...a, residue: String(pickedResidue) }));
  }, [pickedResidue]);

  const base = {
    reviewer, member_id: member.member_id, design_id: member.design_id, gene_symbol: member.gene_symbol,
    sequence_sha256: member.sequence_sha256 ?? null, load_version: loadVersion,
  };
  const canWrite = Boolean(token && reviewer && member.design_id);
  const mine = (reviews?.reviews ?? []).filter((r) => r.design_id === member.design_id);
  const alts = (reviews?.alt_tags ?? []).filter((r) => r.design_id === member.design_id);

  async function verdict(v: "good" | "no") {
    if (v === "no" && !reason.trim()) {
      setMsg("Say why it is a no.");
      return;
    }
    const r = await submitL1Review(API_BASE, token, { ...base, kind: "verdict", verdict: v, reason });
    setMsg(r.ok ? `Saved: ${v === "good" ? "looks good" : "no"}.` : `Not saved: ${r.error}`);
    if (r.ok) {
      setReason("");
      onSaved();
    }
  }

  async function suggest() {
    const r = await submitL1Review(API_BASE, token, {
      ...base, kind: "alt_tag", placement: alt.placement,
      insert_after_residue: alt.residue === "" ? null : Number(alt.residue),
      cassette_variant: alt.cassette, reason: alt.reason,
    });
    setMsg(r.ok ? "Alternative tag saved." : `Not saved: ${r.error}`);
    if (r.ok) {
      setAlt({ residue: "", placement: alt.placement, cassette: "", reason: "" });
      onSaved();
    }
  }

  return (
    <section className={styles.review} aria-label="Review">
      <h3 className={styles.h3}>Your review</h3>
      {!canWrite ? (
        <p className={styles.muted}>Set your name and review token (top of the page) to record a review.</p>
      ) : null}
      <div className={styles.verdictRow}>
        <button type="button" className={styles.good} disabled={!canWrite} onClick={() => verdict("good")}>
          Looks good
        </button>
        <button type="button" className={styles.no} disabled={!canWrite} onClick={() => verdict("no")}>
          No
        </button>
        <textarea
          className={styles.reason}
          placeholder="Why not? (required for No; optional otherwise)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
        />
      </div>
      <details className={styles.altForm} open={pickedResidue != null}>
        <summary>Suggest an alternative tag</summary>
        <div className={styles.altGrid}>
          <label>
            residue (member numbering; or click the structure)
            <input
              inputMode="numeric"
              value={alt.residue}
              onChange={(e) => setAlt({ ...alt, residue: e.target.value.replace(/[^0-9]/g, "") })}
              placeholder={member.ordered_length_aa ? `1–${member.ordered_length_aa}` : ""}
            />
          </label>
          <label>
            placement
            <select value={alt.placement} onChange={(e) => setAlt({ ...alt, placement: e.target.value as L1Placement })}>
              {(Object.keys(PLACEMENT_LABEL) as L1Placement[]).map((p) => (
                <option key={p} value={p}>{PLACEMENT_LABEL[p]}</option>
              ))}
            </select>
          </label>
          <label>
            cassette variant (optional)
            <input value={alt.cassette} onChange={(e) => setAlt({ ...alt, cassette: e.target.value })} placeholder="e.g. linkers-only" />
          </label>
          <label className={styles.altReason}>
            reason
            <textarea rows={2} value={alt.reason} onChange={(e) => setAlt({ ...alt, reason: e.target.value })} />
          </label>
        </div>
        <button type="button" disabled={!canWrite} onClick={suggest}>Save suggestion</button>
      </details>
      {msg ? <p className={styles.msg} role="status">{msg}</p> : null}
      {mine.length || alts.length ? (
        <div className={styles.history}>
          <h4 className={styles.h4}>Recorded for this member</h4>
          <ul>
            {mine.map((r) => (
              <li key={r.review_id}>
                <span className={r.verdict === "good" ? styles.goodText : styles.noText}>{r.verdict === "good" ? "looks good" : "no"}</span>{" "}
                · {r.reviewer} · {r.created_at.slice(0, 16).replace("T", " ")}
                {r.reason ? ` · ${r.reason}` : ""}
              </li>
            ))}
            {alts.map((a) => (
              <li key={a.suggestion_id}>
                <span className={styles.swatch} style={{ background: COLORS.suggestion }} /> alt tag:{" "}
                {PLACEMENT_LABEL[a.placement]}
                {a.insert_after_residue != null ? ` after ${a.insert_after_residue}` : ""}
                {a.cassette_variant ? ` · ${a.cassette_variant}` : ""} · {a.reviewer} ·{" "}
                {a.created_at.slice(0, 16).replace("T", " ")}
                {a.reason ? ` · ${a.reason}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function ContactsTable({ contacts, showHidden }: { contacts: L1Contact[]; showHidden: boolean }) {
  const rows = visibleContacts(contacts, showHidden);
  if (!rows.length) return <p className={styles.muted}>No contact annotations for this member.</p>;
  return (
    <div className={styles.tablewrap}>
      <table className={styles.table}>
        <thead>
          <tr><th>Residue</th><th>Source</th><th>Tier</th><th>Evidence</th><th>Class</th><th>Partner</th><th>Side</th><th>PMIDs</th></tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={`${c.residue}-${c.source}`}>
              <td className={styles.mono}>{c.aa ?? ""}{c.residue}{c.canonical_residue != null && c.canonical_residue !== c.residue ? ` (canon. ${c.canonical_residue})` : ""}</td>
              <td><span className={styles.swatch} style={{ background: contactColor(c) }} />{c.source === "literature_agent" ? "literature (agent-extracted)" : "UniProt binding site"}</td>
              <td>{c.confidence_tier}{c.ion_site ? " · ion site" : ""}{c.additive_only ? " · additive" : ""}</td>
              <td>{c.evidence_types ?? "—"}</td>
              <td>{c.contact_classes ?? "—"}</td>
              <td>{c.ligands ?? "—"}</td>
              <td>{c.in_extracellular ? "outside" : c.topology_state ?? "—"}</td>
              <td>
                {(c.pmids ?? "").split(/[;,\s]+/).filter(Boolean).map((p) => (
                  <a key={p} href={`https://pubmed.ncbi.nlm.nih.gov/${p}/`} target="_blank" rel="noreferrer" className={styles.pmid}>{p}</a>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CuratedContacts({ gene, aligned, acc }: { gene: CuratedContactsData | null | "loading"; aligned: boolean; acc: string | null }) {
  if (!acc) return <p className={styles.muted}>No UniProt accession for this member&rsquo;s model, so no curated contacts.</p>;
  if (gene === "loading") return <p className={styles.muted}>Loading curated contact sites…</p>;
  if (!gene || !gene.sites.length) return <p className={styles.muted}>No curated contact sites for {acc}.</p>;
  return (
    <>
      <p className={styles.muted}>
        {gene.sites.length} curated extracellular contact site{gene.sites.length === 1 ? "" : "s"} for {acc}{" "}
        (structures and databases, the gene page&rsquo;s contact set, release {gene.release_id}).{" "}
        {aligned
          ? "This member's protein is that reference sequence, so they are drawn on the structure."
          : `This member's protein differs from ${acc}'s reference sequence, so they are listed, not drawn.`}
      </p>
      <div className={styles.tablewrap}>
        <table className={styles.table}>
          <thead><tr><th>Partner</th><th>Source</th><th>Residues</th><th>Context</th><th>Reference</th></tr></thead>
          <tbody>
            {gene.sites.map((c, i) => (
              <tr key={`${c.observation_id ?? i}`}>
                <td><span className={styles.swatch} style={{ background: COLORS.curated }} />{c.partner_label ?? c.partner}</td>
                <td>{c.source}</td>
                <td className={styles.mono}>{(c.positions ?? []).length} ({(c.positions ?? []).slice(0, 8).join(", ")}{(c.positions ?? []).length > 8 ? ", …" : ""})</td>
                <td>{c.context ?? "—"}</td>
                <td>{c.reference ? <a href={c.reference} target="_blank" rel="noreferrer">link</a> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function MemberDetail({
  member,
  loadVersion,
  reviews,
  token,
  reviewer,
  onSaved,
}: {
  member: L1Member;
  loadVersion: string;
  reviews: L1Reviews | null;
  token: string;
  reviewer: string;
  onSaved: () => void;
}) {
  const sites = sortSites(member.sites);
  const models = member.structures.filter((s) => s.is_chosen);
  const [modelId, setModelId] = useState<string>("");
  const [showAlts, setShowAlts] = useState(true);
  const [showContacts, setShowContacts] = useState(true);
  const [showHidden, setShowHidden] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);
  const [curated, setCurated] = useState<CuratedContactsData | null | "loading">(null);
  const acc = member.uniprot_acc && /^[A-Z0-9]{6,10}$/.test(member.uniprot_acc) ? member.uniprot_acc : null;
  useEffect(() => {
    if (!acc) {
      setCurated(null);
      return;
    }
    const ctl = new AbortController();
    setCurated("loading");
    fetchCuratedContacts(acc, ctl.signal).then((g) => !ctl.signal.aborted && setCurated(g));
    return () => ctl.abort();
  }, [acc]);
  const curatedGene: CuratedContactsData | null = curated && curated !== "loading" ? curated : null;
  const curatedAligned = curatedContactsAlign(member.sequence_sha256, curatedGene?.reference_sequence_sha256);
  useEffect(() => {
    setModelId(models.find((m) => m.kind === "native")?.structure_id ?? models[0]?.structure_id ?? "");
    setPicked(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [member.member_id]);
  const model: L1Structure | undefined = models.find((m) => m.structure_id === modelId) ?? models[0];
  const url = model ? l1StructureUrl(model) : null;
  const offset = model?.kind === "native" ? model.residue_offset ?? 0 : 0;

  const marks: L1Mark[] = [];
  if (model?.kind === "native") {
    if (showContacts && curatedAligned && curatedGene) {
      for (const c of curatedGene.sites) {
        for (const p of c.positions ?? []) marks.push({ resi: p + offset, color: COLORS.curated, radius: 1.3 });
      }
    }
    if (showContacts) {
      for (const c of visibleContacts(member.contacts ?? [], showHidden)) {
        marks.push({ resi: c.residue + offset, color: contactColor(c), radius: 1.5 });
      }
    }
    // Alternatives first, current picks last: when both name the same residue, the
    // current pick must be the sphere you see.
    for (const s of [...sites].reverse()) {
      if (s.insert_after_residue == null || s.insert_after_residue < 1) continue;
      if (s.is_primary === false && !showAlts) continue;
      marks.push({
        resi: s.insert_after_residue + offset,
        color: siteColor(s),
        radius: s.is_primary === false ? 2.4 : 3.2,
        label: s.is_primary === false ? undefined : `${s.residue_before ?? ""}${s.insert_after_residue}`,
      });
    }
    if (picked != null) marks.push({ resi: picked + offset, color: COLORS.suggestion, radius: 3.0, label: `alt ${picked}` });
  }
  const span: [number, number] | null =
    model?.kind === "native" && member.ordered_length_aa ? [offset + 1, offset + member.ordered_length_aa] : null;
  const cassette: [number, number] | null =
    model?.kind === "tagged" && model.cassette_first_model_residue != null && model.cassette_last_model_residue != null
      ? [model.cassette_first_model_residue, model.cassette_last_model_residue]
      : null;
  const pick = useCallback(
    (resi: number) => {
      if (!model) return;
      const r = modelToMemberResidue(resi, model);
      if (r != null && r >= 0) setPicked(r);
    },
    [model],
  );

  return (
    <div className={styles.detailBody}>
      {member.proteoform?.decision ? (
        <p className={styles.caveat}>
          <strong>Proteoform audit: {member.proteoform.decision}</strong>
          {member.proteoform.target ? ` → ${member.proteoform.target}` : ""}
          {member.proteoform.reason ? `. ${member.proteoform.reason}` : ""}
          {member.proteoform.decided_by ? ` (decided by ${member.proteoform.decided_by})` : ""}
        </p>
      ) : null}
      <ReviewPanel
        member={member}
        loadVersion={loadVersion}
        reviews={reviews}
        token={token}
        reviewer={reviewer}
        pickedResidue={picked}
        onSaved={onSaved}
      />
      <section>
        <h3 className={styles.h3}>Structure</h3>
        <div className={styles.modelRow}>
          {models.map((m) => (
            <button
              key={m.structure_id}
              type="button"
              className={m.structure_id === model?.structure_id ? styles.tabOn : styles.tab}
              onClick={() => setModelId(m.structure_id)}
            >
              {m.kind === "tagged" ? "Tagged refold" : "Native"} · {m.source === "alphafold_db" ? "AlphaFold DB" : "ColabFold"}
              {m.mean_plddt != null ? ` · pLDDT ${m.mean_plddt.toFixed(0)}` : ""}
              {m.refold_verdict ? ` · ${m.refold_verdict}` : ""}
            </button>
          ))}
          {!models.some((m) => m.kind === "tagged") ? <span className={styles.muted}>No tagged refold yet.</span> : null}
        </div>
        {url ? (
          <L1Structure3D pdbUrl={url} span={span} marks={marks} cassette={cassette} onPick={model?.kind === "native" ? pick : undefined} />
        ) : (
          <p className={styles.muted}>No model for this member.</p>
        )}
        <div className={styles.legend}>
          <span><i style={{ background: COLORS.pick }} /> current pick</span>
          <label><input type="checkbox" checked={showAlts} onChange={(e) => setShowAlts(e.target.checked)} /> <i style={{ background: COLORS.ranker }} /> ranker alternatives <i style={{ background: COLORS.agent }} /> agent proposals</label>
          <label><input type="checkbox" checked={showContacts} onChange={(e) => setShowContacts(e.target.checked)} /> <i style={{ background: COLORS.litHigh }} /> literature contacts (agent-extracted; lighter = modeling/homology only) <i style={{ background: COLORS.uniprot }} /> UniProt binding <i style={{ background: COLORS.curated }} /> curated (structures / databases)</label>
          <label><input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} /> include ion sites and crystallization additives</label>
          {model?.kind === "tagged" ? <span><i style={{ background: "#7C5CBF" }} /> cassette</span> : null}
          <span><i style={{ background: COLORS.suggestion }} /> your suggested residue (click the model)</span>
        </div>
        {model?.note || model?.proteoform_match ? (
          <p className={styles.muted}>
            Model: {model.proteoform_match}{model.residue_offset ? `, member residue i = model residue i + ${model.residue_offset}` : ""}
            {model.note ? ` · ${model.note}` : ""}
          </p>
        ) : null}
      </section>
      <section>
        <h3 className={styles.h3}>Tag sites</h3>
        {sites.length ? sites.map((s) => <SiteCard key={s.site_id} site={s} length={member.ordered_length_aa} />)
          : <p className={styles.muted}>No tag site is recorded for this member yet.</p>}
      </section>
      <section>
        <h3 className={styles.h3}>Contact sites</h3>
        <p className={styles.caveat}>
          <strong>Literature (agent-extracted)</strong> rows are residues that literature agents read out of papers and
          that passed mechanical checks (the residue letter matches, the PMID resolves, the quote names the residue).
          Passing means the paper says it, not that the residue contacts the ligand in this construct. Accuracy was
          measured only on a 20-protein pilot against structural contacts (precision 0.47, recall 0.40); the
          library-scale set is not scored against any truth set. Never use these as training labels.
        </p>
        <h4 className={styles.h4}>Curated contacts (structures and databases)</h4>
        <CuratedContacts gene={curated} aligned={curatedAligned} acc={acc} />
        <h4 className={styles.h4}>Literature contacts (agent-extracted) and UniProt binding sites</h4>
        <ContactsTable contacts={member.contacts ?? []} showHidden={showHidden} />
      </section>
    </div>
  );
}

export function L1Review() {
  const [index, setIndex] = useState<L1Index | null | "loading">("loading");
  const [filters, setFilters] = useState(readUrl);
  const [detail, setDetail] = useState<L1DesignFile | null>(null);
  const [token, setToken] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [reviews, setReviews] = useState<L1Reviews | null>(null);
  const [authMsg, setAuthMsg] = useState("");

  useEffect(() => {
    setToken(store.get("l1-review-token"));
    setReviewer(store.get("l1-review-reviewer"));
    fetchL1Index(API_BASE).then((d) => setIndex(d));
  }, []);

  const loadReviews = useCallback(async () => {
    if (!token) {
      setReviews(null);
      return;
    }
    const r = await fetchL1Reviews(API_BASE, token);
    if (r === "unauthorized") {
      setAuthMsg("That review token was not accepted.");
      setReviews(null);
    } else {
      setAuthMsg(r ? "" : "Reviews are unavailable (the review endpoints are not enabled on this API).");
      setReviews(r);
    }
  }, [token]);
  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  const members = index && index !== "loading" ? index.members : [];
  const visible = useMemo(
    () => filterIndex(members, { rung: filters.rung, membraneClass: filters.cls, status: filters.status, query: filters.q }),
    [members, filters.rung, filters.cls, filters.status, filters.q],
  );
  const current: L1IndexMember | undefined =
    members.find((m) => m.design_id === filters.m || m.member_id === filters.m) ?? undefined;
  const pos = current ? visible.findIndex((m) => m.member_id === current.member_id) : -1;
  const verdicts = useMemo(() => latestVerdicts(reviews?.reviews ?? []), [reviews]);

  const update = useCallback((patch: Partial<typeof filters>) => {
    setFilters((f) => {
      const next = { ...f, ...patch };
      writeUrl(next);
      return next;
    });
  }, []);
  const go = useCallback(
    (delta: number) => {
      if (!visible.length) return;
      const i = pos < 0 ? 0 : (pos + delta + visible.length) % visible.length;
      update({ m: visible[i].design_id ?? visible[i].member_id });
    },
    [pos, visible, update],
  );

  useEffect(() => {
    if (!current) {
      setDetail(null);
      return;
    }
    let live = true;
    fetchL1Design(current.gene_symbol, API_BASE).then((d) => live && setDetail(d));
    return () => {
      live = false;
    };
  }, [current?.gene_symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  // A detail from a newer load than the index means a load landed while the page was
  // open: refresh the index so both describe the same library.
  const detailLoad = detail?.load?.load_version;
  const indexLoad = index && index !== "loading" ? index.load?.load_version : undefined;
  useEffect(() => {
    if (detailLoad && indexLoad && detailLoad !== indexLoad) fetchL1Index(API_BASE).then((d) => setIndex(d));
  }, [detailLoad, indexLoad]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
      if (e.key === "ArrowRight" || e.key === "j") go(1);
      if (e.key === "ArrowLeft" || e.key === "k") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  if (index === "loading") return <p className={styles.muted}>Loading the library…</p>;
  if (!index || !index.load) return <p className={styles.muted}>No L1 design is published on this API yet.</p>;

  // Match on design id: member ids are renumbered between loads, design ids are not.
  const member = detail?.members.find((m) =>
    current?.design_id ? m.design_id === current.design_id : m.member_id === current?.member_id,
  );
  const rungCounts = countBy(members.filter((m) => !filters.cls || m.membrane_class === filters.cls), (m) => m.rung);
  const classCounts = countBy(members.filter((m) => !filters.rung || m.rung === filters.rung), (m) => m.membrane_class);
  const reviewedN = new Set((reviews?.reviews ?? []).map((r) => r.design_id)).size;

  return (
    <div className={styles.app}>
      <div className={styles.settings}>
        <label>
          reviewer
          <input value={reviewer} onChange={(e) => { setReviewer(e.target.value); store.set("l1-review-reviewer", e.target.value); }} placeholder="your name" />
        </label>
        <label>
          review token
          <input type="password" value={token} onChange={(e) => { setToken(e.target.value); store.set("l1-review-token", e.target.value); }} placeholder="paste once; kept in this browser" />
        </label>
        {reviews ? (
          <span className={styles.muted}>
            {reviewedN} of {members.length} members reviewed ·{" "}
            <a href={`${API_BASE}/v1/l1-review/export.tsv`} onClick={async (e) => {
              e.preventDefault();
              const res = await fetch(`${API_BASE}/v1/l1-review/export.tsv`, { headers: { "X-L1-Review-Token": token } });
              const blob = await res.blob();
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = "l1_reviews.tsv";
              a.click();
            }}>export reviews + suggestions (TSV)</a>
          </span>
        ) : null}
        {authMsg ? <span className={styles.warn}>{authMsg}</span> : null}
        <span className={`${styles.muted} ${styles.mono}`}>load {index.load.load_version}</span>
      </div>

      <div className={styles.facets}>
        <div>
          <span className={styles.facetLabel}>Rung</span>
          <button type="button" className={!filters.rung ? styles.chipOn : styles.chip} onClick={() => update({ rung: "" })}>all</button>
          {rungCounts.map(([r, n]) => (
            <button key={r} type="button" className={filters.rung === r ? styles.chipOn : styles.chip} onClick={() => update({ rung: filters.rung === r ? "" : r })}>
              {r} <span className={styles.n}>{n}</span>
            </button>
          ))}
        </div>
        <div>
          <span className={styles.facetLabel} title="Rule-based: GPCR flag, HGNC transporter/channel families, rung and DeepTMHMM helix count">Class</span>
          <button type="button" className={!filters.cls ? styles.chipOn : styles.chip} onClick={() => update({ cls: "" })}>all</button>
          {classCounts.map(([c, n]) => (
            <button key={c} type="button" className={filters.cls === c ? styles.chipOn : styles.chip} onClick={() => update({ cls: filters.cls === c ? "" : c })}>
              {c} <span className={styles.n}>{n}</span>
            </button>
          ))}
        </div>
        <div>
          <span className={styles.facetLabel}>Pick</span>
          {["", "built", "decided_not_built", "pending", "no_tag", "none"].map((s) => (
            <button key={s || "all"} type="button" className={filters.status === s ? styles.chipOn : styles.chip} onClick={() => update({ status: s })}>
              {s === "" ? "all" : s === "none" ? "no pick yet" : STATUS_LABEL[s as L1Site["status"]]}
            </button>
          ))}
          <input className={styles.search} value={filters.q} onChange={(e) => update({ q: e.target.value })} placeholder="gene, l1-m…, l1-p…" />
        </div>
      </div>

      <div className={styles.split}>
        <ol className={styles.list} aria-label="Members">
          {visible.map((m) => {
            const v = verdicts.get(m.design_id ?? "") ?? [];
            const on = current?.member_id === m.member_id;
            return (
              <li key={m.member_id}>
                <button type="button" className={on ? styles.rowOn : styles.row} onClick={() => update({ m: m.design_id ?? m.member_id })}>
                  <strong>{m.gene_symbol}</strong>
                  <span className={styles.mono}>{m.member_id}</span>
                  {m.species && m.species !== "human" ? <span className={styles.badge}>{m.species}</span> : null}
                  {m.candidate_set === "isoform" ? <span className={styles.badge}>isoform</span> : null}
                  <span className={styles.rowStatus}>
                    {m.pick_status.length ? m.pick_status.map((s, i) => <StatusPill key={i} status={s} />) : <span className={styles.muted}>no pick</span>}
                    {v.map((r) => (
                      <span key={r.review_id} className={r.verdict === "good" ? styles.goodDot : styles.noDot} title={`${r.reviewer}: ${r.verdict}${r.reason ? ` — ${r.reason}` : ""}`} />
                    ))}
                  </span>
                </button>
              </li>
            );
          })}
          {!visible.length ? <li className={styles.muted}>No member matches these filters.</li> : null}
        </ol>

        <div className={styles.detail}>
          {current ? (
            <>
              <div className={styles.detailHead}>
                <button type="button" onClick={() => go(-1)} aria-label="Previous member">←</button>
                <div>
                  <h2 className={styles.h2}>
                    {current.gene_symbol} <span className={styles.mono}>{current.member_id}</span>{" "}
                    <span className={`${styles.mono} ${styles.muted}`}>{current.design_id}</span>
                  </h2>
                  <p className={styles.muted}>
                    {current.species} {current.candidate_set?.replace(/_/g, " ")} · {current.rung} · {current.membrane_class}
                    {current.n_tm != null ? ` · ${current.n_tm} TM` : ""}
                    {current.ordered_length_aa ? ` · ${current.ordered_length_aa} aa` : ""} ·{" "}
                    <a href={`/${encodeURIComponent(current.gene_symbol)}`}>gene page</a>
                    {pos >= 0 ? ` · ${pos + 1} of ${visible.length} in this view (← → keys)` : " · not in the current filter"}
                  </p>
                </div>
                <button type="button" onClick={() => go(1)} aria-label="Next member">→</button>
              </div>
              {member ? (
                <MemberDetail
                  member={member}
                  loadVersion={index.load.load_version}
                  reviews={reviews}
                  token={token}
                  reviewer={reviewer}
                  onSaved={loadReviews}
                />
              ) : (
                <p className={styles.muted}>Loading {current.gene_symbol}…</p>
              )}
            </>
          ) : (
            <p className={styles.muted}>Pick a member on the left, or a rung or class above and step through it with ← →.</p>
          )}
        </div>
      </div>
    </div>
  );
}
