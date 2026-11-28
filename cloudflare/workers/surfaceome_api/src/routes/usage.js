// Privacy-preserving daily-salted usage beacon endpoint (/v1/events).

import { CORS_HEADERS, badRequest, json } from "../lib/http.js";

import { sha256Hex, toHex } from "../lib/crypto.js";

// ---------------------------------------------------------------------------

const USAGE_EVENT_MAX_BODY = 2048;
const USAGE_EVENT_KINDS = new Set(["link", "external", "button", "pageview"]);
const USAGE_SALT_TTL_S = 48 * 3600;
// Re-read the salt from KV this often: if two isolates race to create a new
// day's salt, they converge on KV's winner within a few minutes.
const USAGE_SALT_MEMO_MS = 5 * 60 * 1000;
const usageSaltMemo = { day: "", salt: "", at: 0 };
const USAGE_SECTIONS = new Set([
  "benchmark", "compare", "api", "prompts", "reproducibility", "privacy",
  "l1-review", "v1-review", "surface-proteomics",
]);
const USAGE_ORIGIN_RE = /^(https:\/\/([a-z0-9-]+\.)*deliverome\.org|http:\/\/localhost(:\d+)?)$/;

/** `/EGFR/` → { page: "gene", gene: "EGFR" }; `/benchmark/` → { page: "benchmark" }. */
export function classifyUsagePage(pathname) {
  const segments = String(pathname).split("/").filter(Boolean);
  if (segments.length === 0) return { page: "home", gene: "" };
  const first = segments[0].toLowerCase();
  if (segments.length === 1 && USAGE_SECTIONS.has(first)) return { page: first, gene: "" };
  if (segments.length === 1 && /^[A-Za-z0-9][A-Za-z0-9.-]{0,24}$/.test(segments[0])) {
    return { page: "gene", gene: segments[0].toUpperCase() };
  }
  return { page: "other", gene: "" };
}

/** Collapse a UI label to one short line, and drop anything e-mail shaped. */
export function cleanUsageLabel(label) {
  const s = String(label).replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
  if (!s || s.includes("@")) return "";
  return s.slice(0, 80);
}

/** Today's (UTC) visitor-hash salt: created on first use, kept in KV for 48 h. */
async function usageDailySalt(env, now = Date.now()) {
  const kv = env.RECORD_CACHE;
  if (!kv) return "";
  const day = new Date(now).toISOString().slice(0, 10);
  if (usageSaltMemo.day === day && now - usageSaltMemo.at < USAGE_SALT_MEMO_MS) return usageSaltMemo.salt;
  const key = `usage:salt:${day}`;
  let salt = await kv.get(key);
  if (!salt) {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    salt = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    await kv.put(key, salt, { expirationTtl: USAGE_SALT_TTL_S });
  }
  Object.assign(usageSaltMemo, { day, salt, at: now });
  return salt;
}

/** Truncated SHA-256 of salt, IP and user agent; "" when there is no salt. */
export async function usageVisitorHash(salt, ip, userAgent) {
  if (!salt) return "";
  const data = new TextEncoder().encode(`${salt}|${ip}|${userAgent}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", data));
  return [...digest.slice(0, 8)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function handleUsageEvent(request, env) {
  const done = () => new Response(null, { status: 204, headers: { ...CORS_HEADERS, "Cache-Control": "no-store" } });
  if (!env.USAGE_EVENTS) return done();
  if (!USAGE_ORIGIN_RE.test(request.headers.get("Origin") || "")) return done();
  let ev;
  try {
    const body = await request.text();
    if (body.length > USAGE_EVENT_MAX_BODY) return done();
    ev = JSON.parse(body);
  } catch {
    return done();
  }
  if (!ev || typeof ev !== "object" || typeof ev.path !== "string" || !ev.path.startsWith("/")) return done();
  if (!USAGE_EVENT_KINDS.has(ev.kind)) return done();
  const { page, gene } = classifyUsagePage(ev.path.slice(0, 120));
  if (ev.kind === "pageview") {
    const visitor = await usageVisitorHash(
      await usageDailySalt(env),
      request.headers.get("CF-Connecting-IP") || "",
      request.headers.get("User-Agent") || "",
    );
    if (!visitor) return done();
    env.USAGE_EVENTS.writeDataPoint({
      indexes: [page],
      blobs: [page, gene, "pageview", visitor],
      doubles: [1],
    });
    return done();
  }
  const label = cleanUsageLabel(ev.label ?? "");
  if (!label) return done();
  env.USAGE_EVENTS.writeDataPoint({
    indexes: [page],
    blobs: [page, gene, ev.kind, label],
    doubles: [1],
  });
  return done();
}
