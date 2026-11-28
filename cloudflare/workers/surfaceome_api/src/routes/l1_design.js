// L1 library design overlay index and per-gene payload.

import { CACHE_TTL_IMMUTABLE, CACHE_TTL_LONG, CORS_HEADERS, badRequest, checkSymbol, isMissingTable, json, notFound } from "../lib/http.js";

export const L1_LOAD_OK = /^l1d-[0-9a-f]{16}$/;

// The unpinned L1 routes must never be served stale: after a new load, a stale index
// paired with a fresh per-gene response would show two different member numberings.
// So no stale-while-revalidate (which json() adds to every cacheable response).
export function l1Fresh(data) {
  const res = json(data, { ttl: 0 });
  res.headers.set("Cache-Control", "public, max-age=30");
  return res;
}

// Fail closed on transient D1/runtime errors: never mask them as `200 { load: null }`
// (which would be cached for 30 s and read as "no library design published yet").
export function l1Unavailable() {
  return new Response(
    JSON.stringify({ error: "l1_design_unavailable" }, null, 2),
    {
      status: 503,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        ...CORS_HEADERS,
      },
    },
  );
}
export const L1_LOAD_COLS =
  "load_version, content_sha256, created_at, inputs_json, n_members, n_sites, n_structures, n_contacts";

export async function l1Load(env, pinnedLoad) {
  try {
    return pinnedLoad
      ? await env.DB.prepare(`SELECT ${L1_LOAD_COLS} FROM l1_design_load_public WHERE load_version = ?`)
          .bind(pinnedLoad).first()
      : await env.DB.prepare(
          `SELECT ${L1_LOAD_COLS} FROM l1_design_load_public ORDER BY created_at DESC, load_version DESC LIMIT 1`
        ).first();
  } catch (e) {
    if (/no such table/i.test(String(e?.message ?? e ?? ""))) return null;
    throw e;
  }
}

export function l1LoadJson(load, withInputs) {
  const num = (v) => (v == null ? null : Number(v));
  let inputs = null;
  if (withInputs) {
    try {
      inputs = JSON.parse(load.inputs_json || "null");
    } catch {
      inputs = null;
    }
  }
  return {
    load_version: load.load_version,
    content_sha256: load.content_sha256,
    created_at: load.created_at,
    n_members: num(load.n_members),
    n_sites: num(load.n_sites),
    n_structures: num(load.n_structures),
    n_contacts: num(load.n_contacts),
    ...(withInputs ? { inputs } : {}),
  };
}

// The whole library, one compact row per member, for the L1 review page's browser:
// rung, membrane class and the status of the member's current pick(s).
// Per-member SP status and UniProt comparison (l1_member_annotation_public). The
// table is newer than the rest of the overlay: if it is missing (migration not applied
// yet) or the query fails, the routes serve these fields as null instead of failing,
// so this read can never take the L1 page down. Returns Map(member_id -> row).
export async function l1Annotations(env, lv, symbol = null) {
  const suffix = symbol ? " AND gene_symbol = ? COLLATE NOCASE" : "";
  try {
    const sql = `SELECT member_id, sp_status, native_sp_last_residue, sp_evidence, sp_concern, sp_metrics_json,
                        uniprot_canonical_acc, uniprot_canonical_length, matches_uniprot_canonical, uniprot_diff_json
                   FROM l1_member_annotation_public
                  WHERE load_version = ?${suffix}`;
    const stmt = env.DB.prepare(sql);
    const res = await (symbol ? stmt.bind(lv, symbol) : stmt.bind(lv)).all();
    return new Map((res?.results ?? []).map((a) => [a.member_id, a]));
  } catch {
    try {
      const sql = `SELECT member_id, sp_status, native_sp_last_residue, sp_evidence, uniprot_canonical_acc,
                          uniprot_canonical_length, matches_uniprot_canonical, uniprot_diff_json
                     FROM l1_member_annotation_public
                    WHERE load_version = ?${suffix}`;
      const stmt = env.DB.prepare(sql);
      const res = await (symbol ? stmt.bind(lv, symbol) : stmt.bind(lv)).all();
      return new Map((res?.results ?? []).map((a) => [a.member_id, a]));
    } catch {
      return new Map();
    }
  }
}

