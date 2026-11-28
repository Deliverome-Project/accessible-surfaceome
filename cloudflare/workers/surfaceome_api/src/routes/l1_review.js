// Private L1 review verdicts and alternative-tag suggestions (invite-token authenticated).

import { CORS_HEADERS, SYMBOL_OK, badRequest, checkSymbol, isMissingTable, json, tsv, tsvCell } from "../lib/http.js";

import { sha256Hex, timingSafeEqualStr } from "../lib/crypto.js";

import { checkRateLimit } from "../lib/cache.js";

import { L1_LOAD_OK } from "./l1_design.js";

// --- L1 review page: verdicts + alternative-tag suggestions (private) ---
//
// Stored append-only in the PRIVATE agents database (FEEDBACK_DB binding; DDL in
// cloudflare/migrations/l1_review_v1.sql + l1_review_v2.sql), never in the public
// mirror. Never edge-cached.
//
// Writes (POST /v1/l1-review) need a non-empty reviewer name (<=80 chars) and one of:
//   * header `X-L1-Review-Token` equal to L1_REVIEW_TOKEN -> auth_method "token"
//     (skips rate limits; also grants read/export access);
//   * header `X-L1-Invite-Token` matching an entry in optional L1_INVITE_TOKENS
//     (comma-separated `token` or `label:token` entries; write-only, never grants reads)
//     -> auth_method "invite" or "invite:<label>" (skips rate limits); or
//   * open public path -> auth_method "rate_limited", protected by Origin check
//     (when Origin is present), silent honeypot (`website`), atomic Worker burst
//     limiter (when bound), per-IP hourly KV cap (100/hr), and a global daily cap
//     (1000/day) so bot swarms cannot fill FEEDBACK_DB.
// Reads (GET /v1/l1-review, /export.tsv) still require L1_REVIEW_TOKEN; with it unset
// they answer 503 rather than run open.
export const L1_REVIEW_HEADER = "X-L1-Review-Token";
export const L1_INVITE_HEADER = "X-L1-Invite-Token";
export const L1_REVIEW_RATE_MAX = 100;
export const L1_REVIEW_GLOBAL_DAILY_MAX = 1000;
export const L1_REVIEW_ROW_LIMIT = 10000;
export const L1_ORIGIN_RE = /^(https:\/\/([a-z0-9-]+\.)*deliverome\.org|https:\/\/([a-z0-9-]+\.)*pages\.dev|http:\/\/localhost(:\d+)?)$/;
export const L1_PLACEMENTS = new Set(["rung_default", "n_term", "c_term", "internal", "after_sp", "igk_tag"]);
export const L1_ID_OK = /^l1-[mp]\d{4,5}$/;

export async function l1TokenMatches(request, env) {
  if (!env.L1_REVIEW_TOKEN) return false;
  const got = request.headers.get(L1_REVIEW_HEADER) ?? "";
  if (!got) return false;
  const [a, b] = await Promise.all([sha256Hex(got), sha256Hex(env.L1_REVIEW_TOKEN)]);
  return timingSafeEqualStr(a, b);
}

// Write-only invite keys from optional env.L1_INVITE_TOKENS
// (`Aashish Manglik:tok1,Rob Oslund:tok2` or unlabeled `tok3`).
// Returns `{ authMethod, displayName }`, or null if unmatched.
export async function l1InviteInfo(request, env) {
  const raw = env.L1_INVITE_TOKENS;
  if (!raw) return null;
  const got = (request.headers.get(L1_INVITE_HEADER) ?? "").trim();
  if (!got) return null;
  const gotHash = await sha256Hex(got);
  for (const part of String(raw).split(",")) {
    const entry = part.trim();
    if (!entry) continue;
    const colon = entry.indexOf(":");
    const label = colon > 0 ? entry.slice(0, colon).trim() : "";
    const secret = colon > 0 ? entry.slice(colon + 1).trim() : entry;
    if (!secret) continue;
    const expectedHash = await sha256Hex(secret);
    if (timingSafeEqualStr(gotHash, expectedHash)) {
      const displayName = label ? label.slice(0, 80) : null;
      const cleanLabel = label.toLowerCase().replace(/[^a-z0-9_-]+/g, "_").replace(/^_|_$/g, "").slice(0, 24);
      return {
        authMethod: cleanLabel ? `invite:${cleanLabel}` : "invite",
        displayName,
      };
    }
  }
  return null;
}

