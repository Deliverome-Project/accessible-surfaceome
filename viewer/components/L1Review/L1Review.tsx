"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type KeyboardEvent as ReactKeyboardEvent, type SetStateAction } from "react";
import {
  PLACEMENT_LABEL,
  SOURCE_LABEL,
  STATUS_HELP,
  STATUS_LABEL,
  armLabel,
  countBy,
  fetchL1Design,
  fetchL1Index,
  fetchL1MemberTopologies,
  fetchL1Reviews,
  filterIndex,
  groupByGene,
  l1MemberRoleLabel,
  l1MemberTopology,
  l1ModelMap,
  l1OrderedProteinLabel,
  l1SiteLabel,
  l1StructureUrl,
  latestVerdicts,
  nextIndexByLetter,
  reviewScopeLabel,
  sortSites,
  standingReviewIds,
  reviewErrorMessage,
  submitL1Review,
  SP_LABEL,
  indexSpStatus,
  memberSp,
  uniprotDiffers,
  uniprotDiffLines,
  l1ResidueSegments,
  memberToModel,
  modelToMember,
  visibleContacts,
  type L1Contact,
  type L1DesignFile,
  type L1Index,
  type L1IndexMember,
  type L1Member,
  type L1Placement,
  type L1AltTagRow,
  type L1ReviewRow,
  type L1Reviews,
  type L1Site,
  type L1Structure,
} from "../../lib/l1-design";
import type { LibraryTopologyRow } from "../../lib/structure-viewer-types";
import { L1TopologyStrip, insertFlags } from "./L1TopologyStrip";
import { L1Structure3D, type L1Mark } from "./L1Structure3D";
import { curatedContactsAlign, fetchCuratedContacts, type CuratedContacts as CuratedContactsData } from "../../lib/l1-design";
import { useTurnstile, type ReviewAuth } from "./useTurnstile";
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

interface UrlFilters { m: string; rung: string; cls: string; status: string; q: string; sp: string; diff: string; rev: string }

function readUrl(): UrlFilters {
  if (typeof window === "undefined") return { m: "", rung: "", cls: "", status: "", q: "", sp: "", diff: "", rev: "" };
  const p = new URLSearchParams(window.location.search);
  return {
    m: p.get("m") ?? "", rung: p.get("rung") ?? "", cls: p.get("class") ?? "", status: p.get("status") ?? "",
    q: p.get("q") ?? "", sp: p.get("sp") ?? "", diff: p.get("diff") ?? "", rev: p.get("reviewed") ?? "",
  };
}