export const l1Bool = (v) => (v == null ? null : Number(v) === 1);

export async function handleL1DesignIndex(env) {
  let load;
  let members;
  let picks;
  let leaders;
  let annotations;
  try {
    load = await l1Load(env, null);
    if (!load) return l1Fresh({ load: null, members: [] });
    const lv = load.load_version;
    [members, picks, leaders, annotations] = await Promise.all([
      env.DB.prepare(
        `SELECT member_id, design_id, gene_symbol, species, candidate_set, rung, membrane_class,
                n_tm, ordered_length_aa, sequence_sha256
           FROM l1_member_public WHERE load_version = ? ORDER BY member_id`
      ).bind(lv).all().then((r) => r?.results ?? []),
      env.DB.prepare(
        `SELECT member_id, status, COUNT(*) AS n FROM l1_tag_site_design_public
          WHERE load_version = ? AND is_primary = 1 GROUP BY member_id, status`
      ).bind(lv).all().then((r) => r?.results ?? []),
      // The leader, snorkel presence, and primary site signature of the member's current pick(s),
      // so the review page can filter by SP type / snorkel and detect stale reviews without one call per gene.
      env.DB.prepare(
        `SELECT member_id, leader, decision, cassette, site_id, insert_after_residue
           FROM l1_tag_site_design_public
          WHERE load_version = ? AND is_primary = 1`
      ).bind(lv).all().then((r) => r?.results ?? []),
      l1Annotations(env, lv),
    ]);
  } catch (e) {
    console.error("l1_design_index_failed", e?.message ?? e);
    return l1Unavailable();
  }
  const leaderBy = new Map();
  const snorkelBy = new Map();
  const sigPartsBy = new Map();
  for (const r of leaders) {
    if (r.leader) leaderBy.set(r.member_id, r.leader);
    const isSnorkel =
      (r.decision ?? "").toLowerCase() === "snorkel" ||
      (r.cassette ?? "").toLowerCase().includes("snorkel") ||
      (r.site_id ?? "").toLowerCase().includes("snorkel");
    if (isSnorkel) snorkelBy.set(r.member_id, true);
    const sigs = sigPartsBy.get(r.member_id) ?? [];
    const ins = r.insert_after_residue == null ? "" : String(r.insert_after_residue);
    sigs.push(`${r.site_id ?? ""}:${ins}:${r.leader ?? ""}:${r.cassette ?? ""}`);
    sigPartsBy.set(r.member_id, sigs);
  }
  const statusBy = new Map();
  for (const p of picks) {
    const list = statusBy.get(p.member_id) ?? [];
    list.push(p.status);
    statusBy.set(p.member_id, list);
  }
  return l1Fresh(
    {
      load: l1LoadJson(load, false),
      members: members.map((m) => ({
        member_id: m.member_id,
        design_id: m.design_id ?? null,
        gene_symbol: m.gene_symbol,
        species: m.species ?? null,
        candidate_set: m.candidate_set ?? null,
        rung: m.rung,
        membrane_class: m.membrane_class,
        n_tm: m.n_tm == null ? null : Number(m.n_tm),
        ordered_length_aa: m.ordered_length_aa == null ? null : Number(m.ordered_length_aa),
        sequence_sha256: m.sequence_sha256 ?? null,
        pick_status: (statusBy.get(m.member_id) ?? []).sort(),
        primary_site_signature: (sigPartsBy.get(m.member_id) ?? []).sort().join("|"),
        pick_leader: leaderBy.get(m.member_id) ?? null,
        has_snorkel: snorkelBy.get(m.member_id) ?? false,
        sp_status: annotations.get(m.member_id)?.sp_status ?? null,
        sp_concern: annotations.get(m.member_id)?.sp_concern ?? null,
        matches_uniprot_canonical: l1Bool(annotations.get(m.member_id)?.matches_uniprot_canonical),
      })),
    },
  );
}