// Resolves the pre-filled reviewer identity for a magic invite link without
// exposing any reviews or other invite tokens.
export async function handleL1ReviewWhoami(request, env) {
  const info = await l1InviteInfo(request, env);
  if (!info) return json({ valid: false, error: "unauthorized" }, { status: 401, ttl: 0 });
  return json({ valid: true, reviewer: info.displayName, auth_method: info.authMethod }, { ttl: 0 });
}

// Read gate (list + export): token only, unchanged.
export async function l1ReviewAuth(request, env) {
  if (!env.L1_REVIEW_TOKEN || !env.FEEDBACK_DB) {
    return json({ error: "review_disabled" }, { status: 503, ttl: 0 });
  }
  if (!(await l1TokenMatches(request, env))) {
    return json({ error: "unauthorized" }, { status: 401, ttl: 0 });
  }
  return null;
}

// Write gate. Returns { authMethod } or { denied: Response }. Called after the body
// validates, so a form error never consumes the per-IP rate limit.
export async function l1ReviewWriteAuth(request, env, inviteInfo = undefined) {
  if (await l1TokenMatches(request, env)) return { authMethod: "token" };
  const resolvedInvite = inviteInfo === undefined ? await l1InviteInfo(request, env) : inviteInfo;
  if (resolvedInvite) return { authMethod: resolvedInvite.authMethod };
  // Block cross-site browser CSRF from foreign origins while allowing direct
  // non-browser clients (no Origin header) to continue through rate limits.
  const origin = request.headers.get("Origin");
  if (origin && !L1_ORIGIN_RE.test(origin)) {
    return { denied: json({ error: "forbidden_origin" }, { status: 403, ttl: 0 }) };
  }
  if (!env.FEEDBACK_RATELIMIT) {
    return { denied: json({ error: "review_disabled" }, { status: 503, ttl: 0 }) };
  }
  const remoteIp = request.headers.get("CF-Connecting-IP") ?? null;
  // Atomic in-colo burst limiter (when bound) closes KV eventual-consistency races.
  const burstLimiter = env.RATE_LIMITER_L1 ?? env.RATE_LIMITER_HEAVY;
  if (burstLimiter) {
    const { success } = await burstLimiter.limit({ key: `l1:${remoteIp ?? "anon"}` });
    if (!success) return { denied: json({ error: "rate_limited" }, { status: 429, ttl: 0 }) };
  }
  const day = new Date().toISOString().slice(0, 10);
  const globalMax = Number(env.L1_REVIEW_GLOBAL_DAILY_MAX) || L1_REVIEW_GLOBAL_DAILY_MAX;
  const globalKey = `l1rl_global:${day}`;
  const globalCur = parseInt((await env.FEEDBACK_RATELIMIT.get(globalKey)) ?? "0", 10) || 0;
  if (globalCur >= globalMax) {
    return { denied: json({ error: "daily_limit_reached" }, { status: 429, ttl: 0 }) };
  }
  const ipHash = await sha256Hex(`${remoteIp ?? "0"}|${day}`);
  const under = await checkRateLimit(env.FEEDBACK_RATELIMIT, ipHash, {
    prefix: "l1rl", max: L1_REVIEW_RATE_MAX,
  });
  if (!under) return { denied: json({ error: "rate_limited" }, { status: 429, ttl: 0 }) };
  await env.FEEDBACK_RATELIMIT.put(globalKey, String(globalCur + 1), { expirationTtl: 86400 });
  return { authMethod: "rate_limited" };
}

