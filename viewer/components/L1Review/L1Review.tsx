"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type KeyboardEvent as ReactKeyboardEvent, type SetStateAction } from "react";
import {
  PLACEMENT_LABEL,
  SOURCE_LABEL,
  STATUS_HELP,
  STATUS_LABEL,
  armLabel,
  countBy,
  currentMemberModels,
  explainDecision,
  explainRungContext,
  fetchL1Design,
  fetchL1ExternalTagSites,
  fetchL1GeneData,
  fetchL1IndexResult,
  fetchL1Reviews,
  filterIndex,
  groupByGene,
  l1MemberRoleLabel,
  l1MemberTopology,
  l1ModelMap,
  l1OrderedProteinLabel,
  l1PrimarySiteSignature,
  l1SiteLabel,
  l1SiteSignature,
  l1StructureUrl,
  latestVerdicts,
  nearestContactInfo,
  nextIndexByLetter,
  parseRefoldMetrics,
  renderableExternalTagSites,
  reviewScopeLabel,
  reviewStaleReason,
  sortSites,
  standingReviewIds,
  reviewErrorMessage,
  submitL1Review,
  SP_CONCERN_LABEL,
  SP_LABEL,
  indexSpStatus,
  memberHasSnorkel,
  memberSp,
  uniprotDiffers,
  uniprotDiffLines,
  l1ResidueSegments,
  memberToModel,
  modelToMember,
  visibleContacts,
  type L1Contact,
  type L1DesignFile,
  type L1ExternalTagSite,
  type L1GeneContext,
  type L1Index,
  type L1IndexFetch,
  type L1IndexMember,
  type L1Member,
  type L1Placement,
  type L1AltTagRow,
  type L1ReviewRow,
  type L1Reviews,
  type L1Site,
  type L1SpMetrics,
  type L1Structure,
} from "../../lib/l1-design";
import type { LibraryTopologyRow } from "../../lib/structure-viewer-types";
import { L1TopologyStrip, armColor, insertFlags } from "./L1TopologyStrip";
import { L1Structure3D, type L1Mark } from "./L1Structure3D";
import { curatedContactsAlign, fetchCuratedContacts, type CuratedContacts as CuratedContactsData } from "../../lib/l1-design";
import { fetchGeneSynonyms, matchingSynonym, type SynonymOverlay } from "../../lib/gene-jump-entries";
import { InfoTip } from "../InfoTip/InfoTip";
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
  agent: "#C2410C",
  tedman: "#E5342E",
  litTag: "#059669",
  litHigh: "#0F766E",
  litLower: "#0369A1",
  uniprot: "#1E1B4B",
  suggestion: "#FF1F8F",
  curated: "#5B21B6",
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

interface UrlFilters { m: string; rung: string; cls: string; status: string; q: string; sp: string; spConcern: string; diff: string; snorkel: string; rev: string }

function readUrl(): UrlFilters {
  if (typeof window === "undefined") return { m: "", rung: "", cls: "", status: "", q: "", sp: "", spConcern: "", diff: "", snorkel: "", rev: "" };
  const p = new URLSearchParams(window.location.search);
  return {
    m: p.get("m") ?? "", rung: p.get("rung") ?? "", cls: p.get("class") ?? "", status: p.get("status") ?? "",
    q: p.get("q") ?? "", sp: p.get("sp") ?? "", spConcern: p.get("sp_concern") ?? "", diff: p.get("diff") ?? "", snorkel: p.get("snorkel") ?? "", rev: p.get("reviewed") ?? "",
  };
}

function writeUrl(s: UrlFilters) {
  const p = new URLSearchParams();
  if (s.m) p.set("m", s.m);
  if (s.rung) p.set("rung", s.rung);
  if (s.cls) p.set("class", s.cls);
  if (s.status) p.set("status", s.status);
  if (s.sp) p.set("sp", s.sp);
  if (s.spConcern) p.set("sp_concern", s.spConcern);
  if (s.diff) p.set("diff", s.diff);
  if (s.snorkel) p.set("snorkel", s.snorkel);
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
  if (s.is_primary !== false) return armColor(s.site_id);
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

function isRedacted(v: string | null | undefined): boolean {
  return !v || /^withheld\b/i.test(v.trim());
}

const INTERNAL_NOISE_CHIPS = /^(?:order rule\s+\S+|GPCR=[01]|decided|loop best)$/i;

/**
 * Split semicolon-delimited status_detail outside parentheses so internal parentheticals
 * like `(built; flag, never hold, Becca 2026-11-22)` are never torn across two chips,
 * strip trailing internal date-stamped policy notes, and drop purely internal tokens
 * like `order rule order_1` or `GPCR=1`.
 */
export function formatStatusDetailChips(raw: string): string[] {
  const parts: string[] = [];
  let cur = "";
  let depth = 0;
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (ch === "(") depth += 1;
    else if (ch === ")" && depth > 0) depth -= 1;
    if (ch === ";" && depth === 0) {
      parts.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  if (cur) parts.push(cur);
  return parts
    .map((p) => p.replace(/\s*\([^)]*\b20\d{2}-\d{2}-\d{2}\b[^)]*\)\s*/g, " ").trim())
    .filter((p) => p && !INTERNAL_NOISE_CHIPS.test(p));
}

/**
 * Rewrite mature-chain `insert after 0` in Igκ-swap refold notes so it matches the
 * member's own residue numbering shown in the header, strip, and Tag sites cards.
 */
export function formatModelNote(
  note: string | null | undefined,
  site: Pick<L1Site, "leader" | "insert_after_residue"> | undefined,
): string | null {
  if (!note) return null;
  if (site?.leader?.toLowerCase().startsWith("igk") && site.insert_after_residue != null && site.insert_after_residue > 0) {
    return note.replace(/\binsert after 0\b/i, `insert after ${site.insert_after_residue} (mature N-terminus after Igκ)`);
  }
  return note;
}

/** Strip a parenthetical `(<why>)` from `sp.source` when `sp.why` is rendered separately below. */
export function formatSpSource(source: string, why: string | null): string {
  if (!why) return source;
  const suffix = ` (${why})`;
  return source.endsWith(suffix) ? source.slice(0, -suffix.length) : source;
}