export async function handleL1Design(env, symbol, pinnedLoad = null) {
  const sym = checkSymbol(symbol);
  if (!sym) return notFound("gene_not_found");
  if (pinnedLoad != null && !L1_LOAD_OK.test(pinnedLoad)) return badRequest("bad_load_version");
  let load;
  let memberRows;
  let siteRows;
  let structRows;
  let contactRows;
  let annotations;
  try {
    load = await l1Load(env, pinnedLoad);
    if (!load) {
      if (pinnedLoad) return notFound("load_not_found");
      return l1Fresh({ gene_symbol: sym, load: null, members: [] });
    }
    const lv = load.load_version;
    const q = (sql) => env.DB.prepare(sql).bind(lv, sym).all().then((r) => r?.results ?? []);
    [memberRows, siteRows, structRows, contactRows, annotations] = await Promise.all([
      q(`SELECT member_id, design_id, gene_symbol, species, candidate_set, rung, membrane_class,
                n_tm, ordered_length_aa, sequence_sha256, topology_version, uniprot_acc, proteoform_json
           FROM l1_member_public
          WHERE load_version = ? AND gene_symbol = ? COLLATE NOCASE
          ORDER BY member_id`),
      q(`SELECT site_id, member_id, design_id, rung, site_source, is_primary, insert_after_residue,
                residue_before, residue_after, leader, cassette, cassette_aa, rank, status, decision,
                status_detail, confidence, rejected_alternative, rationale_json, tagged_protein_sha256,
                source_pr, source_pr_state, source_commit, source_path, decided_by, implemented_by, reason
           FROM l1_tag_site_design_public
          WHERE load_version = ? AND gene_symbol = ? COLLATE NOCASE
          ORDER BY member_id, is_primary DESC, site_source, rank, insert_after_residue, site_id`),
      q(`SELECT structure_id, member_id, kind, site_id, source, release, s3_uri, r2_key,
                model_url, proteoform_match, residue_offset, ordered_length_aa,
                model_length_aa, is_chosen, mean_plddt, cassette_first_model_residue,
                cassette_last_model_residue, refold_verdict, note, decided_by, implemented_by, reason
           FROM l1_structure_design_public
          WHERE load_version = ? AND gene_symbol = ? COLLATE NOCASE
          ORDER BY member_id, kind, is_chosen DESC, structure_id`),
      q(`SELECT member_id, residue, aa, canonical_residue, source, evidence_types, contact_classes,
                confidence_tier, ion_site, additive_only, in_extracellular, topology_state, ligands, pmids
           FROM l1_contact_site_public
          WHERE load_version = ? AND gene_symbol = ? COLLATE NOCASE
          ORDER BY member_id, residue, source`),
      l1Annotations(env, lv, sym),
    ]);
  } catch (e) {
    console.error("l1_design_gene_failed", sym, e?.message ?? e);
    return l1Unavailable();
  }
  const num = (v) => (v == null ? null : Number(v));
  const parse = (s) => {
    if (!s) return null;
    try {
      return JSON.parse(s);
    } catch {
      return null;
    }
  };
  const members = memberRows.map((m) => ({
    member_id: m.member_id,
    design_id: m.design_id ?? null,
    gene_symbol: m.gene_symbol,
    species: m.species ?? null,
    candidate_set: m.candidate_set ?? null,
    rung: m.rung,
    membrane_class: m.membrane_class,
    n_tm: num(m.n_tm),
    ordered_length_aa: num(m.ordered_length_aa),
    sequence_sha256: m.sequence_sha256 ?? null,
    topology_version: m.topology_version ?? null,
    uniprot_acc: m.uniprot_acc ?? null,
    // The proteoform audit's decision for this member (keep / swap / repair / redraw).
    proteoform: parse(m.proteoform_json),
    // SP status and UniProt comparison from the member annotations; null when this
    // load (or this deployment's database) has none.
    ...(() => {
      const a = annotations.get(m.member_id);
      return {
        sp_status: a?.sp_status ?? null,
        native_sp_last_residue: num(a?.native_sp_last_residue),
        sp_evidence: a?.sp_evidence ?? null,
        sp_concern: a?.sp_concern ?? null,
        sp_metrics: a ? parse(a.sp_metrics_json) : null,
        uniprot_canonical_acc: a?.uniprot_canonical_acc ?? null,
        uniprot_canonical_length: num(a?.uniprot_canonical_length),
        matches_uniprot_canonical: l1Bool(a?.matches_uniprot_canonical),
        uniprot_diff: a ? parse(a.uniprot_diff_json) : null,
      };
    })(),
    sites: siteRows
      .filter((s) => s.member_id === m.member_id)
      .map((s) => ({
        site_id: s.site_id,
        rung: s.rung,
        site_source: s.site_source,
        is_primary: Boolean(Number(s.is_primary)),
        // The member's OWN native numbering; 0 = before residue 1; null = no site.
        insert_after_residue: num(s.insert_after_residue),
        residue_before: s.residue_before ?? null,
        residue_after: s.residue_after ?? null,
        leader: s.leader ?? null,
        cassette: s.cassette ?? null,
        cassette_aa: num(s.cassette_aa),
        rank: num(s.rank),
        status: s.status,
        decision: s.decision ?? null,
        status_detail: s.status_detail ?? null,
        confidence: s.confidence ?? null,
        rejected_alternative: s.rejected_alternative ?? null,
        rationale: parse(s.rationale_json),
        tagged_protein_sha256: s.tagged_protein_sha256 ?? null,
        source: {
          pr: num(s.source_pr),
          pr_state: s.source_pr_state ?? null,
          commit: s.source_commit,
          path: s.source_path,
        },
        decided_by: s.decided_by,
        implemented_by: s.implemented_by,
        reason: s.reason ?? null,
      })),
    structures: structRows
      .filter((st) => st.member_id === m.member_id)
      .map((st) => {
        const offset = Number(st.residue_offset || 0);
        const orderedLen = num(st.ordered_length_aa);
        return {
          structure_id: st.structure_id,
          kind: st.kind,
          site_id: st.site_id ?? null,
          source: st.source,
          release: st.release ?? null,
          s3_uri: st.s3_uri ?? null,
          r2_key: st.r2_key ?? null,
          model_url: st.model_url ?? null,
          proteoform_match: st.proteoform_match ?? null,
          residue_offset: offset,
          ordered_length_aa: orderedLen,
          model_length_aa: num(st.model_length_aa),
          // Native models only: the model residues the member covers (1-based, inclusive).
          display_first_model_residue:
            st.kind === "native" && orderedLen != null ? offset + 1 : null,
          display_last_model_residue:
            st.kind === "native" && orderedLen != null ? offset + orderedLen : null,
          is_chosen: Boolean(Number(st.is_chosen)),
          mean_plddt: num(st.mean_plddt),
          cassette_first_model_residue: num(st.cassette_first_model_residue),
          cassette_last_model_residue: num(st.cassette_last_model_residue),
          refold_verdict: st.refold_verdict ?? null,
          note: st.note ?? null,
          decided_by: st.decided_by,
          implemented_by: st.implemented_by,
          reason: st.reason ?? null,
        };
      }),
    contacts: contactRows
      .filter((c) => c.member_id === m.member_id)
      .map((c) => ({
        residue: num(c.residue),
        aa: c.aa ?? null,
        canonical_residue: num(c.canonical_residue),
        source: c.source,
        evidence_types: c.evidence_types ?? null,
        contact_classes: c.contact_classes ?? null,
        confidence_tier: c.confidence_tier,
        ion_site: Boolean(Number(c.ion_site)),
        additive_only: Boolean(Number(c.additive_only)),
        in_extracellular: Boolean(Number(c.in_extracellular)),
        topology_state: c.topology_state ?? null,
        ligands: c.ligands ?? null,
        pmids: c.pmids ?? null,
      })),
  }));
  const body = { gene_symbol: sym, load: l1LoadJson(load, true), members };
  // A pinned load is immutable; the newest load must not be served stale.
  return pinnedLoad ? json(body, { ttl: CACHE_TTL_IMMUTABLE, immutable: true }) : l1Fresh(body);
}