// INSERT resilient to pending additive migrations (site_signature and/or auth_method
// as trailing columns): if a column is missing on FEEDBACK_DB, drop it and retry so
// reviews are never lost across deploy order.
export async function l1Insert(env, sql, vals) {
  let curSql = sql;
  let curVals = [...vals];
  while (true) {
    try {
      return await env.FEEDBACK_DB.prepare(curSql).bind(...curVals).run();
    } catch (err) {
      const msg = String(err?.message ?? err);
      const m = curSql.match(/\(([^)]+)\)\s*VALUES/i);
      if (!m) throw err;
      const cols = m[1].split(",").map((s) => s.trim());
      const drop = ["site_signature", "auth_method"].find((col) => msg.includes(col) && cols.includes(col));
      if (!drop) throw err;
      const idx = cols.indexOf(drop);
      cols.splice(idx, 1);
      curVals.splice(idx, 1);
      const tbl = curSql.match(/INSERT INTO\s+(\w+)/i)?.[1];
      curSql = `INSERT INTO ${tbl} (${cols.join(", ")}) VALUES (${cols.map(() => "?").join(", ")})`;
    }
  }
}

export function l1Str(v, max) {
  if (v == null) return null;
  const s = String(v).trim();
  return s ? s.slice(0, max) : null;
}

export async function handleL1ReviewSubmit(request, env) {
  if (!env.FEEDBACK_DB) return json({ error: "review_disabled" }, { status: 503, ttl: 0 });
  let body;
  try {
    body = await request.json();
  } catch {
    return badRequest("invalid_json");
  }
  // Stored as typed (surrounding whitespace trimmed); too long is an error, not a cut.
  // If a labeled magic-link invite token is present and the caller left reviewer blank,
  // auto-fill the invite's display name so invited experts never need to type it.
  const inviteInfo = await l1InviteInfo(request, env);
  const reviewerRaw = String(body.reviewer ?? "").trim();
  const reviewer = reviewerRaw
    ? (reviewerRaw.length <= 80 ? reviewerRaw : null)
    : (inviteInfo?.displayName ?? null);
  const memberId = l1Str(body.member_id, 12);
  const designId = l1Str(body.design_id, 12);
  const gene = l1Str(body.gene_symbol, 30);
  const loadVersion = l1Str(body.load_version, 24);
  if (!reviewer) return badRequest("invalid_reviewer");
  if (!memberId || !L1_ID_OK.test(memberId) || !designId || !L1_ID_OK.test(designId)) {
    return badRequest("invalid_member");
  }
  if (!gene || !SYMBOL_OK.test(gene)) return badRequest("invalid_gene");
  if (!loadVersion || !L1_LOAD_OK.test(loadVersion)) return badRequest("invalid_load_version");
  const sha = l1Str(body.sequence_sha256, 64);
  const siteSig = l1Str(body.site_signature, 512);
  const reason = l1Str(body.reason, 4000);
  const honeypot = String(body.website ?? "").trim();
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  if (body.kind === "verdict") {
    if (body.verdict !== "good" && body.verdict !== "no") return badRequest("invalid_verdict");
    if (body.verdict === "no" && !reason) return badRequest("reason_required");
    if (honeypot) {
      return json({ ok: true, review_id: id, created_at: now, auth_method: "rate_limited" }, { status: 201, ttl: 0 });
    }
    const auth = await l1ReviewWriteAuth(request, env, inviteInfo);
    if (auth.denied) return auth.denied;
    await l1Insert(
      env,
      `INSERT INTO l1_review (review_id, created_at, reviewer, member_id, design_id, sequence_sha256,
                              gene_symbol, site_id, verdict, reason, load_version, site_signature, auth_method)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, now, reviewer, memberId, designId, sha, gene, l1Str(body.site_id, 80), body.verdict,
        reason, loadVersion, siteSig, auth.authMethod],
    );
    return json({ ok: true, review_id: id, created_at: now, auth_method: auth.authMethod }, { status: 201, ttl: 0 });
  }
  if (body.kind === "alt_tag") {
    const placement = String(body.placement ?? "");
    if (!L1_PLACEMENTS.has(placement)) return badRequest("invalid_placement");
    const residue = body.insert_after_residue == null || body.insert_after_residue === ""
      ? null : Number(body.insert_after_residue);
    if (residue != null && (!Number.isInteger(residue) || residue < 0 || residue > 40000)) {
      return badRequest("invalid_residue");
    }
    if (residue == null && (placement === "internal" || placement === "after_sp")) {
      return badRequest("residue_required");
    }
    if (honeypot) {
      return json({ ok: true, suggestion_id: id, created_at: now, auth_method: "rate_limited" }, { status: 201, ttl: 0 });
    }
    const auth = await l1ReviewWriteAuth(request, env, inviteInfo);
    if (auth.denied) return auth.denied;
    await l1Insert(
      env,
      `INSERT INTO l1_alt_tag (suggestion_id, created_at, reviewer, member_id, design_id, sequence_sha256,
                               gene_symbol, insert_after_residue, placement, cassette_variant, reason,
                               load_version, site_signature, auth_method)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, now, reviewer, memberId, designId, sha, gene, residue, placement,
        l1Str(body.cassette_variant, 120), reason, loadVersion, siteSig, auth.authMethod],
    );
    return json({ ok: true, suggestion_id: id, created_at: now, auth_method: auth.authMethod }, { status: 201, ttl: 0 });
  }
  return badRequest("invalid_kind");
}