export function WelcomeCard({
  totalMembers,
  onStart,
}: {
  totalMembers: number;
  onStart?: () => void;
}) {
  return (
    <section className={styles.welcome} aria-label="How to review">
      <h2 className={styles.welcomeTitle}>Welcome to the v1 library review</h2>
      <p className={styles.welcomeLede}>
        Each of the {totalMembers.toLocaleString()} members in the Deliverome surfaceome v1 library carries a proposed
        extracellular <strong>SpyTag003 + ALFA</strong> tag site, a folded 3D model, a topology strip, and known
        binding/contact sites.
      </p>
      <ol className={styles.welcomeSteps}>
        <li>
          <strong>Pick a protein</strong> on the left — search by gene symbol, alias (e.g. <code>CD20</code>,{" "}
          <code>Nav1.7</code>), class, or rung, or expand <strong>Filters</strong> above.
        </li>
        <li>
          <strong>Check the tag site</strong> on the 3D structure and topology bar: confirm the tag stays exposed and
          clear of ligand/partner contacts or signal-peptide cleavage.
        </li>
        <li>
          <strong>Record a verdict</strong> (<code>Site looks right</code>, <code>Concern</code>, or{" "}
          <code>Suggest another site</code> by clicking any residue on the 3D structure or topology bar).
        </li>
      </ol>
      {onStart ? (
        <div className={styles.welcomeActions}>
          <button type="button" className={styles.primary} onClick={onStart}>
            Start reviewing
          </button>
          <span className={styles.help}>or press → to open the first member</span>
        </div>
      ) : null}
    </section>
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
  const hasDecidedBy = !isRedacted(site.decided_by);
  const hasImplementedBy = !isRedacted(site.implemented_by);
  const hasSource = !isRedacted(site.source.path) && !isRedacted(site.source.commit);
  const redactedProvenance = !hasDecidedBy && !site.rationale;
  return (
    <div
      className={`${styles.site} ${primary ? styles.sitePrimary : ""}`}
      style={primary ? { borderLeftColor: siteColor(site) } : undefined}
    >
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
        {hasDecidedBy ? (<><dt>decided by</dt><dd>{site.decided_by}</dd></>) : null}
        {site.reason ? (<><dt>reason</dt><dd>{site.reason}</dd></>) : null}
        {site.rejected_alternative ? (<><dt>rejected alternative</dt><dd>{site.rejected_alternative}</dd></>) : null}
        {site.decision ? (<><dt>decision</dt><dd>{explainDecision(site.decision)}</dd></>) : null}
        {site.status_detail ? (() => {
          const parts = formatStatusDetailChips(site.status_detail);
          if (!parts.length) return null;
          return (
            <>
              <dt>detail</dt>
              <dd>
                {parts.length > 1 ? (
                  <ul className={styles.detailChips}>
                    {parts.map((part, idx) => <li key={idx}>{part}</li>)}
                  </ul>
                ) : parts[0]}
              </dd>
            </>
          );
        })() : null}
      </dl>
      <details className={styles.more}>
        <summary>{site.rationale || hasSource ? "rationale, scores and source" : "construct & site details"}</summary>
        {site.rationale ? (
          <Rationale value={site.rationale} />
        ) : redactedProvenance ? (
          <p className={styles.muted}>Internal design scores and provenance are withheld on this public API load.</p>
        ) : (
          <p className={styles.muted}>No scores recorded for this pick.</p>
        )}
        <dl className={styles.why}>
          {hasImplementedBy ? (<><dt>implemented by</dt><dd>{site.implemented_by}</dd></>) : null}
          <dt>cassette</dt>
          <dd>{site.cassette ?? "—"}{site.cassette_aa != null ? ` (${site.cassette_aa} aa inserted)` : ""}</dd>
          {hasSource ? (
            <>
              <dt>source</dt>
              <dd className={styles.mono}>
                {site.source.pr != null ? `design PR ${site.source.pr} (${site.source.pr_state ?? "?"}) · ` : ""}
                {site.source.commit.slice(0, 8)} · {site.source.path}
              </dd>
            </>
          ) : null}
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
  alt: { residue: string; cassette: string };
}

const EMPTY_DRAFT: Draft = {
  mode: "",
  reason: "",
  alt: { residue: "", cassette: "" },
};

const MODES: { value: Exclude<ReviewMode, "">; label: string; key: string }[] = [
  { value: "good", label: "Site looks right", key: "=" },
  { value: "no", label: "Concern", key: "-" },
  { value: "alt", label: "Suggest another site", key: "." },
];

export function ReviewPanel({
  member,
  loadVersion,
  reviews,
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
  const [honeypot, setHoneypot] = useState("");
  const commentRef = useRef<HTMLTextAreaElement | null>(null);
  const residueRef = useRef<HTMLInputElement | null>(null);
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
  const staleStandingReasons = useMemo(() => {
    const reasons = new Set<string>();
    for (const r of mine) {
      if (!standing.has(r.review_id)) continue;
      const why = reviewStaleReason(r, member, loadVersion);
      if (why) reasons.add(why);
    }
    return [...reasons];
  }, [mine, standing, member, loadVersion]);
  const fieldId = `l1-review-${key}`;

  function problem(): string | null {
    if (!name) return "Add your name at the top of the page first.";
    if (draft.mode === "no" && !draft.reason.trim()) return "Say what is wrong in the comment.";
    if (draft.mode === "alt") {
      if (draft.alt.residue === "") return "Give the residue the tag goes after, or click one on the structure.";
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
    const primarySig = l1PrimarySiteSignature(sites);
    const inviteToken = store.get("l1-review-invite");
    const base = {
      reviewer: name, member_id: member.member_id, design_id: member.design_id, gene_symbol: member.gene_symbol,
      sequence_sha256: member.sequence_sha256 ?? null, load_version: loadVersion,
      ...(honeypot ? { website: honeypot } : {}),
    };
    const reason = draft.reason.trim() || null;
    setSaving(true);
    try {
      if (draft.mode === "alt") {
        const residue = draft.alt.residue === "" ? null : Number(draft.alt.residue);
        const placement: L1Placement =
          residue === 0
            ? "n_term"
            : residue != null && member.ordered_length_aa != null && residue >= member.ordered_length_aa
              ? "c_term"
              : "internal";
        const cassette = draft.alt.cassette || null;
        const r = await submitL1Review(API_BASE, {
          ...base, kind: "alt_tag", placement, insert_after_residue: residue,
          cassette_variant: cassette, reason, site_signature: primarySig,
        }, inviteToken);
        if (!r.ok) return setMsg({ ok: false, text: `Not saved: ${reviewErrorMessage(r.error)}` });
        const row: L1AltTagRow = {
          suggestion_id: r.id, created_at: r.created_at, ...base, design_id: member.design_id,
          insert_after_residue: residue, placement, cassette_variant: cassette, reason, site_signature: primarySig,
        };
        patch({ mode: "", reason: "", alt: EMPTY_DRAFT.alt });
        setMsg({ ok: true, text: "Saved — thank you. Your suggested site is listed below." });
        onSaved({ alt_tags: [row] });
        return;
      }
      const v = draft.mode;
      const site = siteId || null; // "" is the member as a whole, stored as NULL
      const targetSite = site ? sites.find((s) => s.site_id === site) : undefined;
      const siteSig = targetSite ? l1SiteSignature(targetSite) : primarySig;
      const r = await submitL1Review(API_BASE, {
        ...base, kind: "verdict", verdict: v, reason, site_id: site, site_signature: siteSig,
      }, inviteToken);
      if (!r.ok) return setMsg({ ok: false, text: `Not saved: ${reviewErrorMessage(r.error)}` });
      const row: L1ReviewRow = {
        review_id: r.id, created_at: r.created_at, ...base, design_id: member.design_id,
        site_id: site, verdict: v, reason, site_signature: siteSig,
      };
      patch({ mode: "", reason: "" });
      const about = reviewScopeLabel(site, sites, member.ordered_length_aa);
      setMsg({ ok: true, text: `Saved — thank you. ${v === "good" ? "Looks right" : "Concern"} on ${about}.` });
      onSaved({ reviews: [row] });
    } finally {
      setSaving(false);
    }
  }

  const submitRef = useRef(submit);
  submitRef.current = submit;
  const draftModeRef = useRef(draft.mode);
  draftModeRef.current = draft.mode;

  // Fast verdict shortcuts without colliding with A–Z gene jumping:
  // `=` / `+` = Site looks right, `-` = Concern (focuses comment), `.` = Suggest another site,
  // and ⌘/Ctrl + Enter submits from anywhere once a verdict is selected.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        if (draftModeRef.current) {
          e.preventDefault();
          submitRef.current();
        }
        return;
      }
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "=" || e.key === "+") {
        e.preventDefault();
        patch({ mode: draftModeRef.current === "good" ? "" : "good" });
        setMsg(null);
      } else if (e.key === "-") {
        e.preventDefault();
        const next = draftModeRef.current === "no" ? "" : "no";
        patch({ mode: next });
        setMsg(null);
        if (next === "no") window.setTimeout(() => commentRef.current?.focus(), 0);
      } else if (e.key === ".") {
        e.preventDefault();
        const next = draftModeRef.current === "alt" ? "" : "alt";
        patch({ mode: next });
        setMsg(null);
        if (next === "alt") window.setTimeout(() => residueRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [patch]);

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
      {staleStandingReasons.length > 0 ? (
        <p className={styles.staleBanner} role="status">
          <strong>Previous review is out of date</strong> ({staleStandingReasons.join("; ")}) — please re-review the current construct.
        </p>
      ) : null}
      {/* Toggle buttons, not radios: a focused radio takes the arrow keys, which left a
          reviewer pressing → to change member and changing the verdict instead. */}
      <div className={styles.verdictRow}>
        <div className={styles.segmented} role="group" aria-label="Your verdict">
          {MODES.map((m) => {
            const on = draft.mode === m.value;
            const tone = m.value === "good" ? styles.segGood : m.value === "no" ? styles.segNo : "";
            return (
              <button
                key={m.value}
                type="button"
                aria-pressed={on}
                className={on ? `${styles.segOn} ${tone}` : styles.seg}
                title={`${m.label} (shortcut: ${m.key})`}
                onClick={() => { patch({ mode: on ? "" : m.value }); setMsg(null); }}
              >
                {m.label} <kbd className={styles.segKey}>{m.key}</kbd>
              </button>
            );
          })}
        </div>
        {draft.mode === "good" || draft.mode === "no" ? (
          // A verdict on one arm rather than on the member: the r2 agent round rejects
          // arms, not members, so "a2 is in the pore, a1 and a3 are fine" needs somewhere to go.
          <label className={styles.scope}>
            tag site
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
            <span className={styles.altInputRow}>
              <input
                ref={residueRef}
                type="number"
                min={0}
                max={member.ordered_length_aa ?? undefined}
                step={1}
                value={draft.alt.residue}
                onChange={(e) => setAlt({ residue: e.target.value.replace(/[^0-9]/g, "") })}
                aria-describedby={`${fieldId}-residue-help`}
              />
              {draft.alt.residue !== "" ? (
                <button
                  type="button"
                  className={styles.clearBtn}
                  onClick={() => setAlt({ residue: "" })}
                  aria-label="Clear suggested residue"
                >
                  Clear
                </button>
              ) : null}
            </span>
            <span id={`${fieldId}-residue-help`} className={styles.help}>
              or click a residue on the structure or topology bar
              {member.ordered_length_aa ? ` · 0–${member.ordered_length_aa}` : ""}
            </span>
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
        ref={commentRef}
        id={`${fieldId}-comment`}
        className={styles.reason}
        aria-label="Comment"
        placeholder={placeholder}
        value={draft.reason}
        onChange={(e) => patch({ reason: e.target.value })}
        onFocus={() => setCommentOpen(true)}
        onBlur={() => setCommentOpen(false)}
        // One line until it is used: open while focused or holding text.
        rows={commentOpen || draft.reason ? 3 : 1}
      />
      <input
        type="text"
        name="website"
        value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
      />
      <div className={styles.submitRow}>
        <button type="button" className={styles.primary} disabled={!draft.mode || saving} onClick={submit}>
          {saving ? "Saving…" : "Submit"}
        </button>
        <span className={styles.help}>
          {draft.mode ? "⌘/Ctrl + Enter to submit" : "Choose a verdict (= / - / .) to submit"}
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
            {mine.map((r) => {
              const isStanding = standing.has(r.review_id);
              const staleWhy = reviewStaleReason(r, member, loadVersion);
              const cls = !isStanding ? styles.superseded : staleWhy ? styles.staleRow : undefined;
              return (
                <li key={r.review_id} className={cls}>
                  <span className={r.verdict === "good" ? styles.goodText : styles.noText}>{r.verdict === "good" ? "looks right" : "concern"}</span>{" "}
                  {staleWhy ? <span className={styles.staleBadge} title={staleWhy}>out of date: {staleWhy}</span> : null}
                  {staleWhy ? " " : ""}
                  · {reviewScopeLabel(r.site_id, sites, member.ordered_length_aa)} · {r.reviewer} ·{" "}
                  {r.created_at.slice(0, 16).replace("T", " ")}
                  {isStanding ? "" : " · superseded by a later row"}
                  {r.reason ? ` · ${r.reason}` : ""}
                </li>
              );
            })}
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

const CONTACT_SIDE_LABEL: Record<string, string> = {
  O: "outside",
  I: "inside",
  M: "TM helix",
  S: "signal peptide",
  B: "β-strand",
};

function fmtContactTokens(raw: string | null | undefined): string {
  if (!raw) return "—";
  return raw
    .split(/\s*[;,]\s*/)
    .filter(Boolean)
    .map((t) => t.replace(/_/g, " "))
    .join(", ");
}

function fmtContactSide(c: Pick<L1Contact, "in_extracellular" | "topology_state">): string {
  if (c.in_extracellular) return "outside";
  if (!c.topology_state) return "—";
  return CONTACT_SIDE_LABEL[c.topology_state] ?? c.topology_state;
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
          {rows.map((c) => {
            const pmids = (c.pmids ?? "").split(/[;,\s]+/).filter(Boolean);
            return (
              <tr key={`${c.residue}-${c.source}`}>
                <td className={`${styles.mono} ${styles.cellNowrap}`}>
                  {c.aa ?? ""}{c.residue}
                  {c.canonical_residue != null && c.canonical_residue !== c.residue ? ` (canon. ${c.canonical_residue})` : ""}
                </td>
                <td className={styles.cellNowrap}>
                  <span className={styles.swatch} style={{ background: contactColor(c) }} />
                  {c.source === "literature_agent" ? "literature" : "UniProt"}
                </td>
                <td className={styles.cellNowrap}>
                  {c.confidence_tier}{c.ion_site ? " · ion" : ""}{c.additive_only ? " · additive" : ""}
                </td>
                <td className={styles.cellSoft}>{fmtContactTokens(c.evidence_types)}</td>
                <td className={styles.cellNowrap}>{fmtContactTokens(c.contact_classes)}</td>
                <td className={styles.cellWrap}>{c.ligands ?? "—"}</td>
                <td className={styles.cellNowrap}>{fmtContactSide(c)}</td>
                <td className={styles.cellPmids}>
                  {pmids.length
                    ? pmids.map((p) => (
                        <a key={p} href={`https://pubmed.ncbi.nlm.nih.gov/${p}/`} target="_blank" rel="noreferrer" className={styles.pmid}>{p}</a>
                      ))
                    : "—"}
                </td>
              </tr>
            );
          })}
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
                <td className={styles.cellSoft}><span className={styles.swatch} style={{ background: COLORS.curated }} />{c.partner_label ?? c.partner}</td>
                <td className={styles.cellNowrap}>{c.source}</td>
                <td className={`${styles.mono} ${styles.cellSoft}`}>{(c.positions ?? []).length} ({(c.positions ?? []).slice(0, 8).join(", ")}{(c.positions ?? []).length > 8 ? ", …" : ""})</td>
                <td className={styles.cellWrap}>{c.context ?? "—"}</td>
                <td className={styles.cellNowrap}>{c.reference ? <a href={c.reference} target="_blank" rel="noreferrer">link</a> : "—"}</td>
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

/** Structured SignalP 6 vs DeepTMHMM v1 pre-/post-tag SP metrics for N-after-SP constructs. */
export function SpMetricsBox({ metrics }: { metrics: L1SpMetrics }) {
  const pct = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2));
  const isConcerning = metrics.concern === "concerning";
  const postLabel = metrics.post_leader === "igk" ? "Post-tag (Igκ)" : "Post-tag (native SP)";
  const preCut =
    metrics.signalp_pre_cut != null
      ? `@${metrics.signalp_pre_cut}`
      : metrics.signalp_pre_pred && metrics.signalp_pre_pred !== "SP"
        ? `none (${metrics.signalp_pre_pred})`
        : "—";
  const spread = metrics.cut_spread_aa;
  const delta = metrics.cleavage_prob_delta;
  const reasons = (metrics.concern_reasons ?? []).filter(Boolean);
  return (
    <div className={styles.spMetrics}>
      <div className={styles.spMetricsHead}>
        <span className={isConcerning ? styles.spConcernWarn : styles.spConcernClean}>
          {isConcerning ? "SP concerning" : "SP clean"}
        </span>
        <span className={styles.spMetricsCut}>
          DeepTMHMM v1 {metrics.deeptmhmm_v1_cut != null ? `@${metrics.deeptmhmm_v1_cut}` : "—"} · SignalP 6 pre {preCut}
          {spread != null && spread > 0 ? ` (Δ ${spread} aa)` : spread === 0 ? " (exact match)" : ""}
        </span>
        <InfoTip label="About signal peptide checks">
          Compares DeepTMHMM v1 and SignalP 6 predicted cleavage sites before and after inserting the N-terminal tag.
          SP p = signal peptide probability; cut p = cleavage-site probability; Δ = distance between the two predictors&apos; cut sites.
        </InfoTip>
      </div>
      <div className={styles.spMetricsRows}>
        <span>
          <strong>Pre-tag SignalP 6:</strong> SP p={pct(metrics.signalp_pre_sp_prob)} · cut p={pct(metrics.signalp_pre_cs_prob)}
        </span>
        <span>
          <strong>{postLabel}:</strong> cut {metrics.signalp_post_cut != null ? `@${metrics.signalp_post_cut}` : "—"} · SP p={pct(metrics.signalp_post_sp_prob)} · cut p={pct(metrics.signalp_post_cs_prob)}
          {delta != null ? ` (${delta >= 0 ? "+" : ""}${delta.toFixed(2)})` : ""}
        </span>
      </div>
      {isConcerning && reasons.length ? (
        <div className={styles.spConcernReasons}>
          <strong>Flagged:</strong> {reasons.join(" · ")}
        </div>
      ) : null}
    </div>
  );
}

/** Clarifies when an automated refold screen flagged a built construct that was reviewed and kept. */
export function RefoldFlagBanner({
  model,
  site,
}: {
  model: Pick<L1Structure, "kind" | "refold_verdict" | "note"> | undefined;
  site: Pick<L1Site, "status"> | undefined;
}) {
  if (!model || model.kind !== "tagged" || model.refold_verdict !== "fail" || site?.status !== "built") return null;
  return (
    <p className={styles.refoldFlagBanner} role="note">
      <strong>Automated refold screen flagged (kept as built):</strong>{" "}
      {model.note ? `${model.note}. ` : ""}
      This construct was reviewed and retained in library v1 (flagged for experimental follow-up — e.g., low-confidence AF2 tag compaction while the native fold and/or ALFA control remain exposed).
    </p>
  );
}

/** Label for a structure view tab. When a member carries multiple tagged refolds,
 *  name the arm/insertion residue so tabs are distinguishable before clicking. */
export function structureTabLabel(
  m: Pick<L1Structure, "kind" | "site_id" | "mean_plddt" | "refold_verdict" | "note">,
  sites: readonly (Pick<L1Site, "site_id" | "insert_after_residue"> & { status?: L1Site["status"] })[],
  multiFold: boolean,
): string {
  const site = m.site_id ? sites.find((s) => s.site_id === m.site_id) : undefined;
  let base = m.kind === "tagged" ? "Fold" : "Native";
  if (m.kind === "tagged" && multiFold) {
    const arm = m.site_id ? armLabel(m.site_id) : null;
    const noteRes = m.note ? /insert after (\d+)/i.exec(m.note)?.[1] : null;
    const res = site?.insert_after_residue ?? (noteRes != null ? Number(noteRes) : null);
    const tag =
      arm && res != null ? `${arm} · ${res}`
        : arm ? arm
          : res != null ? `after ${res}`
            : null;
    if (tag) base = `Fold (${tag})`;
  }
  const verdict =
    m.refold_verdict === "fail" && site?.status === "built"
      ? "refold flag (kept)"
      : m.refold_verdict ?? null;
  return [
    base,
    m.mean_plddt != null ? `pLDDT ${m.mean_plddt.toFixed(0)}` : null,
    verdict,
  ].filter(Boolean).join(" · ");
}

/**
 * Consolidates why this tagging strategy was picked, quantitative refold QC metrics,
 * nearest-contact clearance, and surface-biology considerations (proteolytic cleavage/shedding,
 * co-receptors, epitope masking, oligomerization, GPI/dual-anchor topology) from the gene record.
 */
export function DesignContextCard({
  member,
  topology,
  model,
  geneContext,
  curatedPositions,
}: {
  member: Pick<L1Member, "gene_symbol" | "rung" | "sites" | "contacts">;
  topology: string | null | undefined;
  model: Pick<L1Structure, "kind" | "site_id" | "mean_plddt" | "note"> | undefined;
  geneContext: L1GeneContext | null | undefined;
  curatedPositions: ReadonlySet<number>;
}) {
  const primary = member.sites.find((s) => s.is_primary !== false);
  const strategy = explainRungContext(member, topology, geneContext);
  const metrics = parseRefoldMetrics(model?.note, primary?.status_detail);
  const nearest = nearestContactInfo(primary?.insert_after_residue, member.contacts ?? [], curatedPositions);
  const hasBioFlags = !!(
    geneContext?.shedding?.present ||
    geneContext?.coReceptor ||
    geneContext?.epitopeMasking ||
    geneContext?.homoOligomer
  );
  if (!strategy && !metrics.length && !nearest && !geneContext?.summary && !hasBioFlags) return null;

  return (
    <div className={styles.contextCard}>
      {strategy ? (
        <p className={styles.contextStrategy}>
          <strong>Why this strategy:</strong> {strategy}
        </p>
      ) : null}
      {metrics.length || nearest ? (
        <div className={styles.metricStrip} aria-label="Refold QC and contact clearance">
          {model?.kind === "tagged" && model.mean_plddt != null ? (
            <span
              className={model.mean_plddt >= 70 ? styles.metricPass : styles.metricWarn}
              title="Mean predicted local distance difference test (pLDDT) across the tagged refold."
            >
              pLDDT {model.mean_plddt.toFixed(1)}
            </span>
          ) : null}
          {metrics.map((m) => (
            <span
              key={m.label}
              className={m.tone === "pass" ? styles.metricPass : m.tone === "warn" ? styles.metricWarn : styles.metricNeutral}
              title={m.help}
            >
              {m.label} {m.value}
            </span>
          ))}
          {nearest ? (
            <span
              className={nearest.distanceAa <= 10 ? styles.metricWarn : styles.metricPass}
              title={`Sequence distance from the chosen tag insertion to the nearest annotated contact: ${nearest.label}.`}
            >
              {nearest.distanceAa <= 10 ? "⚠ " : ""}Nearest contact: {nearest.distanceAa} aa ({nearest.label})
            </span>
          ) : null}
        </div>
      ) : null}
      {geneContext?.summary || hasBioFlags ? (
        <div className={styles.bioSection}>
          {geneContext?.summary ? (
            <p className={styles.bioSummary}>
              <strong>Protein context:</strong> {geneContext.summary}{" "}
              <a href={`/${encodeURIComponent(member.gene_symbol)}`} target="_blank" rel="noreferrer">
                full gene page
              </a>
            </p>
          ) : null}
          {hasBioFlags ? (
            <ul className={styles.bioFlags}>
              {geneContext?.shedding?.present ? (
                <li>
                  <span className={styles.bioTagWarn}>Proteolytic cleavage / shedding</span>
                  {geneContext.shedding.sheddase ? ` (${geneContext.shedding.sheddase})` : ""}
                  {geneContext.shedding.mechanism
                    ? ` — ${geneContext.shedding.mechanism}`
                    : geneContext.shedding.rationale
                      ? ` — ${geneContext.shedding.rationale}`
                      : ""}
                </li>
              ) : null}
              {geneContext?.coReceptor ? (
                <li>
                  <span className={styles.bioTagWarn}>Co-receptor / partner</span>
                  {geneContext.coReceptor.partners.length ? ` (${geneContext.coReceptor.partners.join(", ")})` : ""}
                  {geneContext.coReceptor.rationale ? ` — ${geneContext.coReceptor.rationale}` : ""}
                </li>
              ) : null}
              {geneContext?.epitopeMasking ? (
                <li>
                  <span className={styles.bioTagNeutral}>
                    Epitope masking: {geneContext.epitopeMasking.mechanisms.join(", ")}
                  </span>
                  {geneContext.epitopeMasking.rationale ? ` — ${geneContext.epitopeMasking.rationale}` : ""}
                </li>
              ) : null}
              {geneContext?.homoOligomer ? (
                <li>
                  <span className={styles.bioTagNeutral}>
                    Homo-oligomer{geneContext.homoOligomer.stoichiometry ? ` (${geneContext.homoOligomer.stoichiometry}-mer)` : ""}
                  </span>
                  {geneContext.homoOligomer.isEcdOnly ? " — predicted ectodomain self-association" : " — predicted self-association"}
                  {geneContext.homoOligomer.source ? ` (${geneContext.homoOligomer.source})` : ""}
                </li>
              ) : null}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Compact reference table of published literature tag sites and Tedman screen-validated controls. */
export function ExternalTagSitesTable({
  sites,
  aligned,
}: {
  sites: readonly L1ExternalTagSite[];
  aligned: boolean;
}) {
  if (!sites.length) return null;
  const posLabel = (s: L1ExternalTagSite) => {
    if (s.site_kind === "terminal_n") {
      return s.insert_after_residue != null && s.insert_after_residue > 0
        ? `N-term (after ${s.insert_after_residue})`
        : "N-terminus";
    }
    if (s.site_kind === "terminal_c") return "C-terminus";
    if (s.insert_after_residue != null) {
      const before = s.residue_before ? `${s.residue_before}${s.insert_after_residue}` : `${s.insert_after_residue}`;
      const after = s.residue_after ? `${s.residue_after}${s.insert_after_residue + 1}` : `${s.insert_after_residue + 1}`;
      return `between ${before} and ${after}`;
    }
    return s.residue_label ?? "—";
  };
  return (
    <div className={styles.extTagSection}>
      <h4 className={styles.h4}>
        Literature &amp; Tedman tag sites ({sites.length})
        {!aligned ? (
          <span className={styles.muted}> — numbered on human canonical (listed, not drawn on this isoform/ortholog)</span>
        ) : null}
      </h4>
      <div className={styles.tablewrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>Source</th><th>Position</th><th>Tag</th><th>Rationale / validation</th><th>Refs</th></tr>
          </thead>
          <tbody>
            {sites.map((s) => {
              const isTedman = s.provenance === "screen_validated";
              const refs = (s.sources ?? []).filter((src) => src.pmid || src.doi);
              return (
                <tr key={s.site_id}>
                  <td className={styles.cellNowrap}>
                    <span className={styles.swatch} style={{ background: isTedman ? COLORS.tedman : COLORS.litTag }} />
                    {isTedman ? "Tedman control" : "Literature"}
                  </td>
                  <td className={`${styles.mono} ${styles.cellNowrap}`}>{posLabel(s)}</td>
                  <td className={styles.cellNowrap}>{s.tag_type || "—"}</td>
                  <td className={styles.cellWrap}>
                    {s.rationale || s.functional_impact_measured || (isTedman ? "Tedman GPCR N-terminal HA surface-expression control" : "—")}
                    {s.validation_level ? <span className={styles.muted}> · {s.validation_level.replace(/_/g, " ")}</span> : null}
                  </td>
                  <td className={styles.cellPmids}>
                    {refs.length
                      ? refs.slice(0, 3).map((src, i) =>
                          src.pmid ? (
                            <a key={i} href={`https://pubmed.ncbi.nlm.nih.gov/${src.pmid}/`} target="_blank" rel="noreferrer" className={styles.pmid}>
                              {src.pmid}
                            </a>
                          ) : src.doi ? (
                            <a key={i} href={`https://doi.org/${src.doi}`} target="_blank" rel="noreferrer" className={styles.pmid}>
                              DOI
                            </a>
                          ) : null,
                        )
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MemberDetail({
  member,
  topologyRow,
  geneContext,
  externalTagSites,
  loadVersion,
  reviews,
  reviewer,
  onEditName,
  drafts,
  setDrafts,
  onSaved,
}: {
  member: L1Member;
  topologyRow: LibraryTopologyRow | null;
  geneContext: L1GeneContext | null;
  externalTagSites: readonly L1ExternalTagSite[];
  loadVersion: string;
  reviews: L1Reviews | null;
  reviewer: string;
  onEditName: () => void;
  drafts: Record<string, Draft>;
  setDrafts: Dispatch<SetStateAction<Record<string, Draft>>>;
  onSaved: (saved: Partial<L1Reviews>) => void;
}) {
  const sites = sortSites(member.sites);
  // Current-pick fold(s) first and open by default, then native; earlier/unlisted sweep
  // refolds are excluded altogether.
  const models = useMemo(
    () => currentMemberModels(member.structures, member.sites),
    [member.structures, member.sites],
  );
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [modelId, setModelId] = useState<string>("");
  const [showAlts, setShowAlts] = useState(true);
  const [showExternalTags, setShowExternalTags] = useState(true);
  const [showContacts, setShowContacts] = useState(true);
  const [showHidden, setShowHidden] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);
  // A residue clicked on either model, as {r, n}: n changes on every click so clicking
  // the same residue again (after typing another) still reaches the review card.
  const [picked, setPicked] = useState<{ r: number; n: number } | null>(null);
  // The arm being looked at (clicked on the strip or a tag-site card).
  const [focusSite, setFocusSite] = useState<string | null>(null);
  const [resetSeq, setResetSeq] = useState(0);
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
  const nativeModel = models.find((m) => m.kind === "native");
  const nativeUrl = nativeModel ? l1StructureUrl(nativeModel) : null;

  // Marks are placed through the model's own residue map, so picks, the focused arm and
  // the reviewer's suggestion show on the fold as well as on the native model.
  // Contacts stay on the native model, whose numbering is the member's own.
  const segments = model ? l1ResidueSegments(member, model) : null;
  const toModel = (r: number) => memberToModel(r, segments);
  const canOverlay = !!(model?.kind === "tagged" && nativeModel && nativeUrl && segments?.length);
  const overlayPairs = useMemo<[number, number][] | null>(() => {
    if (!showOverlay || !canOverlay || !segments || !nativeModel) return null;
    const natOff = nativeModel.residue_offset ?? 0;
    const pairs: [number, number][] = [];
    for (const seg of segments) {
      for (let r = seg.unpLo; r <= seg.unpHi; r += 1) {
        pairs.push([r + natOff, r + seg.offset]);
      }
    }
    return pairs.length >= 3 ? pairs : null;
  }, [showOverlay, canOverlay, segments, nativeModel]);
  const draftKey = member.design_id ?? member.member_id;
  const draft = drafts[draftKey];
  const suggested =
    draft?.mode === "alt" && draft.alt.residue !== "" && Number.isFinite(Number(draft.alt.residue))
      ? Number(draft.alt.residue)
      : null;
  const clearSuggested = useCallback(() => {
    setPicked(null);
    setDrafts((d) => {
      const cur = d[draftKey];
      if (!cur) return d;
      return { ...d, [draftKey]: { ...cur, alt: { ...cur.alt, residue: "" } } };
    });
  }, [draftKey, setDrafts]);
  const marks: L1Mark[] = [];
  if (segments) {
    if (showContacts && curatedAligned && curatedGene) {
      for (const c of curatedGene.sites) {
        const partner = c.partner_label ?? c.partner;
        const hover = `curated contact${partner ? `: ${partner}` : ""}${c.source ? ` (${c.source})` : ""}`;
        for (const p of c.positions ?? []) {
          const resi = toModel(p);
          if (resi != null) marks.push({ resi, color: COLORS.curated, radius: 2.8, stick: true, hover });
        }
      }
    }
    if (showContacts) {
      for (const c of visibleContacts(member.contacts ?? [], showHidden)) {
        const resi = toModel(c.residue);
        const kind =
          c.source === "uniprot_binding"
            ? "UniProt binding site"
            : c.confidence_tier === "lower"
              ? "lit contact (model)"
              : "lit contact";
        const hover = `${kind}${c.ligands ? `: ${c.ligands}` : ""}`;
        if (resi != null) marks.push({ resi, color: contactColor(c), radius: 2.8, stick: true, hover });
      }
    }
  }
  const differs = uniprotDiffers(member);
  const externalAligned = differs === false;
  const renderableExternal = useMemo(
    () =>
      externalAligned && member.ordered_length_aa
        ? renderableExternalTagSites(externalTagSites, member.ordered_length_aa)
        : [],
    [externalAligned, externalTagSites, member.ordered_length_aa],
  );
  // External literature & Tedman screen-validated tag sites (drawn before current picks so
  // the primary pick sphere stays prominent when they share a residue).
  if (segments && showExternalTags && renderableExternal.length) {
    for (const ext of renderableExternal) {
      const resi = toModel(ext.residue);
      if (resi == null) continue;
      marks.push({
        resi,
        color: ext.isTedman ? COLORS.tedman : COLORS.litTag,
        radius: ext.isTedman ? 2.8 : 2.6,
        label: ext.isTedman ? `Tedman ${ext.tagType}` : `lit ${ext.tagType}`,
        hover: ext.isTedman
          ? `Tedman control (${ext.tagType}, res ${ext.residue})`
          : `literature tag (${ext.tagType}, after ${ext.residue})`,
      });
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
      hover: `${s.is_primary !== false ? "tag pick" : "alt site"} (after ${s.insert_after_residue})`,
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
      if (e.key === "0") {
        e.preventDefault();
        setResetSeq((n) => n + 1);
        return;
      }
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
          <span className={styles.muted}> · from {formatSpSource(sp.source, sp.why)}</span>
          {sp.why ? <span className={styles.spWhy}>{sp.why}</span> : null}
          {member.sp_metrics ? <SpMetricsBox metrics={member.sp_metrics} /> : null}
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
          {differs === null ? null : differs ? (
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
          onPickResidue={(r) => setPicked({ r, n: Date.now() })}
          suggestedResidue={suggested}
          onClearSuggested={suggested != null ? clearSuggested : undefined}
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
        <div className={styles.structureHeader}>
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
          <div className={styles.structureControls} aria-label="Structure overlays">
            {canOverlay ? (
              <span className={styles.ctrlGroup}>
                <label className={showOverlay ? styles.ctrlOn : styles.ctrl}>
                  <input type="checkbox" checked={showOverlay} onChange={(e) => setShowOverlay(e.target.checked)} />
                  Native overlay
                </label>
                <InfoTip align="end" label="About native overlay">
                  Superpose the native protein backbone (translucent slate ghost) onto the tagged refold by Kabsch Cα alignment over shared native residues.
                </InfoTip>
              </span>
            ) : null}
            <span className={styles.ctrlGroup}>
              <label className={showAlts ? styles.ctrlOn : styles.ctrl}>
                <input type="checkbox" checked={showAlts} onChange={(e) => setShowAlts(e.target.checked)} />
                Alternatives
              </label>
              <InfoTip align="end" label="About alternative sites">
                Candidate tag sites proposed by the ranker (gold) and agent proposer (burnt orange) that were not chosen as the primary pick.
              </InfoTip>
            </span>
            {renderableExternal.length > 0 ? (
              <span className={styles.ctrlGroup}>
                <label className={showExternalTags ? styles.ctrlOn : styles.ctrl}>
                  <input type="checkbox" checked={showExternalTags} onChange={(e) => setShowExternalTags(e.target.checked)} />
                  Lit &amp; Tedman tags
                </label>
                <InfoTip align="end" label="About literature and Tedman tag sites">
                  Published extracellular tag insertion sites from literature (emerald) and Tedman GPCR N-terminal HA controls (red) aligned to the human canonical sequence.
                </InfoTip>
              </span>
            ) : null}
            {segments ? (
              <>
                <span className={styles.ctrlGroup}>
                  <label className={showContacts ? styles.ctrlOn : styles.ctrl}>
                    <input type="checkbox" checked={showContacts} onChange={(e) => setShowContacts(e.target.checked)} />
                    Contacts
                  </label>
                  <InfoTip align="end" label="About contact sites">
                    Extracellular ligand/partner contact residues from curated PDB/PDBe structures (violet), UniProt binding sites (indigo), and agent-extracted literature (teal/cyan).
                  </InfoTip>
                </span>
                {showContacts ? (
                  <span className={styles.ctrlGroup}>
                    <label className={showHidden ? styles.ctrlOn : styles.ctrl}>
                      <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />
                      Ions &amp; additives
                    </label>
                    <InfoTip align="end" label="About ions and crystallization additives">
                      Include metal/ion coordination sites (e.g. Ca²⁺, Zn²⁺) and crystallization buffer additives (e.g. PEG, glycerol, lipids). Hidden by default so real ligand/protein interfaces stay clear.
                    </InfoTip>
                  </span>
                ) : null}
              </>
            ) : (() => {
              const nativeIdx = models.findIndex((m) => m.kind === "native");
              const keyHint = nativeIdx >= 0 && nativeIdx < 9 ? ` (key ${nativeIdx + 1})` : "";
              return <span className={styles.muted}>contacts: native{keyHint}</span>;
            })()}
          </div>
        </div>
        {url ? (
          <L1Structure3D
            pdbUrl={url}
            span={span}
            marks={marks}
            cassette={cassette}
            onPick={segments ? pick : undefined}
            modelToMemberResi={segments ? (resi) => modelToMember(resi, segments) : undefined}
            focusResi={(() => {
              const f = sites.find((x) => x.site_id === focusSite);
              return f?.insert_after_residue != null ? toModel(f.insert_after_residue) : null;
            })()}
            onReset={() => setFocusSite(null)}
            resetSeq={resetSeq}
            topology={topology || null}
            map={modelMap}
            modelLength={model?.model_length_aa ?? null}
            nonNativeLabel={
              pickLeader?.toLowerCase().startsWith("igk")
                ? "Igκ leader construct residues (not this protein's own)"
                : "added residues (not this protein's own)"
            }
            overlayPdbUrl={showOverlay && canOverlay ? nativeUrl : null}
            overlayPairs={overlayPairs}
          />
        ) : (
          <p className={styles.muted}>No model for this member.</p>
        )}
        {/* Two fixed single-line keys (Tag sites vs. Contacts) so toggling Contacts
            never jumps between 1 and 2 lines, and only present sources are listed. */}
        {(() => {
          const hasRankerAlt = sites.some((s) => s.is_primary === false && s.site_source !== "agent_proposer");
          const hasAgentAlt = sites.some((s) => s.is_primary === false && s.site_source === "agent_proposer");
          const curatedPos = new Set<number>();
          if (curatedAligned && curatedGene) {
            for (const c of curatedGene.sites) for (const p of c.positions ?? []) curatedPos.add(p);
          }
          const visContacts = visibleContacts(member.contacts ?? [], showHidden);
          const litHighN = visContacts.filter((c) => c.source === "literature_agent" && c.confidence_tier === "high").length;
          const litLowerN = visContacts.filter((c) => c.source === "literature_agent" && c.confidence_tier !== "high").length;
          const uniprotN = visContacts.filter((c) => c.source === "uniprot_binding").length;
          const anyContacts = curatedPos.size + litHighN + litLowerN + uniprotN > 0;
          return (
            <div className={styles.legend}>
              <div className={styles.legendRow}>
                <span className={styles.legendLabel}>Tag sites:</span>
                {flags.length > 1 ? (
                  flags.map((f) => (
                    <span key={f.siteId}>
                      <i style={{ background: f.color ?? COLORS.pick }} /> {f.label}
                    </span>
                  ))
                ) : (
                  <span><i style={{ background: COLORS.pick }} /> chosen pick</span>
                )}
                {showAlts && hasRankerAlt ? (
                  <span title="Runner-up candidate tag site scored by the tag-site ranker (not ordered)">
                    <i style={{ background: COLORS.ranker }} /> runner-up (ranker)
                  </span>
                ) : null}
                {showAlts && hasAgentAlt ? (
                  <span title="Alternative candidate tag site proposed by an LLM (not ordered)">
                    <i style={{ background: COLORS.agent }} /> runner-up (LLM)
                  </span>
                ) : null}
                {showExternalTags && renderableExternal.some((x) => x.isTedman) ? (
                  <span title="Tedman screen-validated N-terminal HA surface-expression control">
                    <i style={{ background: COLORS.tedman }} /> Tedman ({renderableExternal.filter((x) => x.isTedman).length})
                  </span>
                ) : null}
                {showExternalTags && renderableExternal.some((x) => !x.isTedman) ? (
                  <span title="Published extracellular tag insertion site from the literature">
                    <i style={{ background: COLORS.litTag }} /> literature tag ({renderableExternal.filter((x) => !x.isTedman).length})
                  </span>
                ) : null}
                <span>
                  <i style={{ background: COLORS.suggestion }} /> your suggestion
                  {suggested != null ? (
                    <>{" "}<button type="button" className={styles.clearInline} onClick={clearSuggested} aria-label="Clear suggested site">clear ×</button></>
                  ) : null}
                </span>
              </div>
              {segments ? (
                <div className={styles.legendRow}>
                  <span className={styles.legendLabel}>Contacts (sticks):</span>
                  {!showContacts ? (
                    <span className={styles.muted}>hidden</span>
                  ) : !anyContacts ? (
                    <span className={styles.muted}>none annotated on this protein</span>
                  ) : (
                    <>
                      {curatedPos.size > 0 ? (
                        <span title="Curated ligand/partner contact residues from PDB/PDBe structures and databases">
                          <i style={{ background: COLORS.curated }} /> PDB / DB ({curatedPos.size})
                        </span>
                      ) : null}
                      {litHighN > 0 ? (
                        <span title="Paper-extracted ligand/partner contacts backed by direct structural or mutagenesis evidence">
                          <i style={{ background: COLORS.litHigh }} /> literature, direct ({litHighN})
                        </span>
                      ) : null}
                      {litLowerN > 0 ? (
                        <span title="Paper-extracted contact residues inferred from homology or modeling">
                          <i style={{ background: COLORS.litLower }} /> literature, inferred ({litLowerN})
                        </span>
                      ) : null}
                      {uniprotN > 0 ? (
                        <span title="UniProt-annotated ligand binding-site residues">
                          <i style={{ background: COLORS.uniprot }} /> UniProt binding ({uniprotN})
                        </span>
                      ) : null}
                    </>
                  )}
                </div>
              ) : null}
            </div>
          );
        })()}
        {(() => {
          const modelSite = model?.site_id ? sites.find((s) => s.site_id === model.site_id) : undefined;
          const formattedNote = formatModelNote(model?.note, modelSite);
          return (
            <>
              <RefoldFlagBanner model={model} site={modelSite} />
              {formattedNote || model?.proteoform_match ? (
                <p className={styles.modelNote}>
                  Model: {model?.proteoform_match}{model?.residue_offset ? `, member residue i = model residue i + ${model.residue_offset}` : ""}
                  {formattedNote ? ` · ${formattedNote}` : ""}
                </p>
              ) : null}
            </>
          );
        })()}
      </section>
      </div>
      <section>
        <h3 className={styles.h3}>
          Tag sites{" "}
          <InfoTip label="About tag sites and arm codes">
            Each construct inserts an extracellular SpyTag003 + ALFA tag cassette. Multi-arm proteins carry numbered arms
            (a1, a2, a3, …) tested or ordered at distinct extracellular loops; alternatives are runner-up sites not ordered.
          </InfoTip>
        </h3>
        <DesignContextCard
          member={member}
          topology={topology || null}
          model={model}
          geneContext={geneContext}
          curatedPositions={(() => {
            const set = new Set<number>();
            if (curatedAligned && curatedGene) {
              for (const c of curatedGene.sites) for (const p of c.positions ?? []) set.add(p);
            }
            return set;
          })()}
        />
        {sites.length ? sites.map((s) => (
            <SiteCard key={s.site_id} site={s} length={member.ordered_length_aa} focused={focusSite === s.site_id} onShow={() => showSite(s.site_id)} />
          ))
          : <p className={styles.muted}>No tag site is recorded for this member yet.</p>}
        <ExternalTagSitesTable sites={externalTagSites} aligned={externalAligned} />
      </section>
      <section>
        <h3 className={styles.h3}>Contact sites</h3>
        {(member.contacts ?? []).some((c) => c.source === "literature_agent") ? (
          <p className={styles.caveat}>
            <strong>Literature (agent-extracted)</strong> rows are residues that literature agents read out of papers and
            that passed mechanical checks (the residue letter matches, the PMID resolves, the quote names the residue).
            Passing means the paper says it, not that the residue contacts the ligand in this construct. Accuracy was
            measured only on a 20-protein pilot against structural contacts (precision 0.47, recall 0.40); the
            library-scale set is not scored against any truth set. Never use these as training labels.
          </p>
        ) : null}
        <h4 className={styles.h4}>Curated contacts (structures and databases)</h4>
        <CuratedContacts gene={curated} aligned={curatedAligned} acc={acc} />
        <h4 className={styles.h4}>Literature contacts (agent-extracted) and UniProt binding sites</h4>
        <ContactsTable contacts={member.contacts ?? []} showHidden={showHidden} />
      </section>
    </div>
  );
}

export type L1IndexState = { kind: "loading" } | L1IndexFetch;

export function L1IndexStatus({
  state,
  onRetry,
}: {
  state: L1IndexState;
  onRetry: () => void;
}) {
  if (state.kind === "loading") {
    return <p className={styles.muted}>Loading the library…</p>;
  }
  if (state.kind === "error") {
    return (
      <div className={styles.indexError} role="alert">
        <p className={styles.error}>
          Could not load the v1 library design from the API (temporary error or network issue
          {state.status != null ? `; HTTP ${state.status}` : ""}).
        </p>
        <button type="button" className={styles.primary} onClick={onRetry}>
          Retry
        </button>
      </div>
    );
  }
  if (!state.data.load) {
    return <p className={styles.muted}>No v1 library design is published on this API yet.</p>;
  }
  return null;
}

export function L1Review({ initialIndexState }: { initialIndexState?: L1IndexState } = {}) {
  const [indexState, setIndexState] = useState<L1IndexState>(initialIndexState ?? { kind: "loading" });
  const index: L1Index | null = indexState.kind === "ok" ? indexState.data : null;
  const loadSeqRef = useRef(0);
  const loadIndex = useCallback(() => {
    const seq = ++loadSeqRef.current;
    setIndexState({ kind: "loading" });
    fetchL1IndexResult(API_BASE).then((res) => {
      if (loadSeqRef.current === seq) setIndexState(res);
    });
  }, []);
  const [filters, setFilters] = useState(readUrl);
  const [detail, setDetail] = useState<L1DesignFile | null>(null);
  const [reviewer, setReviewer] = useState("");
  // Rows from the Worker's read endpoint (token-gated, so normally null on this page)
  // plus the rows this browser saved since the page opened, so a reviewer sees their own.
  const [serverReviews, setServerReviews] = useState<L1Reviews | null>(null);
  const [savedHere, setSavedHere] = useState<L1Reviews>({ reviews: [], alt_tags: [] });
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
  // Unsaved review text, per member, for as long as the page is open. Held here because
  // this component outlives the detail panel: stepping to another gene empties `detail`
  // while the next design is fetched, which unmounts the panel the text was typed into.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [topologies, setTopologies] = useState<LibraryTopologyRow[]>([]);
  const [geneContext, setGeneContext] = useState<L1GeneContext | null>(null);
  const [externalTagSites, setExternalTagSites] = useState<L1ExternalTagSite[]>([]);
  const [copiedLink, setCopiedLink] = useState(false);
  const [synonyms, setSynonyms] = useState<SynonymOverlay | null>(null);
  // What the last letter key did, shown for a moment so a key that found nothing is not
  // silent (pressing Z with no Z gene in the filter otherwise looks like a dead page).
  const [letterMsg, setLetterMsg] = useState("");
  const searchRef = useRef<HTMLInputElement | null>(null);
  const activeRowRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLOListElement | null>(null);
  const [keyHelpOpen, setKeyHelpOpen] = useState(false);

  useEffect(() => {
    setReviewer(store.get("l1-review-reviewer"));
    // Capture an optional invite code (?k=... or ?invite=...) into localStorage
    // and strip it from the URL so copied links do not leak the invite token.
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const invite = (sp.get("k") ?? sp.get("invite") ?? "").trim();
      if (invite) {
        store.set("l1-review-invite", invite);
        sp.delete("k");
        sp.delete("invite");
        const nextSearch = sp.toString();
        const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}${window.location.hash}`;
        window.history.replaceState(null, "", nextUrl);
      }
    }
    loadIndex();
    fetchGeneSynonyms().then((s) => setSynonyms(s));
  }, [loadIndex]);

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

  const members = index ? index.members : [];
  const currentLoadVersion = index?.load?.load_version ?? null;
  const memberByDesign = useMemo(() => {
    const map = new Map<string, L1IndexMember>();
    for (const m of members) map.set(m.design_id ?? m.member_id, m);
    return map;
  }, [members]);
  const verdicts = useMemo(() => latestVerdicts(reviews?.reviews ?? []), [reviews]);
  const staleDesignIds = useMemo(() => {
    const out = new Set<string>();
    for (const [did, rows] of verdicts.entries()) {
      const m = memberByDesign.get(did);
      if (!m) continue;
      if (rows.some((r) => reviewStaleReason(r, m, currentLoadVersion) != null)) out.add(did);
    }
    return out;
  }, [verdicts, memberByDesign, currentLoadVersion]);
  const reviewedByMe = useMemo(() => {
    const name = reviewer.trim().toLowerCase();
    const freshMine = new Set<string>();
    if (name) {
      for (const [did, rows] of verdicts.entries()) {
        const m = memberByDesign.get(did);
        for (const r of rows) {
          if (r.reviewer.trim().toLowerCase() !== name) continue;
          if (!m || reviewStaleReason(r, m, currentLoadVersion) == null) freshMine.add(did);
        }
      }
      for (const a of reviews?.alt_tags ?? []) {
        if (a.reviewer.trim().toLowerCase() === name) freshMine.add(a.design_id);
      }
    }
    for (const id of mineIds) {
      if (!staleDesignIds.has(id)) freshMine.add(id);
    }
    return freshMine;
  }, [mineIds, reviews, reviewer, verdicts, memberByDesign, currentLoadVersion, staleDesignIds]);
  const facetBase = {
    rung: filters.rung, membraneClass: filters.cls, status: filters.status, query: filters.q,
    sp: filters.sp, spConcern: filters.spConcern, diff: filters.diff, snorkel: filters.snorkel, reviewed: filters.rev,
    reviewedByMe, staleDesignIds, synonyms,
  };
  const visible = useMemo(() => filterIndex(members, facetBase), [members, filters, reviewedByMe, staleDesignIds, synonyms]); // eslint-disable-line react-hooks/exhaustive-deps
  const current: L1IndexMember | undefined =
    members.find((m) => m.design_id === filters.m || m.member_id === filters.m) ?? undefined;
  const pos = current ? visible.findIndex((m) => m.member_id === current.member_id) : -1;

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
      setGeneContext(null);
      setExternalTagSites([]);
      return;
    }
    let live = true;
    const ctl = new AbortController();
    fetchL1Design(current.gene_symbol, API_BASE).then((d) => live && setDetail(d));
    // Per-residue topologies and surface-biology context live on the gene record, not on
    // the design payload. Fetched once per gene in parallel with the design.
    setTopologies([]);
    setGeneContext(null);
    setExternalTagSites([]);
    fetchL1GeneData(current.gene_symbol, API_BASE, ctl.signal).then(({ topologies: rows, context }) => {
      if (!live) return;
      setTopologies(rows);
      setGeneContext(context);
    });
    fetchL1ExternalTagSites(current.gene_symbol, API_BASE, ctl.signal).then((keep) => {
      if (!live) return;
      setExternalTagSites(keep);
    });
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
  const indexLoad = index?.load?.load_version;
  useEffect(() => {
    if (detailLoad && indexLoad && detailLoad !== indexLoad) {
      fetchL1IndexResult(API_BASE).then((res) => {
        if (res.kind === "ok") setIndexState(res);
      });
    }
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

  if (indexState.kind !== "ok" || !index || !index.load) {
    return <L1IndexStatus state={indexState} onRetry={loadIndex} />;
  }

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
  const forSpConcern = without("spConcern");
  const spConcernKnown = members.some((m) => m.sp_concern != null);
  const spConcernCount = (k: string) => (k === "" ? forSpConcern.length : forSpConcern.filter((m) => m.sp_concern === k).length);
  const forDiff = without("diff");
  const diffKnown = members.some((m) => uniprotDiffers(m) !== null);
  const diffCount = (k: string) => (k === "" ? forDiff.length : forDiff.filter((m) => uniprotDiffers(m) === (k === "yes")).length);
  const forSnorkel = without("snorkel");
  const snorkelKnown = members.some((m) => memberHasSnorkel(m) !== null);
  const snorkelCount = (k: string) => (k === "" ? forSnorkel.length : forSnorkel.filter((m) => memberHasSnorkel(m) === (k === "yes")).length);
  const forRev = without("reviewed");
  const revCount = (k: string) =>
    k === ""
      ? forRev.length
      : k === "stale"
        ? forRev.filter((m) => staleDesignIds.has(m.design_id ?? m.member_id)).length
        : forRev.filter((m) => reviewedByMe.has(m.design_id ?? m.member_id) === (k === "mine")).length;
  const filterSummary = [
    filters.rung && `rung: ${filters.rung}`,
    filters.cls && `class: ${filters.cls}`,
    filters.status && `pick: ${filters.status === "none" ? "no pick yet" : STATUS_LABEL[filters.status as L1Site["status"]] ?? filters.status}`,
    filters.sp && `SP: ${SP_LABEL[filters.sp as keyof typeof SP_LABEL] ?? filters.sp}`,
    filters.spConcern && `SP check: ${SP_CONCERN_LABEL[filters.spConcern as keyof typeof SP_CONCERN_LABEL] ?? filters.spConcern}`,
    filters.diff && (filters.diff === "yes" ? "differs from UniProt" : "same as UniProt"),
    filters.snorkel && (filters.snorkel === "yes" ? "snorkel tag" : "no snorkel"),
    filters.rev && (filters.rev === "mine" ? "reviewed by me" : filters.rev === "stale" ? "out of date" : "not reviewed by me"),
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
      {/* Filters and reviewer identity share one slim hairline strip so the member list,
          review card and 3D structure all start high above the fold. */}
      <div className={styles.utilityBar}>
      <details className={styles.filters}>
        <summary>
          Filters
          <span className={styles.filterNow}>{filterSummary}</span>
        </summary>
      <div className={styles.facets}>
        <div>
          <span className={styles.facetLabel} title="Tagging strategy rung assigned from topology and signal-peptide structure (e.g. N after SP, N at residue 1, C-terminal, internal loop)">Rung</span>
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
        {(() => {
          const presentStatuses = ["built", "decided_not_built", "pending", "no_tag", "none"].filter(
            (st) =>
              filters.status === st ||
              members.some((m) => (st === "none" ? !m.pick_status.length : m.pick_status.includes(st as L1Site["status"]))),
          );
          if (presentStatuses.length <= 1 && !filters.status) return null;
          return (
            <div>
              <span className={styles.facetLabel}>Pick</span>
              {["", ...presentStatuses].map((st) => (
                <button key={st || "all"} type="button" className={filters.status === st ? styles.chipOn : styles.chip} onClick={() => update({ status: st })}>
                  {st === "" ? "all" : st === "none" ? "no pick yet" : STATUS_LABEL[st as L1Site["status"]]}{" "}
                  <span className={styles.n}>{statusCount(st)}</span>
                </button>
              ))}
            </div>
          );
        })()}
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
        {spConcernKnown ? (
          <div>
            <span className={styles.facetLabel} title="N-after-SP pre- vs post-tag SignalP 6 and DeepTMHMM v1 cleavage checks (predictor spread >3 aa, cleavage shift/softening, weak cleavage, or second-source swap)">SP check</span>
            {[["", "all"], ["concerning", "concerning"], ["clean", "clean"]].map(([k, label]) => (
              <button key={k || "all"} type="button" className={filters.spConcern === k ? styles.chipOn : styles.chip} onClick={() => update({ spConcern: k })}>
                {label} <span className={styles.n}>{spConcernCount(k)}</span>
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
        {snorkelKnown ? (
          <div>
            <span className={styles.facetLabel} title="Whether the primary pick uses a C-terminal snorkel TM-module tag">Snorkel</span>
            {[["", "all"], ["yes", "snorkel tag"], ["no", "no snorkel"]].map(([k, label]) => (
              <button key={k || "all"} type="button" className={filters.snorkel === k ? styles.chipOn : styles.chip} onClick={() => update({ snorkel: k })}>
                {label} <span className={styles.n}>{snorkelCount(k)}</span>
              </button>
            ))}
          </div>
        ) : null}
        <div>
          <span className={styles.facetLabel} title="Review status; out of date means the protein sequence or tag site changed after review">Reviewed</span>
          {[["", "all"], ["notmine", "not reviewed by me"], ["mine", "reviewed by me"], ["stale", "out of date"]].map(([k, label]) => (
            <button key={k || "all"} type="button" className={filters.rev === k ? styles.chipOn : styles.chip} onClick={() => update({ rev: k })}>
              {label} <span className={styles.n}>{revCount(k)}</span>
            </button>
          ))}
        </div>
      </div>
      </details>
        <div className={styles.identityRow}>
          <details
            className={styles.identity}
            open={identityOpen}
            onToggle={(e) => setIdentityOpen((e.currentTarget as HTMLDetailsElement).open)}
          >
            <summary title={`Design load ${index.load.load_version}`}>
              {reviewer.trim() ? `Reviewing as ${reviewer.trim()}` : "Add your name to review"}
              {reviews ? ` · ${reviewedN} of ${members.length} reviewed` : ""}
              {staleDesignIds.size > 0 ? ` · ${staleDesignIds.size} out of date` : ""}
            </summary>
            <div className={styles.settings}>
              <label>
                your name
                <span className={styles.nameInputRow}>
                  <input
                    ref={nameRef}
                    value={reviewer}
                    maxLength={80}
                    autoComplete="name"
                    onChange={(e) => { setReviewer(e.target.value); store.set("l1-review-reviewer", e.target.value); }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        setIdentityOpen(false);
                        e.currentTarget.blur();
                      }
                    }}
                    placeholder="your name"
                    title="Shown with each review; kept in this browser"
                  />
                  <button
                    type="button"
                    className={styles.nameDoneBtn}
                    onClick={() => setIdentityOpen(false)}
                  >
                    Done
                  </button>
                </span>
              </label>
              <span className={styles.muted}>
                {serverReviews
                  ? <>Design load <span className={styles.mono}>{index.load.load_version}</span>.</>
                  : <>Reviews you save here are listed under each member; other reviewers&apos; are collected for the design team. · <span className={styles.mono}>{index.load.load_version}</span></>}
              </span>
            </div>
          </details>
        </div>
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
            placeholder="gene, CD20, class…  (/)"
            aria-label="Search members by gene, protein alias, class, rung or SP type"
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
                  <span><kbd>?</kbd> keys</span>
                </span>
              </summary>
              <dl className={styles.keyTable}>
                <dt><kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd></dt>
                <dd>previous / next member in this filter (orthologs and isoforms included)</dd>
                <dt><kbd>=</kbd> <kbd>-</kbd> <kbd>.</kbd></dt>
                <dd>verdict: = site looks right, - concern (focuses comment), . suggest another site</dd>
                <dt><kbd>⌘</kbd>/<kbd>Ctrl</kbd>+<kbd>↵</kbd></dt>
                <dd>submit the chosen verdict from anywhere on the page</dd>
                <dt><kbd>A</kbd>–<kbd>Z</kbd></dt>
                <dd>jump to the next gene starting with that letter; press it again to walk them</dd>
                <dt><kbd>1</kbd>–<kbd>9</kbd> / <kbd>0</kbd></dt>
                <dd>switch structure view (tagged fold(s) first, then native) / 0 resets camera</dd>
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
              const qUpper = filters.q.trim().toUpperCase();
              const aliasHit =
                qUpper && !g.gene_symbol.toUpperCase().includes(qUpper)
                  ? matchingSynonym(synonyms?.[g.gene_symbol], qUpper)
                  : null;
              return (
                <li key={g.gene_symbol} className={styles.geneGroup}>
                  <button
                    type="button"
                    ref={onGene && current?.member_id === primary.member_id ? activeRowRef : undefined}
                    className={current?.member_id === primary.member_id ? styles.rowOn : styles.row}
                    onClick={() => update({ m: primary.design_id ?? primary.member_id })}
                  >
                    <strong>{g.gene_symbol}</strong>
                    {aliasHit ? <span className={styles.muted}>({aliasHit})</span> : null}
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
                      {(verdicts.get(primary.design_id ?? "") ?? []).map((r) => {
                        const staleWhy = reviewStaleReason(r, primary, currentLoadVersion);
                        const dotCls = staleWhy ? styles.staleDot : r.verdict === "good" ? styles.goodDot : styles.noDot;
                        const prefix = staleWhy ? `OUT OF DATE (${staleWhy}) · ` : "";
                        return (
                          <span
                            key={r.review_id}
                            className={dotCls}
                            title={`${prefix}${r.reviewer}: ${r.verdict} · ${r.site_id ? armLabel(r.site_id) ?? r.site_id : "the member"}${r.reason ? ` — ${r.reason}` : ""}`}
                          />
                        );
                      })}
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
                            {(verdicts.get(m.design_id ?? "") ?? []).map((r) => {
                              const staleWhy = reviewStaleReason(r, m, currentLoadVersion);
                              const dotCls = staleWhy ? styles.staleDot : r.verdict === "good" ? styles.goodDot : styles.noDot;
                              return <span key={r.review_id} className={dotCls} title={staleWhy ? `OUT OF DATE (${staleWhy})` : undefined} />;
                            })}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </li>
              );
            })}
            {!visible.length ? <li className={styles.listEmpty}>No member matches these filters.</li> : null}
          </ol>
        </div>

        <div className={styles.detail}>
          {current ? (
            <>
              <div className={styles.detailHead}>
                <button type="button" onClick={() => go(-1)} aria-label="Previous member" title="Previous member (←)">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M10 3.5L5.5 8L10 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <div>
                  <h2 className={styles.h2}>
                    <a
                      className={styles.geneLink}
                      href={`/${encodeURIComponent(current.gene_symbol)}`}
                      target="_blank"
                      rel="noreferrer"
                      title={`Open ${current.gene_symbol} in the main Surfaceome viewer`}
                    >
                      {current.gene_symbol}
                    </a>{" "}
                    <span className={styles.mono}>{current.member_id}</span>
                    {current.design_id && current.design_id !== current.member_id ? (
                      <> <span className={`${styles.mono} ${styles.muted}`}>{current.design_id}</span></>
                    ) : null}
                    <button
                      type="button"
                      className={styles.copyLinkBtn}
                      title="Copy direct link to this member"
                      onClick={() => {
                        try {
                          navigator.clipboard?.writeText(window.location.href);
                          setCopiedLink(true);
                          window.setTimeout(() => setCopiedLink(false), 1500);
                        } catch {
                          /* clipboard unavailable */
                        }
                      }}
                    >
                      {copiedLink ? "Copied ✓" : "Copy link"}
                    </button>
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
                <button type="button" onClick={() => go(1)} aria-label="Next member" title="Next member (→)">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M6 3.5L10.5 8L6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
              {member ? (
                <MemberDetail
                  member={member}
                  topologyRow={l1MemberTopology(topologies, member)}
                  geneContext={geneContext}
                  externalTagSites={externalTagSites}
                  loadVersion={index.load.load_version}
                  reviews={reviews}
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
            <WelcomeCard
              totalMembers={members.length}
              onStart={visible.length ? () => goTo(0) : undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
}