function writeUrl(s: UrlFilters) {
  const p = new URLSearchParams();
  if (s.m) p.set("m", s.m);
  if (s.rung) p.set("rung", s.rung);
  if (s.cls) p.set("class", s.cls);
  if (s.status) p.set("status", s.status);
  if (s.sp) p.set("sp", s.sp);
  if (s.diff) p.set("diff", s.diff);
  if (s.rev) p.set("reviewed", s.rev);
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

export function SiteCard({
  site,
  length,
  focused,
  onShow,
}: {
  site: L1Site;
  length: number | null;
  focused?: boolean;
  /** Focus this site on the structure and the topology strip. */
  onShow?: () => void;
}) {
  const primary = site.is_primary !== false;
  return (
    <div className={`${styles.site} ${primary ? styles.sitePrimary : ""}`}>
      <div className={styles.siteHead}>
        <span className={styles.swatch} style={{ background: siteColor(site) }} />
        <strong>{primary ? "Current pick" : "Alternative"}</strong>
        <span>{l1SiteLabel(site, length)}</span>
        {site.leader === "igk" ? <span className={styles.badge}>Igκ leader</span> : null}
        <StatusPill status={site.status} />
        {onShow && site.insert_after_residue != null ? (
          <button
            type="button"
            className={focused ? `${styles.siteShow} ${styles.siteShowOn}` : styles.siteShow}
            aria-pressed={!!focused}
            onClick={onShow}
          >
            {focused ? "shown on structure" : "show on structure"}
          </button>
        ) : null}
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

/** What a reviewer has chosen for one member and not yet saved. */
type ReviewMode = "" | "good" | "no" | "alt";
interface Draft {
  mode: ReviewMode;
  /** The tag site a verdict is about: undefined = not chosen yet (defaults to the current
   *  pick), "" = the member as a whole (a null `site_id`). */
  siteId?: string;
  /** One comment for every mode: the reason for a concern, or why the other site. */
  reason: string;
  alt: { residue: string; placement: L1Placement; cassette: string };
}

const EMPTY_DRAFT: Draft = {
  mode: "",
  reason: "",
  alt: { residue: "", placement: "internal", cassette: "" },
};

const MODES: { value: Exclude<ReviewMode, "">; label: string }[] = [
  { value: "good", label: "Site looks right" },
  { value: "no", label: "Concern" },
  { value: "alt", label: "Suggest another site" },
];

export function ReviewPanel({
  member,
  loadVersion,
  reviews,
  auth,
  reviewer,
  onEditName,
  pickedResidue,
  pickSeq = 0,
  drafts,
  setDrafts,
  onSaved,
}: {
  member: L1Member;
  loadVersion: string;
  reviews: L1Reviews | null;
  auth: ReviewAuth;
  reviewer: string;
  /** Opens the reviewer bar at the top of the page and focuses the name field. */
  onEditName: () => void;
  pickedResidue: number | null;
  /** Changes on every click on the model, so the same residue clicked twice still lands. */
  pickSeq?: number;
  drafts: Record<string, Draft>;
  setDrafts: Dispatch<SetStateAction<Record<string, Draft>>>;
  onSaved: (saved: Partial<L1Reviews>) => void;
}) {
  // Drafts are held per member for as long as the page is open, rather than cleared when
  // the member changes. Reading a neighbouring member before finishing a sentence is the
  // normal way to answer someone — "is a2 really worse than TFR2's?" — and clearing on
  // member change threw that text away silently.
  //
  // They are owned by `L1Review` and passed in, not held here: stepping to another gene
  // empties `detail` while the next design loads, which unmounts this panel and its
  // parent, so panel-local state cannot survive the very move that loses the text. Only
  // the page component stays mounted across it.
  const key = member.design_id ?? member.member_id;
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [commentOpen, setCommentOpen] = useState(false);
  const draft = drafts[key] ?? EMPTY_DRAFT;
  const patch = useCallback(
    (p: Partial<Draft>) => setDrafts((d) => ({ ...d, [key]: { ...(d[key] ?? EMPTY_DRAFT), ...p } })),
    [key],
  );
  const setAlt = useCallback(
    (p: Partial<Draft["alt"]>) =>
      setDrafts((d) => {
        const cur = d[key] ?? EMPTY_DRAFT;
        return { ...d, [key]: { ...cur, alt: { ...cur.alt, ...p } } };
      }),
    [key],
  );
  // The save message belongs to the member it was about; the draft text does not.
  useEffect(() => {
    setMsg(null);
  }, [key]);
  // Deps stay on `pickedResidue` alone, and the member is read through a ref: with `key`
  // in the deps this would re-run on a member change, while the parent has not yet reset
  // the pick to null, and write the old member's residue into the new member's draft.
  // Clicking a residue on the structure is a suggestion, so it also picks that mode.
  const keyRef = useRef(key);
  keyRef.current = key;
  useEffect(() => {
    if (pickedResidue == null) return;
    const k = keyRef.current;
    setDrafts((d) => {
      const cur = d[k] ?? EMPTY_DRAFT;
      return { ...d, [k]: { ...cur, mode: "alt", alt: { ...cur.alt, residue: String(pickedResidue) } } };
    });
  }, [pickedResidue, pickSeq]);

  const sites = useMemo(() => sortSites(member.sites), [member.sites]);
  // "This site" by default: the verdict is on the tag site we plan to use.
  const defaultSite = sites.find((s) => s.is_primary)?.site_id ?? "";
  const siteId = draft.siteId ?? defaultSite;
  // Real cassettes this member's sites carry; no free text.
  const cassettes = useMemo(
    () => [...new Set(sites.map((s) => s.cassette).filter((c): c is string => !!c))].sort(),
    [sites],
  );
  const name = reviewer.trim();
  const mine = (reviews?.reviews ?? []).filter((r) => r.design_id === member.design_id);
  const alts = (reviews?.alt_tags ?? []).filter((r) => r.design_id === member.design_id);
  const standing = useMemo(() => standingReviewIds(reviews?.reviews ?? []), [reviews]);
  const fieldId = `l1-review-${key}`;

  function problem(): string | null {
    if (!name) return "Add your name at the top of the page first.";
    if (draft.mode === "no" && !draft.reason.trim()) return "Say what is wrong in the comment.";
    if (draft.mode === "alt") {
      const needsResidue = draft.alt.placement === "internal" || draft.alt.placement === "after_sp";
      if (needsResidue && draft.alt.residue === "") return "Give the residue the tag goes after, or click one on the structure.";
    }
    return null;
  }

  async function submit() {
    if (!draft.mode || saving || !member.design_id) return;
    const p = problem();
    if (p) {
      setMsg({ ok: false, text: p });
      if (!name) onEditName();
      return;
    }
    // Every submit spends the current Turnstile token, so a fresh one is fetched after it.
    const t = auth.take();
    if (!t) {
      setMsg({
        ok: false,
        text: auth.status === "off"
          ? "Not saved: the anti-bot check is not available on this build."
          : auth.status === "error"
            ? `Not saved: ${reviewErrorMessage("turnstile_failed")}`
            : "Not saved: the anti-bot check is still running. Wait a second and submit again.",
      });
      return;
    }
    const base = {
      reviewer: name, member_id: member.member_id, design_id: member.design_id, gene_symbol: member.gene_symbol,
      sequence_sha256: member.sequence_sha256 ?? null, load_version: loadVersion,
    };
    const reason = draft.reason.trim() || null;
    setSaving(true);
    try {
      if (draft.mode === "alt") {
        const residue = draft.alt.residue === "" ? null : Number(draft.alt.residue);
        const cassette = draft.alt.cassette || null;
        const r = await submitL1Review(API_BASE, t, {
          ...base, kind: "alt_tag", placement: draft.alt.placement, insert_after_residue: residue,
          cassette_variant: cassette, reason,
        });
        if (!r.ok) return setMsg({ ok: false, text: `Not saved: ${reviewErrorMessage(r.error)}` });
        const row: L1AltTagRow = {
          suggestion_id: r.id, created_at: r.created_at, ...base, design_id: member.design_id,
          insert_after_residue: residue, placement: draft.alt.placement, cassette_variant: cassette, reason,
        };
        patch({ mode: "", reason: "", alt: EMPTY_DRAFT.alt });
        setMsg({ ok: true, text: "Saved — thank you. Your suggested site is listed below." });
        onSaved({ alt_tags: [row] });
        return;
      }
      const v = draft.mode;
      const site = siteId || null; // "" is the member as a whole, stored as NULL
      const r = await submitL1Review(API_BASE, t, { ...base, kind: "verdict", verdict: v, reason, site_id: site });
      if (!r.ok) return setMsg({ ok: false, text: `Not saved: ${reviewErrorMessage(r.error)}` });
      const row: L1ReviewRow = {
        review_id: r.id, created_at: r.created_at, ...base, design_id: member.design_id, site_id: site, verdict: v, reason,
      };
      patch({ mode: "", reason: "" });
      const about = reviewScopeLabel(site, sites, member.ordered_length_aa);
      setMsg({ ok: true, text: `Saved — thank you. ${v === "good" ? "Looks right" : "Concern"} on ${about}.` });
      onSaved({ reviews: [row] });
    } finally {
      setSaving(false);
    }
  }

  const placeholder =
    draft.mode === "good" ? "Anything to add? (optional)"
      : draft.mode === "alt" ? "Why this site instead? (optional)"
        : "What should change, and why?";

  return (
    <section className={styles.review} aria-label="Review">
      {/* Not "your review": the list below carries every reviewer's rows, which is what
          makes answering someone else's point possible at all. */}
      <h3 className={styles.h3}>Review</h3>
      <p className={styles.reviewIntro}>
        {name ? (
          <>
            Reviewing as{" "}
            <button type="button" className={styles.nameButton} onClick={onEditName} title="Change your name">
              {name} ▾
            </button>{" "}
            — your verdict on this member&apos;s tag site.
          </>
        ) : (
          <>
            <button type="button" className={styles.nameButton} onClick={onEditName}>
              Add your name ▾
            </button>{" "}
            to review this member&apos;s tag site.
          </>
        )}
      </p>
      {/* Toggle buttons, not radios: a focused radio takes the arrow keys, which left a
          reviewer pressing → to change member and changing the verdict instead. */}
      <div className={styles.verdictRow}>
        <div className={styles.segmented} role="group" aria-label="Your verdict">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              aria-pressed={draft.mode === m.value}
              className={draft.mode === m.value ? styles.segOn : styles.seg}
              onClick={() => { patch({ mode: draft.mode === m.value ? "" : m.value }); setMsg(null); }}
            >
              {m.label}
            </button>
          ))}
        </div>
        {draft.mode === "good" || draft.mode === "no" ? (
          // A verdict on one arm rather than on the member: the r2 agent round rejects
          // arms, not members, so "a2 is in the pore, a1 and a3 are fine" needs somewhere to go.
          <label className={styles.scope}>
            about
            <select value={siteId} onChange={(e) => patch({ siteId: e.target.value })}>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {reviewScopeLabel(s.site_id, sites, member.ordered_length_aa)}
                </option>
              ))}
              <option value="">the member as a whole</option>
            </select>
          </label>
        ) : null}
      </div>
      {draft.mode === "alt" ? (
        <div className={styles.altGrid}>
          <label>
            after residue (ordered-protein numbering)
            <input
              type="number"
              min={0}
              max={member.ordered_length_aa ?? undefined}
              step={1}
              value={draft.alt.residue}
              onChange={(e) => setAlt({ residue: e.target.value.replace(/[^0-9]/g, "") })}
              aria-describedby={`${fieldId}-residue-help`}
            />
            <span id={`${fieldId}-residue-help`} className={styles.help}>
              or click a residue on the structure
              {member.ordered_length_aa ? ` · 1–${member.ordered_length_aa}` : ""}
            </span>
          </label>
          <label>
            placement
            <select value={draft.alt.placement} onChange={(e) => setAlt({ placement: e.target.value as L1Placement })}>
              {(Object.keys(PLACEMENT_LABEL) as L1Placement[]).map((p) => (
                <option key={p} value={p}>{PLACEMENT_LABEL[p]}</option>
              ))}
            </select>
          </label>
          {cassettes.length > 1 ? (
            <label>
              cassette
              <select value={draft.alt.cassette} onChange={(e) => setAlt({ cassette: e.target.value })}>
                <option value="">same as the current pick</option>
                {cassettes.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          ) : null}
        </div>
      ) : null}
      <textarea
        id={`${fieldId}-comment`}
        className={styles.reason}
        aria-label="Comment"
        placeholder={placeholder}
        value={draft.reason}
        onChange={(e) => patch({ reason: e.target.value })}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            submit();
          }
        }}
        onFocus={() => setCommentOpen(true)}
        onBlur={() => setCommentOpen(false)}
        // One line until it is used: open while focused or holding text.
        rows={commentOpen || draft.reason ? 3 : 1}
      />
      <div className={styles.submitRow}>
        <button type="button" className={styles.primary} disabled={!draft.mode || saving} onClick={submit}>
          {saving ? "Saving…" : "Submit"}
        </button>
        <span className={styles.help}>
          {draft.mode ? "⌘/Ctrl + Enter from the comment" : "Choose a verdict to submit"}
        </span>
        {msg ? (
          <span className={msg.ok ? styles.saved : styles.error} role={msg.ok ? "status" : "alert"}>
            {msg.text}
          </span>
        ) : null}
      </div>
      {mine.length || alts.length ? (
        <div className={styles.history}>
          <h4 className={styles.h4}>Recorded for this member, every reviewer, oldest first</h4>
          <ul>
            {mine.map((r) => (
              <li key={r.review_id} className={standing.has(r.review_id) ? undefined : styles.superseded}>
                <span className={r.verdict === "good" ? styles.goodText : styles.noText}>{r.verdict === "good" ? "looks right" : "concern"}</span>{" "}
                · {reviewScopeLabel(r.site_id, sites, member.ordered_length_aa)} · {r.reviewer} ·{" "}
                {r.created_at.slice(0, 16).replace("T", " ")}
                {standing.has(r.review_id) ? "" : " · superseded by a later row"}
                {r.reason ? ` · ${r.reason}` : ""}
              </li>
            ))}
            {alts.map((a) => (
              <li key={a.suggestion_id}>
                <span className={styles.swatch} style={{ background: COLORS.suggestion }} /> another site:{" "}
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

/** "Reference CDS · UniProt canonical": which library CDS, and the protein it orders. */
function memberChipText(m: Pick<L1Member, "candidate_set" | "species">, topo: LibraryTopologyRow | null): string {
  const protein = l1OrderedProteinLabel(topo);
  return protein ? `${l1MemberRoleLabel(m)} · ${protein}` : l1MemberRoleLabel(m);
}

/** Label for a structure view tab. When a member carries multiple tagged refolds,
 *  name the arm/insertion residue so tabs are distinguishable before clicking. */
export function structureTabLabel(
  m: Pick<L1Structure, "kind" | "site_id" | "mean_plddt" | "refold_verdict">,
  sites: readonly Pick<L1Site, "site_id" | "insert_after_residue">[],
  multiFold: boolean,
): string {
  let base = m.kind === "tagged" ? "Fold" : "Native";
  if (m.kind === "tagged" && multiFold && m.site_id) {
    const site = sites.find((s) => s.site_id === m.site_id);
    const arm = armLabel(m.site_id);
    const res = site?.insert_after_residue;
    const tag =
      arm && res != null ? `${arm} · ${res}`
        : arm ? arm
          : res != null ? `after ${res}`
            : null;
    if (tag) base = `Fold (${tag})`;
  }
  return [
    base,
    m.mean_plddt != null ? `pLDDT ${m.mean_plddt.toFixed(0)}` : null,
    m.refold_verdict ?? null,
  ].filter(Boolean).join(" · ");
}

function MemberDetail({
  member,
  topologyRow,
  loadVersion,
  reviews,
  auth,
  reviewer,
  onEditName,
  drafts,
  setDrafts,
  onSaved,
}: {
  member: L1Member;
  topologyRow: LibraryTopologyRow | null;
  loadVersion: string;
  reviews: L1Reviews | null;
  auth: ReviewAuth;
  reviewer: string;
  onEditName: () => void;
  drafts: Record<string, Draft>;
  setDrafts: Dispatch<SetStateAction<Record<string, Draft>>>;
  onSaved: (saved: Partial<L1Reviews>) => void;
}) {
  const sites = sortSites(member.sites);
  // The fold (tagged refold) first and open by default: it is the construct being
  // reviewed, tag and all. The native model is the comparison.
  const models = useMemo(
    () => member.structures
      .filter((s) => s.is_chosen)
      .sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "tagged" ? -1 : 1)),
    [member.structures],
  );
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [modelId, setModelId] = useState<string>("");
  const [showAlts, setShowAlts] = useState(true);
  const [showContacts, setShowContacts] = useState(true);
  const [showHidden, setShowHidden] = useState(false);
  // A residue clicked on either model, as {r, n}: n changes on every click so clicking
  // the same residue again (after typing another) still reaches the review card.
  const [picked, setPicked] = useState<{ r: number; n: number } | null>(null);
  // The arm being looked at (clicked on the strip or a tag-site card).
  const [focusSite, setFocusSite] = useState<string | null>(null);
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
    setModelId(models[0]?.structure_id ?? "");
    setPicked(null);
    setFocusSite(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [member.member_id]);
  const model: L1Structure | undefined = models.find((m) => m.structure_id === modelId) ?? models[0];
  const url = model ? l1StructureUrl(model) : null;
  const offset = model?.kind === "native" ? model.residue_offset ?? 0 : 0;

  // Marks are placed through the model's own residue map, so picks, the focused arm and
  // the reviewer's suggestion show on the fold as well as on the native model.
  // Contacts stay on the native model, whose numbering is the member's own.
  const segments = model ? l1ResidueSegments(member, model) : null;
  const toModel = (r: number) => memberToModel(r, segments);
  const draftKey = member.design_id ?? member.member_id;
  const draft = drafts[draftKey];
  const suggested =
    draft?.mode === "alt" && draft.alt.residue !== "" && Number.isFinite(Number(draft.alt.residue))
      ? Number(draft.alt.residue)
      : null;
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
  }
  // Alternatives first, current picks last: when both name the same residue, the current
  // pick must be the sphere you see. The focused arm goes on top, larger and labelled.
  for (const s of [...sites].reverse()) {
    if (s.insert_after_residue == null || s.insert_after_residue < 1) continue;
    if (s.is_primary === false && !showAlts && s.site_id !== focusSite) continue;
    const resi = toModel(s.insert_after_residue);
    if (resi == null) continue;
    const on = s.site_id === focusSite;
    const arm = armLabel(s.site_id);
    marks.push({
      resi,
      color: siteColor(s),
      radius: on ? 4.2 : s.is_primary === false ? 2.4 : 3.2,
      label: on || s.is_primary !== false ? `${arm ? `${arm} ` : ""}${s.residue_before ?? ""}${s.insert_after_residue}` : undefined,
    });
  }
  if (suggested != null) {
    const resi = toModel(suggested);
    if (resi != null) marks.push({ resi, color: COLORS.suggestion, radius: 3.0, label: `you: after ${suggested}` });
  }
  const span: [number, number] | null =
    model?.kind === "native" && member.ordered_length_aa ? [offset + 1, offset + member.ordered_length_aa] : null;
  const cassette: [number, number] | null =
    model?.kind === "tagged" && model.cassette_first_model_residue != null && model.cassette_last_model_residue != null
      ? [model.cassette_first_model_residue, model.cassette_last_model_residue]
      : null;
  // Number keys switch the structure view (1 = fold, 2 = native, ...) from anywhere on the
  // page, except while typing, so a reviewer never has to reach for the mouse.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const i = /^[1-9]$/.test(e.key) ? Number(e.key) - 1 : -1;
      if (i < 0 || i >= models.length) return;
      e.preventDefault();
      setModelId(models[i].structure_id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [models]);
  // Inside the focused tab strip the arrows move between views (and do not step to the
  // next member, which the page-level arrows otherwise do).
  const onTabKey = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    const cur = models.findIndex((m) => m.structure_id === model?.structure_id);
    let next = -1;
    // Up / down only: left / right always step to the next member, even with a view
    // tab focused (clicking a tab used to capture them, which read as "arrows broken").
    if (e.key === "ArrowDown") next = (cur + 1) % models.length;
    else if (e.key === "ArrowUp") next = (cur - 1 + models.length) % models.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = models.length - 1;
    if (next < 0) return;
    e.preventDefault();
    e.stopPropagation();
    setModelId(models[next].structure_id);
    tabRefs.current[next]?.focus();
  };

  const pick = useCallback(
    (resi: number) => {
      const r = modelToMember(resi, segments);
      if (r != null && r >= 0) setPicked({ r, n: Date.now() });
    },
    // segments is rebuilt each render from model + member; key on what it depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [model?.structure_id, member.member_id],
  );
  // Focusing an arm the current view does not carry (an Igk swap's site is not in the
  // fold) switches to the native model, where every member residue is drawn. Only at
  // the moment of focusing: pressing 1 afterwards still shows the fold.
  const showSite = (siteId: string) => {
    if (focusSite === siteId) return setFocusSite(null);
    setFocusSite(siteId);
    const f = sites.find((x) => x.site_id === siteId);
    if (f?.insert_after_residue != null && f.insert_after_residue >= 1 && toModel(f.insert_after_residue) == null) {
      const native = models.find((m) => m.kind === "native");
      if (native) setModelId(native.structure_id);
    }
  };

  const topology = topologyRow?.per_residue_topology ?? "";
  const flags = insertFlags(sites, member.ordered_length_aa);
  const modelMap = topology && model ? l1ModelMap(member, model, topology) : null;
  const sp = memberSp(member, topology || null);
  const pickLeader = sites.find((s) => s.is_primary !== false)?.leader ?? null;
  const differs = uniprotDiffers(member);
  const diffLines = uniprotDiffLines(member.uniprot_diff ?? []);

  return (
    <div className={styles.detailBody}>
      <div className={styles.topGrid}>
      <div className={styles.topLeft}>
      {/* What the construct does at the N-terminus and how the ordered protein compares
          with UniProt: the two facts a reviewer otherwise has to reconstruct. */}
      <dl className={styles.facts}>
        <dt>N-terminus</dt>
        <dd title={`from ${sp.source}`}>
          {sp.status ? <span className={styles.spTag}>{SP_LABEL[sp.status]}</span> : null} {sp.text}
          <span className={styles.muted}> · from {sp.source}</span>
        </dd>
        <dt>UniProt</dt>
        <dd>
          {member.uniprot_canonical_acc || member.uniprot_acc ? (
            <a href={`https://www.uniprot.org/uniprotkb/${member.uniprot_canonical_acc ?? member.uniprot_acc}/entry`} target="_blank" rel="noreferrer">
              {member.uniprot_canonical_acc ?? member.uniprot_acc}
            </a>
          ) : "no accession"}
          {member.uniprot_canonical_length ? ` · canonical ${member.uniprot_canonical_length} aa` : ""}
          {member.ordered_length_aa ? ` · ordered ${member.ordered_length_aa} aa` : ""}
          {differs === null ? (
            <span className={styles.muted}> · comparison with the canonical not in this load</span>
          ) : differs ? (
            <>
              {" · "}<strong>differs from the canonical</strong>
              {diffLines.length ? (
                <ul className={styles.diffList}>
                  {diffLines.slice(0, 8).map((l, i) => <li key={i}>{l}</li>)}
                  {diffLines.length > 8 ? <li className={styles.muted}>+{diffLines.length - 8} more</li> : null}
                </ul>
              ) : null}
            </>
          ) : (
            " · identical to the canonical"
          )}
        </dd>
      </dl>
      {topology ? (
        <L1TopologyStrip
          topology={topology}
          sp={sp.band ? { ...sp.band, label: sp.text } : null}
          flags={flags}
          gene={member.gene_symbol}
          variantLabel={memberChipText(member, topologyRow)}
          nAlternatives={sites.filter((s) => s.is_primary === false).length}
          focusSiteId={focusSite}
          onFlagClick={showSite}
          suggestedResidue={suggested}
        />
      ) : null}
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
        auth={auth}
        reviewer={reviewer}
        onEditName={onEditName}
        pickedResidue={picked?.r ?? null}
        pickSeq={picked?.n ?? 0}
        drafts={drafts}
        setDrafts={setDrafts}
        onSaved={onSaved}
      />
      </div>
      <section className={styles.structurePane} aria-label="Structure">
        <div className={styles.modelRow} role="tablist" aria-label="Structure view (keys 1–9; up / down when focused)" onKeyDown={onTabKey}>
          <h3 className={styles.h3inline}>Structure</h3>
          {(() => {
            const multiFold = models.filter((x) => x.kind === "tagged").length > 1;
            return models.map((m, i) => {
              const on = m.structure_id === model?.structure_id;
              return (
                <button
                  key={m.structure_id}
                  ref={(el) => { tabRefs.current[i] = el; }}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  tabIndex={on ? 0 : -1}
                  className={on ? styles.tabOn : styles.tab}
                  onClick={() => setModelId(m.structure_id)}
                  title={`${m.kind === "tagged" ? "The ordered tagged protein, folded whole" : "The member's protein without the tag"} · ${m.source === "alphafold_db" ? "AlphaFold DB" : "ColabFold"} · key ${i + 1}`}
                >
                  {i < 9 ? <kbd className={styles.tabKey}>{i + 1}</kbd> : null}
                  {structureTabLabel(m, sites, multiFold)}
                </button>
              );
            });
          })()}
          {!models.some((m) => m.kind === "tagged") ? <span className={styles.muted}>No tagged refold yet.</span> : null}
        </div>
        {url ? (
          <L1Structure3D
            pdbUrl={url}
            span={span}
            marks={marks}
            cassette={cassette}
            onPick={segments ? pick : undefined}
            focusResi={(() => {
              const f = sites.find((x) => x.site_id === focusSite);
              return f?.insert_after_residue != null ? toModel(f.insert_after_residue) : null;
            })()}
            topology={topology || null}
            map={modelMap}
            modelLength={model?.model_length_aa ?? null}
            nonNativeLabel={
              pickLeader?.toLowerCase().startsWith("igk")
                ? "Igκ leader construct residues (not this protein's own)"
                : "added residues (not this protein's own)"
            }
          />
        ) : (
          <p className={styles.muted}>No model for this member.</p>
        )}
        {/* Picks, the focused arm and your suggestion are drawn on both views; contacts
            only on the native model, whose numbering is the member's own. */}
        <div className={styles.legend}>
          <span><i style={{ background: COLORS.pick }} /> current pick (click a flag or &ldquo;show on structure&rdquo; to focus an arm)</span>
          <label><input type="checkbox" checked={showAlts} onChange={(e) => setShowAlts(e.target.checked)} /> <i style={{ background: COLORS.ranker }} /> ranker alternatives <i style={{ background: COLORS.agent }} /> agent proposals</label>
          {model?.kind === "native" ? (
            <>
              <label><input type="checkbox" checked={showContacts} onChange={(e) => setShowContacts(e.target.checked)} /> <i style={{ background: COLORS.litHigh }} /> literature contacts (agent-extracted; lighter = modeling/homology only) <i style={{ background: COLORS.uniprot }} /> UniProt binding <i style={{ background: COLORS.curated }} /> curated (structures / databases)</label>
              <label><input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} /> include ion sites and crystallization additives</label>
            </>
          ) : (() => {
            const nativeIdx = models.findIndex((m) => m.kind === "native");
            const keyHint = nativeIdx >= 0 && nativeIdx < 9 ? ` (key ${nativeIdx + 1})` : "";
            return <span className={styles.muted}>contact sites: native model{keyHint}</span>;
          })()}
          <span><i style={{ background: COLORS.suggestion }} /> your suggested residue (click the model, or type it under &ldquo;Suggest another site&rdquo;)</span>
        </div>
        {model?.note || model?.proteoform_match ? (
          <p className={styles.muted}>
            Model: {model.proteoform_match}{model.residue_offset ? `, member residue i = model residue i + ${model.residue_offset}` : ""}
            {model.note ? ` · ${model.note}` : ""}
          </p>
        ) : null}
      </section>
      </div>
      <section>
        <h3 className={styles.h3}>Tag sites</h3>
        {sites.length ? sites.map((s) => (
            <SiteCard key={s.site_id} site={s} length={member.ordered_length_aa} focused={focusSite === s.site_id} onShow={() => showSite(s.site_id)} />
          ))
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
  const [reviewer, setReviewer] = useState("");
  // Rows from the Worker's read endpoint (token-gated, so normally null on this page)
  // plus the rows this browser saved since the page opened, so a reviewer sees their own.
  const [serverReviews, setServerReviews] = useState<L1Reviews | null>(null);
  const [savedHere, setSavedHere] = useState<L1Reviews>({ reviews: [], alt_tags: [] });
  const turnstile = useTurnstile();
  // The reviewer bar starts folded to one line, even with no name yet: open, it pushes the
  // structure below the fold at 1440x900. It opens on the first write attempt without a
  // name, or from the card's "Reviewing as … ▾" / "Add your name ▾", with the cursor in
  // the name field.
  const [identityOpen, setIdentityOpen] = useState(false);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const editName = useCallback(() => {
    setIdentityOpen(true);
    window.setTimeout(() => {
      nameRef.current?.scrollIntoView({ block: "nearest" });
      nameRef.current?.focus();
    }, 0);
  }, []);
  const auth: ReviewAuth = useMemo(() => ({ take: turnstile.take, status: turnstile.status }), [turnstile.take, turnstile.status]);
  // Unsaved review text, per member, for as long as the page is open. Held here because
  // this component outlives the detail panel: stepping to another gene empties `detail`
  // while the next design is fetched, which unmounts the panel the text was typed into.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [topologies, setTopologies] = useState<LibraryTopologyRow[]>([]);
  // What the last letter key did, shown for a moment so a key that found nothing is not
  // silent (pressing Z with no Z gene in the filter otherwise looks like a dead page).
  const [letterMsg, setLetterMsg] = useState("");
  const searchRef = useRef<HTMLInputElement | null>(null);
  const activeRowRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLOListElement | null>(null);
  const [keyHelpOpen, setKeyHelpOpen] = useState(false);

  useEffect(() => {
    setReviewer(store.get("l1-review-reviewer"));
    fetchL1Index(API_BASE).then((d) => setIndex(d));
  }, []);

  const loadReviews = useCallback(async () => {
    const r = await fetchL1Reviews(API_BASE);
    setServerReviews(r && r !== "unauthorized" ? r : null);
  }, []);
  useEffect(() => {
    loadReviews();
  }, [loadReviews]);
  // Design ids this reviewer has saved something on, kept per name in this browser:
  // the Worker's read endpoint is token-gated, so the page cannot ask it.
  const mineKey = `l1-review-mine:${reviewer.trim().toLowerCase()}`;
  const [mineIds, setMineIds] = useState<string[]>([]);
  useEffect(() => {
    if (!reviewer.trim()) return setMineIds([]);
    try {
      setMineIds(JSON.parse(store.get(mineKey) || "[]"));
    } catch {
      setMineIds([]);
    }
  }, [mineKey]);
  const onSaved = useCallback(
    (saved: Partial<L1Reviews>) => {
      const ids = [...(saved.reviews ?? []), ...(saved.alt_tags ?? [])].map((r) => r.design_id);
      setMineIds((cur) => {
        const next = [...new Set([...cur, ...ids])];
        store.set(mineKey, JSON.stringify(next));
        return next;
      });
      setSavedHere((cur) => ({
        reviews: [...cur.reviews, ...(saved.reviews ?? [])],
        alt_tags: [...cur.alt_tags, ...(saved.alt_tags ?? [])],
      }));
      loadReviews();
    },
    [loadReviews, mineKey],
  );
  const reviews = useMemo<L1Reviews | null>(() => {
    if (!serverReviews && !savedHere.reviews.length && !savedHere.alt_tags.length) return null;
    const seenR = new Set((serverReviews?.reviews ?? []).map((r) => r.review_id));
    const seenA = new Set((serverReviews?.alt_tags ?? []).map((r) => r.suggestion_id));
    return {
      reviews: [...(serverReviews?.reviews ?? []), ...savedHere.reviews.filter((r) => !seenR.has(r.review_id))],
      alt_tags: [...(serverReviews?.alt_tags ?? []), ...savedHere.alt_tags.filter((r) => !seenA.has(r.suggestion_id))],
    };
  }, [serverReviews, savedHere]);

  const members = index && index !== "loading" ? index.members : [];
  const reviewedByMe = useMemo(() => {
    const name = reviewer.trim().toLowerCase();
    const fromRows = (reviews?.reviews ?? []).filter((r) => r.reviewer.trim().toLowerCase() === name).map((r) => r.design_id);
    const fromAlts = (reviews?.alt_tags ?? []).filter((r) => r.reviewer.trim().toLowerCase() === name).map((r) => r.design_id);
    return new Set([...mineIds, ...(name ? [...fromRows, ...fromAlts] : [])]);
  }, [mineIds, reviews, reviewer]);
  const facetBase = {
    rung: filters.rung, membraneClass: filters.cls, status: filters.status, query: filters.q,
    sp: filters.sp, diff: filters.diff, reviewed: filters.rev, reviewedByMe,
  };
  const visible = useMemo(() => filterIndex(members, facetBase), [members, filters, reviewedByMe]); // eslint-disable-line react-hooks/exhaustive-deps
  const current: L1IndexMember | undefined =
    members.find((m) => m.design_id === filters.m || m.member_id === filters.m) ?? undefined;
  const pos = current ? visible.findIndex((m) => m.member_id === current.member_id) : -1;
  const verdicts = useMemo(() => latestVerdicts(reviews?.reviews ?? []), [reviews]);

  const update = useCallback((patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
  }, []);
  // The URL is written from an effect, not from inside the setFilters updater. React
  // runs an updater during render, and Next patches `history.replaceState`, so writing
  // there made the router set state mid-render — React's "Cannot update a component
  // while rendering a different component" warning, once per keypress now that the
  // arrows drive this.
  useEffect(() => {
    writeUrl(filters);
  }, [filters]);
  const go = useCallback(
    (delta: number) => {
      if (!visible.length) return;
      // One member in view (a search for one gene): say why nothing moved.
      if (visible.length === 1 && pos === 0) {
        setLetterMsg("only one member in this filter — clear the search or filters to step through the rest");
        return;
      }
      const i = pos < 0 ? 0 : (pos + delta + visible.length) % visible.length;
      update({ m: visible[i].design_id ?? visible[i].member_id });
    },
    [pos, visible, update],
  );
  const goTo = useCallback(
    (i: number) => {
      const m = visible[i];
      if (m) update({ m: m.design_id ?? m.member_id });
    },
    [visible, update],
  );
  /** Jump to the next gene starting with `letter`, wrapping; says so when there is none. */
  const jumpToLetter = useCallback(
    (letter: string) => {
      const i = nextIndexByLetter(visible, letter, pos);
      const L = letter.toUpperCase();
      if (i < 0) {
        setLetterMsg(`${L} — no gene in this filter`);
        return;
      }
      setLetterMsg(`${L} → ${visible[i].gene_symbol}`);
      goTo(i);
    },
    [visible, pos, goTo],
  );
  useEffect(() => {
    if (!letterMsg) return;
    const t = setTimeout(() => setLetterMsg(""), 1600);
    return () => clearTimeout(t);
  }, [letterMsg]);

  useEffect(() => {
    if (!current) {
      setDetail(null);
      setTopologies([]);
      return;
    }
    let live = true;
    const ctl = new AbortController();
    fetchL1Design(current.gene_symbol, API_BASE).then((d) => live && setDetail(d));
    // The per-residue topology strings live on the gene record, not on the design
    // payload. Fetched per gene, in parallel with the design, so stepping through
    // members of one gene costs one call for the whole group.
    setTopologies([]);
    fetchL1MemberTopologies(current.gene_symbol, API_BASE, ctl.signal).then(
      (rows) => live && setTopologies(rows),
    );
    return () => {
      live = false;
      ctl.abort();
    };
  }, [current?.gene_symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fit the list to the window rather than to a guessed `calc(100vh - Nrem)`: how far
  // down the page it starts depends on how many rows the filter chips wrap onto, which
  // changes with the window width and with the filters themselves. A list taller than
  // the space below it is the specific bug this avoids — `scrollIntoView` would put the
  // selected row inside the list's own view but below the window's, so arrow-stepping
  // looked like it had stopped moving.
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const fit = () => {
      // Below the split's breakpoint the list sits above the detail panel at a fixed
      // 40vh (the stylesheet's job); an inline height would fight it.
      if (window.innerWidth <= 900) {
        el.style.removeProperty("max-height");
        return;
      }
      const want = Math.max(220, Math.round(window.innerHeight - el.getBoundingClientRect().top - 12));
      // Only write on a real change: this runs from a ResizeObserver, and an
      // unconditional write is how those turn into loops.
      if (Math.abs(want - parseFloat(el.style.maxHeight || "0")) > 1) el.style.maxHeight = `${want}px`;
    };
    let raf = 0;
    const scheduleFit = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        fit();
      });
    };
    fit();
    window.addEventListener("resize", scheduleFit);
    window.addEventListener("scroll", scheduleFit, { passive: true });
    const ro = new ResizeObserver(scheduleFit);
    ro.observe(document.body);
    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", scheduleFit);
      window.removeEventListener("scroll", scheduleFit);
      ro.disconnect();
    };
    // Keyed on `index` because the list element does not exist while the library is
    // loading: a mount-only effect would measure nothing and leave the stylesheet's
    // fallback height in place, which is the very over-long list this works around.
  }, [index]);

  // Keep the selected row in view when the keys move the selection: the list is a
  // scrolling column, so arrow-walking it without this scrolls the selection off screen
  // within a dozen members. Scrolls the LIST only, by the least that brings the row in —
  // `scrollIntoView` would also scroll the window, which drags the detail panel and the
  // filters the reviewer is working against out from under them on a deep-linked load.
  useEffect(() => {
    const row = activeRowRef.current;
    const box = listRef.current;
    if (!row || !box) return;
    const r = row.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    const pad = 8;
    if (r.top < b.top) box.scrollTop -= b.top - r.top + pad;
    else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom + pad;
  }, [current?.member_id]);

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
      const typing =
        !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
      // Escape leaves a field so the rest of the keys come back; everything else stays
      // out of the way while the reviewer is writing a reason.
      if (typing) {
        if (e.key === "Escape") t.blur();
        return;
      }
      // Never steal a browser or OS shortcut (⌘L, ctrl-F, alt-←).
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Escape") {
        setKeyHelpOpen(false);
        return;
      }
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        go(1);
        return;
      }
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        go(-1);
        return;
      }
      if (e.key === "Home") {
        e.preventDefault();
        goTo(0);
        return;
      }
      if (e.key === "End") {
        e.preventDefault();
        goTo(visible.length - 1);
        return;
      }
      // `?` is shift+/ on a US layout, where the browser reports key "?" — but not on
      // every layout or every automation driver, so shift+/ is taken as `?` too.
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) {
        e.preventDefault();
        setKeyHelpOpen((v) => !v);
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }
      // A single letter jumps to the next gene starting with it. This is why j / k are no
      // longer prev / next: 2,710 members run the whole alphabet, so every letter has to
      // mean "jump to that letter" — the arrows already cover prev / next.
      if (/^[a-zA-Z]$/.test(e.key)) {
        e.preventDefault();
        jumpToLetter(e.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, goTo, jumpToLetter, visible.length]);

  if (index === "loading") return <p className={styles.muted}>Loading the library…</p>;
  if (!index || !index.load) return <p className={styles.muted}>No L1 design is published on this API yet.</p>;

  // Match on design id: member ids are renumbered between loads, design ids are not.
  const member = detail?.members.find((m) =>
    current?.design_id ? m.design_id === current.design_id : m.member_id === current?.member_id,
  );
  // Every chip counts the members it would show with the OTHER filters as they are, so a
  // number always means "click this and get that many".
  const without = (k: keyof typeof facetBase) => filterIndex(members, { ...facetBase, [k]: "" });
  const rungCounts = countBy(without("rung"), (m) => m.rung);
  const classCounts = countBy(without("membraneClass"), (m) => m.membrane_class);
  const forStatus = without("status");
  const statusCount = (s: string) =>
    s === "" ? forStatus.length : forStatus.filter((m) => (s === "none" ? !m.pick_status.length : m.pick_status.includes(s as L1Site["status"]))).length;
  const forSp = without("sp");
  const spKnown = members.some((m) => indexSpStatus(m) !== null);
  const spHasNone = members.some((m) => m.sp_status != null);
  const spCount = (k: string) => (k === "" ? forSp.length : forSp.filter((m) => indexSpStatus(m) === k).length);
  const forDiff = without("diff");
  const diffKnown = members.some((m) => uniprotDiffers(m) !== null);
  const diffCount = (k: string) => (k === "" ? forDiff.length : forDiff.filter((m) => uniprotDiffers(m) === (k === "yes")).length);
  const forRev = without("reviewed");
  const revCount = (k: string) => (k === "" ? forRev.length : forRev.filter((m) => reviewedByMe.has(m.design_id ?? m.member_id) === (k === "mine")).length);
  const filterSummary = [
    filters.rung && `rung: ${filters.rung}`,
    filters.cls && `class: ${filters.cls}`,
    filters.status && `pick: ${filters.status === "none" ? "no pick yet" : STATUS_LABEL[filters.status as L1Site["status"]] ?? filters.status}`,
    filters.sp && `SP: ${SP_LABEL[filters.sp as keyof typeof SP_LABEL] ?? filters.sp}`,
    filters.diff && (filters.diff === "yes" ? "differs from UniProt" : "same as UniProt"),
    filters.rev && (filters.rev === "mine" ? "reviewed by me" : "not reviewed by me"),
  ].filter(Boolean).join(" · ") || "none";
  const reviewedN = new Set((reviews?.reviews ?? []).map((r) => r.design_id)).size;

  const groups = groupByGene(visible);
  // Topology rows are fetched per gene, so every member of the current gene has one and
  // the tab strip can name each proteoform.
  const topoFor = (m: { design_id: string | null; ordered_length_aa: number | null }) =>
    l1MemberTopology(topologies, m);
  // The current gene's members, in browsing order, for the detail panel's tab strip.
  const siblings = current ? (groups.find((g) => g.gene_symbol === current.gene_symbol)?.members ?? []) : [];

  return (
    <div className={styles.app}>
      {/* One slim line when folded. No token: the name is trusted as typed and Cloudflare
          Turnstile (beside it, invisible unless it needs a click) keeps bots out. */}
      <div className={styles.identityRow}>
        <details
          className={styles.identity}
          open={identityOpen}
          onToggle={(e) => setIdentityOpen((e.currentTarget as HTMLDetailsElement).open)}
        >
          <summary>
            {reviewer.trim() ? `Reviewing as ${reviewer.trim()}` : "Add your name to review"}
            {reviews ? ` · ${reviewedN} of ${members.length} members reviewed` : ""}
            {" · "}
            <span className={styles.mono}>load {index.load.load_version}</span>
          </summary>
          <div className={styles.settings}>
            <label>
              your name
              <input
                ref={nameRef}
                value={reviewer}
                maxLength={80}
                autoComplete="name"
                onChange={(e) => { setReviewer(e.target.value); store.set("l1-review-reviewer", e.target.value); }}
                placeholder="your name"
                title="Shown with each review; kept in this browser"
              />
            </label>
            {serverReviews ? null : (
              <span className={styles.muted}>Reviews you save here are listed under each member; other reviewers&apos; are collected for the design team.</span>
            )}
          </div>
        </details>
        {/* One Turnstile widget for the page, beside the name. It runs invisibly; the slot
            opens only while Cloudflare wants a click and folds away once passed. */}
        <div
          ref={turnstile.slotRef}
          className={turnstile.needsClick ? styles.turnstile : `${styles.turnstile} ${styles.turnstileFolded}`}
          aria-label="anti-bot check"
          aria-hidden={!turnstile.needsClick}
        />
        {turnstile.status === "error" ? (
          <span className={styles.warn}>The anti-bot check could not load. Reload the page to retry.</span>
        ) : turnstile.status === "off" ? (
          <span className={styles.warn}>The anti-bot check is not configured on this build, so saving will fail.</span>
        ) : null}
      </div>

      {/* Filters are set once per session and then left alone, so they fold into one line
          that says what is applied. The search box lives on the gene list itself. */}
      <div className={styles.filterBar}>
      <details className={styles.filters}>
        <summary>
          Filters
          <span className={styles.filterNow}>{filterSummary}</span>
        </summary>
      <div className={styles.facets}>
        <div>
          <span className={styles.facetLabel}>Rung</span>
          <button type="button" className={!filters.rung ? styles.chipOn : styles.chip} onClick={() => update({ rung: "" })}>
            all <span className={styles.n}>{without("rung").length}</span>
          </button>
          {rungCounts.map(([r, n]) => (
            <button key={r} type="button" className={filters.rung === r ? styles.chipOn : styles.chip} onClick={() => update({ rung: filters.rung === r ? "" : r })}>
              {r} <span className={styles.n}>{n}</span>
            </button>
          ))}
        </div>
        <div>
          <span className={styles.facetLabel} title="Rule-based: GPCR flag, HGNC transporter/channel families, rung and DeepTMHMM helix count">Class</span>
          <button type="button" className={!filters.cls ? styles.chipOn : styles.chip} onClick={() => update({ cls: "" })}>
            all <span className={styles.n}>{without("membraneClass").length}</span>
          </button>
          {classCounts.map(([c, n]) => (
            <button key={c} type="button" className={filters.cls === c ? styles.chipOn : styles.chip} onClick={() => update({ cls: filters.cls === c ? "" : c })}>
              {c} <span className={styles.n}>{n}</span>
            </button>
          ))}
        </div>
        <div>
          <span className={styles.facetLabel}>Pick</span>
          {["", "built", "decided_not_built", "pending", "no_tag", "none"].map((st) => (
            <button key={st || "all"} type="button" className={filters.status === st ? styles.chipOn : styles.chip} onClick={() => update({ status: st })}>
              {st === "" ? "all" : st === "none" ? "no pick yet" : STATUS_LABEL[st as L1Site["status"]]}{" "}
              <span className={styles.n}>{statusCount(st)}</span>
            </button>
          ))}
        </div>
        {spKnown ? (
          <div>
            <span className={styles.facetLabel} title="Signal peptide / leader at the N-terminus, from the primary pick (or the design export when it says)">SP</span>
            {(spHasNone || filters.sp === "none"
              ? ["", "native", "igk_swap", "igk_res1", "none"]
              : ["", "native", "igk_swap", "igk_res1"]).map((k) => (
              <button key={k || "all"} type="button" className={filters.sp === k ? styles.chipOn : styles.chip} onClick={() => update({ sp: k })}>
                {k === "" ? "all" : SP_LABEL[k as keyof typeof SP_LABEL]} <span className={styles.n}>{spCount(k)}</span>
              </button>
            ))}
          </div>
        ) : null}
        {diffKnown ? (
          <div>
            <span className={styles.facetLabel} title="The ordered protein compared with the UniProt canonical sequence">UniProt</span>
            {[["", "all"], ["yes", "differs from canonical"], ["no", "same as canonical"]].map(([k, label]) => (
              <button key={k || "all"} type="button" className={filters.diff === k ? styles.chipOn : styles.chip} onClick={() => update({ diff: k })}>
                {label} <span className={styles.n}>{diffCount(k)}</span>
              </button>
            ))}
          </div>
        ) : null}
        <div>
          <span className={styles.facetLabel} title="Members you saved a review or suggestion on, in this browser">Reviewed</span>
          {[["", "all"], ["notmine", "not reviewed by me"], ["mine", "reviewed by me"]].map(([k, label]) => (
            <button key={k || "all"} type="button" className={filters.rev === k ? styles.chipOn : styles.chip} onClick={() => update({ rev: k })}>
              {label} <span className={styles.n}>{revCount(k)}</span>
            </button>
          ))}
        </div>
      </div>
      </details>
      </div>

      <div className={styles.split}>
        <div className={styles.listCol}>
          {/* On the list it filters. ↓ / ↑ step through the matches without leaving the
              box; Enter or Esc hands the keys back to the page. */}
          <input
            ref={searchRef}
            className={styles.search}
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                go(e.key === "ArrowDown" ? 1 : -1);
              } else if (e.key === "Enter") {
                e.preventDefault();
                if (pos < 0 && visible.length) goTo(0);
                e.currentTarget.blur();
              }
            }}
            placeholder="gene, class, rung, igk, l1-p…  ( / )"
            aria-label="Search members by gene, class, rung or SP type"
          />
          <div className={styles.listHead}>
            <span className={styles.listCount}>
              {groups.length} gene{groups.length === 1 ? "" : "s"} · {visible.length} member
              {visible.length === 1 ? "" : "s"}
            </span>
            {letterMsg ? <span className={styles.letterToast}>{letterMsg}</span> : null}
            <details
              className={styles.keyHelp}
              open={keyHelpOpen}
              onToggle={(e) => setKeyHelpOpen((e.currentTarget as HTMLDetailsElement).open)}
            >
              <summary>
                <span className={styles.keys}>
                  <span><kbd>←</kbd><kbd>→</kbd> member</span>
                  <span><kbd>A</kbd>–<kbd>Z</kbd> gene</span>
                  <span><kbd>1</kbd><kbd>2</kbd> view</span>
                  <span><kbd>?</kbd> keys</span>
                </span>
              </summary>
              <dl className={styles.keyTable}>
                <dt><kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd></dt>
                <dd>previous / next member in this filter (orthologs and isoforms included)</dd>
                <dt><kbd>A</kbd>–<kbd>Z</kbd></dt>
                <dd>jump to the next gene starting with that letter; press it again to walk them</dd>
                <dt><kbd>1</kbd>–<kbd>9</kbd></dt>
                <dd>switch structure view (tagged fold(s) first, then native model)</dd>
                <dt><kbd>Home</kbd> <kbd>End</kbd></dt>
                <dd>first / last member in this filter</dd>
                <dt><kbd>/</kbd></dt>
                <dd>focus the search box</dd>
                <dt><kbd>Esc</kbd></dt>
                <dd>leave a text field or close this list</dd>
                <dt><kbd>?</kbd></dt>
                <dd>show or hide this list</dd>
              </dl>
            </details>
          </div>
          <ol ref={listRef} className={styles.list} aria-label="Members">
            {/* One entry per gene: its library reference and any isoform or ortholog member
                are tabs on that entry, not unrelated rows, so the human reference and its
                cyno or mouse ortholog are read side by side. The ← → keys still walk member
                by member through the same order, so nothing is skipped. */}
            {groups.map((g) => {
              const primary = g.members.find((m) => m.candidate_set === "library_reference") ?? g.members[0];
              const onGene = current?.gene_symbol === g.gene_symbol;
              return (
                <li key={g.gene_symbol} className={styles.geneGroup}>
                  <button
                    type="button"
                    ref={onGene && current?.member_id === primary.member_id ? activeRowRef : undefined}
                    className={current?.member_id === primary.member_id ? styles.rowOn : styles.row}
                    onClick={() => update({ m: primary.design_id ?? primary.member_id })}
                  >
                    <strong>{g.gene_symbol}</strong>
                    <span className={styles.mono}>{primary.member_id}</span>
                    {g.members.length > 1 ? (
                      <span className={styles.badge} title={`${g.members.length} members of this gene in view`}>
                        {g.members.length} forms
                      </span>
                    ) : null}
                    <span className={styles.rowStatus}>
                      {primary.pick_status.length
                        ? primary.pick_status.map((s, i) => <StatusPill key={i} status={s} />)
                        : <span className={styles.muted}>no pick</span>}
                      {/* One dot per reviewer per scope, so a member whose a2 was
                          rejected and whose a1 passed shows both. The index carries no
                          sites, so the arm is read off the site id. */}
                      {(verdicts.get(primary.design_id ?? "") ?? []).map((r) => (
                        <span key={r.review_id} className={r.verdict === "good" ? styles.goodDot : styles.noDot} title={`${r.reviewer}: ${r.verdict} · ${r.site_id ? armLabel(r.site_id) ?? r.site_id : "the member"}${r.reason ? ` — ${r.reason}` : ""}`} />
                      ))}
                    </span>
                  </button>
                  {g.members.length > 1 ? (
                    <div className={styles.memberTabs}>
                      {g.members.map((m) => {
                        const on = current?.member_id === m.member_id;
                        return (
                          <button
                            key={m.member_id}
                            type="button"
                            ref={on ? activeRowRef : undefined}
                            className={on ? styles.memberTabOn : styles.memberTab}
                            title={`${m.member_id} · ${m.candidate_set ?? ""} · ${m.species ?? ""}`}
                            onClick={() => update({ m: m.design_id ?? m.member_id })}
                          >
                            {l1MemberRoleLabel(m)}
                            {on && m.member_id !== primary.member_id ? <span className={styles.mono}>· {m.member_id}</span> : null}
                            {(verdicts.get(m.design_id ?? "") ?? []).map((r) => (
                              <span key={r.review_id} className={r.verdict === "good" ? styles.goodDot : styles.noDot} />
                            ))}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </li>
              );
            })}
            {!visible.length ? <li className={styles.muted}>No member matches these filters.</li> : null}
          </ol>
        </div>

        <div className={styles.detail}>
          {current ? (
            <>
              <div className={styles.detailHead}>
                <button type="button" onClick={() => go(-1)} aria-label="Previous member">←</button>
                <div>
                  <h2 className={styles.h2}>
                    {current.gene_symbol} <span className={styles.mono}>{current.member_id}</span>
                    {current.design_id && current.design_id !== current.member_id ? (
                      <> <span className={`${styles.mono} ${styles.muted}`}>{current.design_id}</span></>
                    ) : null}
                  </h2>
                  <p className={styles.muted}>
                    {current.species} {current.candidate_set?.replace(/_/g, " ")} · {current.rung} · {current.membrane_class}
                    {current.n_tm != null ? ` · ${current.n_tm} TM` : ""}
                    {current.ordered_length_aa ? ` · ${current.ordered_length_aa} aa` : ""} ·{" "}
                    <a href={`/${encodeURIComponent(current.gene_symbol)}`}>gene page</a>
                    {pos >= 0 ? (
                      ` · ${pos + 1} of ${visible.length} in this view (← → keys)`
                    ) : (
                      <> · <span className={styles.badge}>not in the current filter</span></>
                    )}
                  </p>
                  {/* The gene's other forms, so the human reference and its cyno or mouse
                      ortholog are one click apart. Each keeps its own residue numbering —
                      the strip and every residue below are the selected member's. */}
                  {siblings.length > 1 ? (
                    <div className={styles.detailTabs} role="group" aria-label={`${current.gene_symbol} forms`}>
                      {siblings.map((m) => {
                        const on = m.member_id === current.member_id;
                        return (
                          <button
                            key={m.member_id}
                            type="button"
                            aria-pressed={on}
                            className={on ? styles.memberTabOn : styles.memberTab}
                            title={`${m.member_id}${m.ordered_length_aa ? ` · ${m.ordered_length_aa} aa` : ""} · its own numbering`}
                            onClick={() => update({ m: m.design_id ?? m.member_id })}
                          >
                            {l1MemberRoleLabel(m)}
                            {l1OrderedProteinLabel(topoFor(m)) ? <span className={styles.chipSub}>{l1OrderedProteinLabel(topoFor(m))}</span> : null}
                            {m.ordered_length_aa ? <span className={styles.mono}>{m.ordered_length_aa} aa</span> : null}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
                <button type="button" onClick={() => go(1)} aria-label="Next member">→</button>
              </div>
              {member ? (
                <MemberDetail
                  member={member}
                  topologyRow={l1MemberTopology(topologies, member)}
                  loadVersion={index.load.load_version}
                  reviews={reviews}
                  auth={auth}
                  reviewer={reviewer}
                  onEditName={editName}
                  drafts={drafts}
                  setDrafts={setDrafts}
                  onSaved={onSaved}
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
