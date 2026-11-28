// WebCrypto HMAC/SHA-256, constant-time comparison, and build-bypass auth helpers.

export function timingSafeEqualFallback(a, b) {
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

// The archiver (accessible_surfaceome.cloud.record_history) must see the
// current D1 state, not a cached copy, and sweeps ~5k genes from one IP.
// A request carrying the ARCHIVE_BYPASS_TOKEN secret skips both cache tiers
// and the rate limiter. Without the exact secret nothing changes.
//
// The comparison is timing-safe: a naive `===` leaks the token length and
// the position of the first mismatched byte through response-time
// variance, which over enough requests is a practical side channel for
// guessing a long-lived secret. `crypto.subtle.timingSafeEqual` is a
// Cloudflare Workers-runtime-specific (non-standard) addition to
// SubtleCrypto; Node's webcrypto (used by the offline test harness below)
// doesn't implement it, so we fall back to a manual constant-time compare.
export async function isArchiveBypass(request, env) {
  const token = env?.ARCHIVE_BYPASS_TOKEN;
  if (!token) return false;
  const given = request.headers.get("X-Archive-Bypass");
  if (!given) return false;
  const enc = new TextEncoder();
  const tokenBytes = enc.encode(token);
  const givenBytes = enc.encode(given);
  if (tokenBytes.length !== givenBytes.length) return false;
  const subtle = globalThis.crypto && globalThis.crypto.subtle;
  if (subtle && typeof subtle.timingSafeEqual === "function") {
    return await subtle.timingSafeEqual(tokenBytes, givenBytes);
  }
  return timingSafeEqualFallback(tokenBytes, givenBytes);
}


export function toHex(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Base64url (no padding) — safe to put in a URL.
export function toBase64Url(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// HMAC-SHA256(secret, message) → base64url.
export async function hmacSign(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return toBase64Url(sig);
}

// Constant-time compare for base64url-or-hex strings of equal length.
export function timingSafeEqualStr(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

// SHA-256(text) → hex.
export async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return toHex(buf);
}

// Strip HTML tags and normalize whitespace. Comments render as plaintext
// in the viewer (no dangerouslySetInnerHTML), so this is defense-in-depth.