export async function l1ReviewRows(env) {
  const [reviews, alts] = await Promise.all([
    env.FEEDBACK_DB.prepare(
      `SELECT * FROM l1_review ORDER BY created_at, review_id LIMIT ?`,
    ).bind(L1_REVIEW_ROW_LIMIT).all(),
    env.FEEDBACK_DB.prepare(
      `SELECT * FROM l1_alt_tag ORDER BY created_at, suggestion_id LIMIT ?`,
    ).bind(L1_REVIEW_ROW_LIMIT).all(),
  ]);
  return { reviews: reviews?.results ?? [], alt_tags: alts?.results ?? [] };
}

export async function handleL1ReviewList(request, env) {
  const denied = await l1ReviewAuth(request, env);
  if (denied) return denied;
  return json(await l1ReviewRows(env), { ttl: 0 });
}

export const L1_EXPORT_COLS = [
  "kind", "id", "created_at", "reviewer", "member_id", "design_id", "sequence_sha256", "gene_symbol",
  "site_id", "verdict", "insert_after_residue", "placement", "cassette_variant", "reason", "load_version",
  "site_signature", "auth_method",
];

export async function handleL1ReviewExport(request, env) {
  const denied = await l1ReviewAuth(request, env);
  if (denied) return denied;
  const { reviews, alt_tags } = await l1ReviewRows(env);
  const rows = [
    ...reviews.map((r) => ({ ...r, kind: "verdict", id: r.review_id })),
    ...alt_tags.map((r) => ({ ...r, kind: "alt_tag", id: r.suggestion_id })),
  ].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  const cell = (v) => (v == null ? "" : String(v).replace(/[\t\r\n]+/g, " "));
  const tsv = [L1_EXPORT_COLS.join("\t"), ...rows.map((r) => L1_EXPORT_COLS.map((c) => cell(r[c])).join("\t"))]
    .join("\n") + "\n";
  return new Response(tsv, {
    headers: {
      "Content-Type": "text/tab-separated-values; charset=utf-8",
      "Content-Disposition": 'attachment; filename="l1_reviews.tsv"',
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}

// Tag-insertion sites for one gene (deterministic + literature), from
// tag_site_public. Returns a TaggedSitesFile (viewer/lib/tag-sites-types.ts) so
// the viewer's fetchTaggedSites -> parseTaggedSitesFile consumes it unchanged.
// Empty-but-200 on no rows: absence is not an error (same contract the static
// asset had).
