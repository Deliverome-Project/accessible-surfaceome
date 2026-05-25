# Per-gene feedback button — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ship a UniProt-style "Submit feedback" affordance on each
gene page, with an optional public-posting path gated by maintainer
approval via email magic links.

**Architecture:** extend the existing `surfaceome-api` Worker with
three endpoints (`POST /v1/feedback/submit`, `GET /v1/feedback/moderate`,
`GET /v1/feedback/public`); add a private D1 table for unmoderated
submissions and a public mirror table for approved-only sanitized
notes; add a `<FeedbackButton>` + `<FeedbackModal>` on the gene page,
and a `<CommunityNotesCard>` that fetches approved notes client-side.

**Tech Stack:** Cloudflare Workers (JS), D1 (SQLite), Workers KV
(rate-limit counters), Cloudflare Turnstile (anti-spam), Resend
(transactional email), Next.js 16 (viewer SSG), React client
components, CSS Modules.

**Prerequisites already in place:** root `.env` has `RESEND_API_KEY`,
`MAGIC_LINK_SECRET`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`,
`TURNSTILE_SECRET_KEY`, `MAINTAINER_EMAIL`,
`CLOUDFLARE_KV_FEEDBACK_RATELIMIT_ID`,
`CLOUDFLARE_D1_SURFACEOME_AGENTS_ID`,
`CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID`, `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`. The KV namespace `FEEDBACK_RATELIMIT` already
exists at id `3a243003db0443698f0e47b9f047df40`. Resend domain
`deliverome.org` is verified. Turnstile site `surfaceome-feedback` is
created with site key `0x4AAAAAADWMXfjX7seRgQLJ`.

**Branch:** all commits land on `claude/heuristic-leavitt-80fcd3` (open
PR #38) via fast-forward push from this local sub-branch.

**Open scope assumption:** the current `CLOUDFLARE_API_TOKEN` lacks
`Workers Scripts:Edit` scope (as discovered with the KV namespace
attempt). Tasks that require it (`wrangler secret put`, `wrangler
deploy`) are written with both an "I'll attempt" path and a "user runs
locally" fallback.

---

## File Structure

### Files to create

| Path | Responsibility |
|---|---|
| `viewer/components/FeedbackButton/FeedbackButton.tsx` | Client component — renders the "Submit feedback" link inside `crumbActions`; dispatches a CustomEvent to open the modal. |
| `viewer/components/FeedbackButton/FeedbackButton.module.css` | Empty/minimal — uses the existing `crumbAction` styling. (May be unnecessary; included for parity.) |
| `viewer/components/FeedbackButton/FeedbackModal.tsx` | Client component — the actual form, Turnstile widget, validation, POST to Worker, success / error states. |
| `viewer/components/FeedbackButton/FeedbackModal.module.css` | Modal layout: backdrop, panel, fields, submit row. |
| `viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.tsx` | Client component — fetches approved notes for the gene, renders inside a `<SectionCard>`. Renders `null` when empty. |
| `viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.module.css` | Note list + per-note byline styling. |

### Files to modify

| Path | Change |
|---|---|
| `cloudflare/d1_schema.sql` | Append `CREATE TABLE feedback` + indices. |
| `cloudflare/d1_public_schema.sql` | Append `CREATE TABLE feedback_public` + index. |
| `cloudflare/workers/surfaceome_api/src/index.js` | Add helpers (HMAC, Turnstile, Resend, sanitize, rate-limit); add `handleFeedbackSubmit`, `handleFeedbackModerate`, `handleFeedbackPublic`; loosen the 405 method gate to allow `POST /v1/feedback/submit`; register routes. |
| `cloudflare/workers/surfaceome_api/wrangler.toml.example` | Document new `FEEDBACK_DB` D1 binding + `FEEDBACK_RATELIMIT` KV binding + required secrets. |
| `cloudflare/workers/surfaceome_api/wrangler.toml` | (Gitignored locally) — same new bindings with real IDs from `.env`. |
| `viewer/next.config.mjs` | Expose `NEXT_PUBLIC_TURNSTILE_SITE_KEY` + `NEXT_PUBLIC_GIT_SHA` + `NEXT_PUBLIC_FEEDBACK_API_BASE` to client at build time. |
| `viewer/app/[symbol]/page.tsx` | Import `<FeedbackButton>` and render it inside the `crumbActions` span; import `<FeedbackModal>` and mount it once at the page level (sibling of `<EvidenceDrawer>`); add a `community` entry to the `sections` array rendering `<CommunityNotesCard>`. |
| `cloudflare/workers/surfaceome_api/README.md` | Append a "Feedback flow" section documenting the new endpoints + magic-link contract. |

---

## Task 1: Apply D1 schemas

**Files:**
- Modify: `cloudflare/d1_schema.sql` (append)
- Modify: `cloudflare/d1_public_schema.sql` (append)
- Test (verification): `D1Client.query()` against both DBs

- [ ] **Step 1: Append the private `feedback` table to `cloudflare/d1_schema.sql`**

Add at the end of the file:

```sql

-- ============================================================
-- Per-gene feedback submissions (private — PII + audit trail)
-- ============================================================
-- One row per incoming submission from the gene-page "Submit
-- feedback" modal. The Worker writes here from POST
-- /v1/feedback/submit and updates the status column from GET
-- /v1/feedback/moderate when a magic link is clicked. Approved
-- public rows are mirrored (sanitized subset) into
-- surfaceome_public.feedback_public.

CREATE TABLE IF NOT EXISTS feedback (
  id               TEXT PRIMARY KEY,         -- crypto.randomUUID()
  gene_symbol      TEXT NOT NULL,            -- e.g. "SRC"
  uniprot_acc      TEXT,                     -- e.g. "P12931"
  submitter_name   TEXT NOT NULL,
  submitter_email  TEXT NOT NULL,
  subject          TEXT NOT NULL,            -- editable; becomes email subject
  comment          TEXT NOT NULL,            -- raw; max 4000 chars
  public_requested INTEGER NOT NULL DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'pending',
                   -- pending / approved_public / approved_private / discarded
  referrer         TEXT,
  user_agent       TEXT,
  site_version     TEXT,
  ip_hash          TEXT,
  approve_token    TEXT NOT NULL,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  moderated_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_feedback_gene
  ON feedback(gene_symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_status
  ON feedback(status, created_at DESC);
```

- [ ] **Step 2: Append the public `feedback_public` table to `cloudflare/d1_public_schema.sql`**

Add at the end of the file:

```sql

-- ============================================================
-- Approved-only community notes (public mirror)
-- ============================================================
-- Sanitized subset of surfaceome_agents.feedback rows where status =
-- 'approved_public'. Inserted by the Worker's magic-link approval
-- handler. The viewer fetches from here via GET /v1/feedback/public.

CREATE TABLE IF NOT EXISTS feedback_public (
  id              TEXT PRIMARY KEY,          -- same id as private row
  gene_symbol     TEXT NOT NULL,
  submitter_name  TEXT NOT NULL,
  comment         TEXT NOT NULL,
  approved_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_public_gene
  ON feedback_public(gene_symbol, approved_at DESC);
```

- [ ] **Step 3: Apply both schemas via `D1Client.query()`**

Create a one-off script in the repo root (don't commit it):

```bash
cd /Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/exciting-knuth-b9e3fe

uv run python -c "
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
import os

load_env()

# --- private (surfaceome_agents) ---
private_stmts = [
  '''CREATE TABLE IF NOT EXISTS feedback (
       id TEXT PRIMARY KEY,
       gene_symbol TEXT NOT NULL,
       uniprot_acc TEXT,
       submitter_name TEXT NOT NULL,
       submitter_email TEXT NOT NULL,
       subject TEXT NOT NULL,
       comment TEXT NOT NULL,
       public_requested INTEGER NOT NULL DEFAULT 0,
       status TEXT NOT NULL DEFAULT 'pending',
       referrer TEXT,
       user_agent TEXT,
       site_version TEXT,
       ip_hash TEXT,
       approve_token TEXT NOT NULL,
       created_at TEXT NOT NULL DEFAULT (datetime('now')),
       moderated_at TEXT
     );''',
  'CREATE INDEX IF NOT EXISTS idx_feedback_gene ON feedback(gene_symbol, created_at DESC);',
  'CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status, created_at DESC);',
]
with D1Client() as d1:
    for s in private_stmts:
        d1.query(s, [])
print('private schema applied')

# --- public (surfaceome_public) ---
public_stmts = [
  '''CREATE TABLE IF NOT EXISTS feedback_public (
       id TEXT PRIMARY KEY,
       gene_symbol TEXT NOT NULL,
       submitter_name TEXT NOT NULL,
       comment TEXT NOT NULL,
       approved_at TEXT NOT NULL DEFAULT (datetime('now'))
     );''',
  'CREATE INDEX IF NOT EXISTS idx_feedback_public_gene ON feedback_public(gene_symbol, approved_at DESC);',
]
os.environ['CLOUDFLARE_D1_DATABASE_ID'] = os.environ['CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID']
with D1Client() as d1:
    for s in public_stmts:
        d1.query(s, [])
print('public schema applied')
"
```

Expected output:
```
private schema applied
public schema applied
```

If `D1Client()` doesn't accept the override for switching DBs, fall
back to instantiating it with an explicit `database_id` argument; the
client lives at `src/accessible_surfaceome/cloud/d1_client.py` — read
it to see the constructor signature. The repo already does this style
of in-line schema apply (per CLAUDE.md "Applying schema changes when
wrangler isn't handy").

- [ ] **Step 4: Verify both tables exist**

```bash
uv run python -c "
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
import os
load_env()
with D1Client() as d1:
    print('private:', d1.query(\"SELECT name FROM sqlite_master WHERE type='table' AND name='feedback';\", []))
os.environ['CLOUDFLARE_D1_DATABASE_ID'] = os.environ['CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID']
with D1Client() as d1:
    print('public:', d1.query(\"SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_public';\", []))
"
```

Expected: both lists contain one row each.

- [ ] **Step 5: Commit the schema files**

```bash
cd /Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/exciting-knuth-b9e3fe
git add cloudflare/d1_schema.sql cloudflare/d1_public_schema.sql
git commit -m "feat(d1): add feedback + feedback_public tables for gene-page feedback flow"
```

---

## Task 2: Update wrangler.toml (new bindings)

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/wrangler.toml.example`
- Modify: `cloudflare/workers/surfaceome_api/wrangler.toml` (gitignored)

- [ ] **Step 1: Update `wrangler.toml.example` with new bindings + secret list**

Append at the end of `cloudflare/workers/surfaceome_api/wrangler.toml.example`:

```toml

# --- Feedback flow bindings (per docs/superpowers/specs/2026-05-25-feedback-button-design.md) ---

# Write binding for unmoderated submissions (PII + audit). Same database
# as the main agent-run history.
[[d1_databases]]
binding       = "FEEDBACK_DB"
database_name = "surfaceome_agents"
database_id   = "REPLACE_WITH_AGENTS_D1_UUID"

# Rate-limit counters (5 submissions / IP-hash / hour).
[[kv_namespaces]]
binding = "FEEDBACK_RATELIMIT"
id      = "REPLACE_WITH_FEEDBACK_RATELIMIT_KV_ID"

# Secrets — set via:
#   cd cloudflare/workers/surfaceome_api
#   npx wrangler secret put RESEND_API_KEY
#   npx wrangler secret put TURNSTILE_SECRET_KEY
#   npx wrangler secret put MAGIC_LINK_SECRET
#   npx wrangler secret put MAINTAINER_EMAIL
# Values come from the root .env (RESEND_API_KEY, TURNSTILE_SECRET_KEY,
# MAGIC_LINK_SECRET, MAINTAINER_EMAIL respectively).
```

- [ ] **Step 2: Update the gitignored `wrangler.toml` with real IDs**

Read the current file:

```bash
cat cloudflare/workers/surfaceome_api/wrangler.toml
```

Then append the same `[[d1_databases]]` and `[[kv_namespaces]]` blocks,
substituting:

- `database_id` = value of `$CLOUDFLARE_D1_SURFACEOME_AGENTS_ID` from
  root `.env` (which is `62d05ed3-c8f9-4bad-ac39-da31f64d0ee2`).
- `id` (KV) = `3a243003db0443698f0e47b9f047df40` (from root `.env`
  `CLOUDFLARE_KV_FEEDBACK_RATELIMIT_ID`).

The file is gitignored — these IDs stay local.

- [ ] **Step 3: Commit the example**

```bash
git add cloudflare/workers/surfaceome_api/wrangler.toml.example
git commit -m "docs(cf): document new FEEDBACK_DB + FEEDBACK_RATELIMIT bindings in wrangler example"
```

---

## Task 3: Push wrangler secrets to Cloudflare

**Files:** none (Cloudflare encrypted store only).

- [ ] **Step 1: Try `wrangler secret put RESEND_API_KEY` with current token**

```bash
cd /Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/exciting-knuth-b9e3fe
set -a; source /Users/rebeccacarlson/Git/accessible-surfaceome/.env; set +a
cd cloudflare/workers/surfaceome_api
printf "%s" "$RESEND_API_KEY" | npx --yes wrangler secret put RESEND_API_KEY
```

Expected output (on success):
```
🌀 Creating the secret for the Worker "surfaceome-api"
✨ Success! Uploaded secret RESEND_API_KEY
```

If you see `Authentication error [code: 10000]`, the current API
token lacks `Workers Scripts:Edit` scope. **Fallback:** ask the user to
add the scope to the token (Cloudflare dashboard → My Profile → API
Tokens → edit `cfut_Izv…` → add `Account → Workers Scripts → Edit` →
save), then re-run.

- [ ] **Step 2: Push the remaining three secrets**

```bash
printf "%s" "$TURNSTILE_SECRET_KEY" | npx --yes wrangler secret put TURNSTILE_SECRET_KEY
printf "%s" "$MAGIC_LINK_SECRET"     | npx --yes wrangler secret put MAGIC_LINK_SECRET
printf "%s" "$MAINTAINER_EMAIL"      | npx --yes wrangler secret put MAINTAINER_EMAIL
```

Each should print `✨ Success! Uploaded secret <NAME>`.

- [ ] **Step 3: Verify by listing**

```bash
npx --yes wrangler secret list
```

Expected: an array of `{"name": "...", "type": "secret_text"}` containing all four names.

No commit — secrets are not in any file.

---

## Task 4: Worker — add feedback helpers

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js` — add a new helper block above the `// --- entry ---` line (line ~805).

- [ ] **Step 1: Add the feedback-helpers block**

Open `cloudflare/workers/surfaceome_api/src/index.js` and find the comment line `// --- entry ----------------------------------------------------------------` (around line 805). Insert the following block **above** that line:

```javascript

// === Feedback flow helpers ================================================
// All functions in this block support the three /v1/feedback/* endpoints
// added below. They never leak PII or unsanitized HTML across the
// public/private boundary.

// Hex-encode an ArrayBuffer or Uint8Array.
function toHex(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Base64url (no padding) — safe to put in a URL.
function toBase64Url(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// HMAC-SHA256(secret, message) → base64url.
async function hmacSign(secret, message) {
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
function timingSafeEqualStr(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

// SHA-256(text) → hex.
async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return toHex(buf);
}

// Strip HTML tags and collapse whitespace. Comments render as plaintext
// in the viewer (no dangerouslySetInnerHTML), so this is defense-in-depth.
function sanitizeComment(s) {
  return String(s ?? "")
    .replace(/<[^>]*>/g, "")
    .replace(/\r\n/g, "\n")     // normalize CRLF -> LF
    .replace(/[ \t]+\n/g, "\n") // strip trailing whitespace on lines
    .trim()
    .slice(0, 4000);
}

// Cheap email-shape check. Real validation lives at the auth layer
// (we never auto-trust the address); this is just "does it look like
// an email at all".
function looksLikeEmail(s) {
  return typeof s === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

// HTML-escape a string for safe embedding in the moderate-confirmation
// page and the Resend email body.
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Verify a Cloudflare Turnstile token against the siteverify endpoint.
// Returns true on success, false on failure (does NOT throw — caller
// decides response code).
async function verifyTurnstile(token, secret, remoteIp) {
  if (!token || !secret) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (remoteIp) body.set("remoteip", remoteIp);
  try {
    const r = await fetch(
      "https://challenges.cloudflare.com/turnstile/v0/siteverify",
      { method: "POST", body },
    );
    const j = await r.json();
    return !!j.success;
  } catch {
    return false;
  }
}

// Rate-limit per IP-hash. Returns true if under the limit, false if over.
// Window: 1 hour, max: 5 submissions. KV is eventually consistent — that
// is acceptable here (bursts of 6-10 once an hour aren't a real DoS).
async function checkRateLimit(kv, ipHash) {
  const key = `rl:${ipHash}:${Math.floor(Date.now() / 3600_000)}`; // hour bucket
  const v = await kv.get(key);
  const n = v ? parseInt(v, 10) : 0;
  if (n >= 5) return false;
  await kv.put(key, String(n + 1), { expirationTtl: 3600 });
  return true;
}

// Send the feedback notification email via Resend. Returns true on
// success, false on failure (the caller still 200's the submission —
// we don't lose the row just because email is slow).
async function sendFeedbackEmail({ apiKey, from, to, replyTo, subject, html }) {
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: [to],
        reply_to: replyTo ? [replyTo] : undefined,
        subject,
        html,
      }),
    });
    if (!r.ok) {
      console.error("Resend send failed:", r.status, await r.text());
      return false;
    }
    return true;
  } catch (err) {
    console.error("Resend send error:", err);
    return false;
  }
}

// Compose the email body sent to the maintainer.
function feedbackEmailHtml({ rec, base, approvePublicUrl, discardUrl }) {
  const additional = `
    <p><strong>Additional information</strong></p>
    <ul style="line-height: 1.5">
      <li>Referred from: <code>${escapeHtml(rec.referrer || "—")}</code></li>
      <li>User browser: <code>${escapeHtml(rec.user_agent || "—")}</code></li>
      <li>Website version: <code>${escapeHtml(rec.site_version || "—")}</code></li>
    </ul>
  `;
  const publicBtn = rec.public_requested
    ? `<a href="${approvePublicUrl}"
          style="background:#922038;color:#fff;padding:0.7em 1.2em;
                 border-radius:999px;text-decoration:none;
                 display:inline-block;margin-right:0.6em;">
         Approve as public
       </a>`
    : "";
  return `
    <div style="font-family:system-ui,sans-serif;color:#1f1718;
                max-width:640px;margin:0 auto;line-height:1.55">
      <h2 style="margin-top:0">New feedback for ${escapeHtml(rec.gene_symbol)}</h2>
      <p style="color:#6f5d5a;margin:0 0 1em">
        From <strong>${escapeHtml(rec.submitter_name)}</strong>
        &lt;${escapeHtml(rec.submitter_email)}&gt;
      </p>
      <p><strong>Subject:</strong> ${escapeHtml(rec.subject)}</p>
      <p style="white-space:pre-wrap;border-left:3px solid #e5ded3;
                padding-left:1em;color:#1f1718">
        ${escapeHtml(rec.comment)}
      </p>
      ${additional}
      <p style="margin-top:2em">
        ${publicBtn}
        <a href="${discardUrl}"
           style="color:#6f5d5a;text-decoration:underline;
                  display:inline-block;padding:0.7em 0">
          Discard
        </a>
      </p>
      <p style="color:#80706a;font-size:0.85em;margin-top:2em">
        Reply directly to this e-mail to respond to the submitter
        (their address is set as Reply-To).
      </p>
    </div>
  `;
}
```

- [ ] **Step 2: Smoke-test the helpers by running locally with `wrangler dev`**

You can't fully test these in isolation without `wrangler dev` + a test
request. Skip standalone testing here; Task 9 covers integration smoke.

- [ ] **Step 3: Commit**

```bash
git add cloudflare/workers/surfaceome_api/src/index.js
git commit -m "feat(api): add feedback-flow helpers (HMAC, Turnstile, Resend, sanitize, rate-limit)"
```

---

## Task 5: Worker — `POST /v1/feedback/submit`

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js` — add a new handler function below the helpers (above `// --- entry ---`).

- [ ] **Step 1: Add `handleFeedbackSubmit`**

Insert below the helpers block from Task 4:

```javascript

async function handleFeedbackSubmit(request, env, url) {
  // Parse + validate body.
  let body;
  try {
    body = await request.json();
  } catch {
    return badRequest("invalid_json");
  }
  const gene = String(body.gene ?? "").trim();
  if (!/^[A-Z0-9-]{1,30}$/.test(gene)) return badRequest("invalid_gene");
  const name = String(body.name ?? "").trim();
  if (name.length < 1 || name.length > 80) return badRequest("invalid_name");
  const email = String(body.email ?? "").trim();
  if (!looksLikeEmail(email)) return badRequest("invalid_email");
  const subject = String(body.subject ?? "").trim();
  if (subject.length < 1 || subject.length > 200) return badRequest("invalid_subject");
  const comment = String(body.comment ?? "").trim();
  if (comment.length < 1 || comment.length > 4000) return badRequest("invalid_comment");

  // Turnstile.
  const tToken = String(body.turnstile_token ?? "");
  const remoteIp = request.headers.get("CF-Connecting-IP") ?? null;
  const ok = await verifyTurnstile(tToken, env.TURNSTILE_SECRET_KEY, remoteIp);
  if (!ok) return badRequest("turnstile_failed");

  // Rate-limit by IP-hash (per day salt = today's UTC date).
  const day = new Date().toISOString().slice(0, 10);
  const ipHash = await sha256Hex(`${remoteIp ?? "0"}|${day}`);
  const under = await checkRateLimit(env.FEEDBACK_RATELIMIT, ipHash);
  if (!under) {
    return json({ error: "rate_limited" }, { status: 429, ttl: 0 });
  }

  // Insert.
  const id = crypto.randomUUID();
  const approveToken = await hmacSign(env.MAGIC_LINK_SECRET, id);
  const publicRequested = body.public_requested ? 1 : 0;
  await env.FEEDBACK_DB.prepare(
    `INSERT INTO feedback (
       id, gene_symbol, uniprot_acc, submitter_name, submitter_email,
       subject, comment, public_requested, referrer, user_agent,
       site_version, ip_hash, approve_token
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    id, gene,
    String(body.uniprot_acc ?? "") || null,
    name, email, subject, comment, publicRequested,
    String(body.referrer ?? "") || null,
    String(body.user_agent ?? "") || null,
    String(body.site_version ?? "") || null,
    ipHash, approveToken,
  ).run();

  // Email notify maintainer.
  const base = `${url.protocol}//${url.host}`;
  const approvePublicUrl =
    `${base}/v1/feedback/moderate?id=${encodeURIComponent(id)}` +
    `&action=public&t=${encodeURIComponent(await hmacSign(env.MAGIC_LINK_SECRET, id + ":public"))}`;
  const discardUrl =
    `${base}/v1/feedback/moderate?id=${encodeURIComponent(id)}` +
    `&action=discard&t=${encodeURIComponent(await hmacSign(env.MAGIC_LINK_SECRET, id + ":discard"))}`;

  await sendFeedbackEmail({
    apiKey: env.RESEND_API_KEY,
    from: env.MAINTAINER_EMAIL,
    to: env.MAINTAINER_EMAIL,
    replyTo: email,
    subject,
    html: feedbackEmailHtml({
      rec: {
        gene_symbol: gene, submitter_name: name, submitter_email: email,
        subject, comment, public_requested: publicRequested,
        referrer: String(body.referrer ?? ""),
        user_agent: String(body.user_agent ?? ""),
        site_version: String(body.site_version ?? ""),
      },
      base, approvePublicUrl, discardUrl,
    }),
  });

  return json({ ok: true, id }, { status: 200, ttl: 0 });
}
```

- [ ] **Step 2: Commit**

```bash
git add cloudflare/workers/surfaceome_api/src/index.js
git commit -m "feat(api): add POST /v1/feedback/submit handler"
```

---

## Task 6: Worker — `GET /v1/feedback/moderate`

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js` — add another handler below `handleFeedbackSubmit`.

- [ ] **Step 1: Add `handleFeedbackModerate`**

Insert:

```javascript

// HTML confirmation page (no JS — just shows the outcome).
function moderateHtmlPage({ title, message, accent = "#922038" }) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>${escapeHtml(title)}</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:560px;margin:6em auto;
       padding:0 1em;color:#1f1718;line-height:1.55}
  h1{font-size:1.4rem;color:${accent};margin-bottom:0.3em}
  p{color:#6f5d5a}
  .hint{font-size:0.85em;color:#80706a;margin-top:2em}
</style></head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <p>${escapeHtml(message)}</p>
  <p class="hint">You can close this tab.</p>
</body></html>`;
}

function htmlResponse(content, { status = 200 } = {}) {
  return new Response(content, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}

async function handleFeedbackModerate(env, url) {
  const id = url.searchParams.get("id");
  const action = url.searchParams.get("action");
  const t = url.searchParams.get("t");
  if (!id || !action || !t) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "This moderation link is missing required parameters.",
      }),
      { status: 400 },
    );
  }
  if (action !== "public" && action !== "discard") {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "Unknown action.",
      }),
      { status: 400 },
    );
  }
  const expected = await hmacSign(env.MAGIC_LINK_SECRET, `${id}:${action}`);
  if (!timingSafeEqualStr(expected, t)) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Invalid link",
        message: "This link is invalid or has been tampered with.",
      }),
      { status: 403 },
    );
  }

  const row = await env.FEEDBACK_DB.prepare(
    "SELECT id, gene_symbol, submitter_name, comment, status FROM feedback WHERE id = ?",
  ).bind(id).first();
  if (!row) {
    return htmlResponse(
      moderateHtmlPage({
        title: "Not found",
        message: "We couldn't find that submission.",
      }),
      { status: 404 },
    );
  }
  if (row.status !== "pending") {
    return htmlResponse(
      moderateHtmlPage({
        title: "Already handled",
        message: `This submission was already marked "${row.status}".`,
      }),
    );
  }

  if (action === "discard") {
    await env.FEEDBACK_DB.prepare(
      "UPDATE feedback SET status = 'discarded', moderated_at = datetime('now') WHERE id = ?",
    ).bind(id).run();
    return htmlResponse(
      moderateHtmlPage({
        title: "Discarded",
        message: `The submission about ${row.gene_symbol} from ${row.submitter_name} has been discarded.`,
        accent: "#6f5d5a",
      }),
    );
  }

  // action === 'public' — copy sanitized subset to public DB, then mark approved.
  const sanitized = sanitizeComment(row.comment);
  await env.DB.prepare(
    `INSERT OR IGNORE INTO feedback_public (id, gene_symbol, submitter_name, comment)
     VALUES (?, ?, ?, ?)`,
  ).bind(row.id, row.gene_symbol, row.submitter_name, sanitized).run();
  await env.FEEDBACK_DB.prepare(
    "UPDATE feedback SET status = 'approved_public', moderated_at = datetime('now') WHERE id = ?",
  ).bind(id).run();
  return htmlResponse(
    moderateHtmlPage({
      title: "Approved & published",
      message: `${row.submitter_name}'s note on ${row.gene_symbol} is now visible on the gene page.`,
    }),
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add cloudflare/workers/surfaceome_api/src/index.js
git commit -m "feat(api): add GET /v1/feedback/moderate magic-link handler"
```

---

## Task 7: Worker — `GET /v1/feedback/public`

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js` — third handler.

- [ ] **Step 1: Add `handleFeedbackPublic`**

Insert:

```javascript

async function handleFeedbackPublic(env, url) {
  const gene = url.searchParams.get("gene");
  if (!gene || !/^[A-Z0-9-]{1,30}$/.test(gene)) {
    return badRequest("invalid_gene");
  }
  const rows = await env.DB.prepare(
    `SELECT id, submitter_name, comment, approved_at
     FROM feedback_public
     WHERE gene_symbol = ?
     ORDER BY approved_at DESC
     LIMIT 50`,
  ).bind(gene).all();
  return json({ gene, notes: rows.results }, { ttl: CACHE_TTL_SHORT });
}
```

- [ ] **Step 2: Commit**

```bash
git add cloudflare/workers/surfaceome_api/src/index.js
git commit -m "feat(api): add GET /v1/feedback/public listing handler"
```

---

## Task 8: Worker — wire routes + loosen method gate

**Files:**
- Modify: `cloudflare/workers/surfaceome_api/src/index.js` — the `export default { async fetch(...) { ... } }` block.

- [ ] **Step 1: Replace the existing method-gate + router**

Find the existing block (line ~807):

```javascript
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }
    const url = new URL(request.url);
    // ... existing prefix stripping ...
    if (path === "/v1/health") return handleHealth(env);
    // ... rest of routes ...
    return notFound("route_not_found");
  },
};
```

Replace with:

```javascript
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
      });
    }
    const url = new URL(request.url);
    let path = url.pathname.replace(/\/+$/, "");
    if (path.startsWith("/surfaceome/")) {
      path = path.slice("/surfaceome".length);
    } else if (path === "/surfaceome") {
      path = "";
    }

    // POST is allowed ONLY on the feedback submit endpoint.
    if (request.method === "POST") {
      if (path === "/v1/feedback/submit") {
        return handleFeedbackSubmit(request, env, url);
      }
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, { status: 405, ttl: 0 });
    }

    if (path === "/v1/health") return handleHealth(env);
    if (path === "/v1/genes") return handleGeneList(env);
    if (path === "/v1/catalog") return handleCatalog(env);
    if (path === "/v1/benchmark") return handleBenchmarkList(env);
    if (path === "/v1/benchmark/matrix") return handleBenchmarkMatrix(env);
    if (path === "/v1/benchmark/export.tsv") return handleBenchmarkExport(env);
    if (path === "/v1/triage/export.tsv") return handleTriageExport(env, url);
    if (path === "/v1/feedback/moderate") return handleFeedbackModerate(env, url);
    if (path === "/v1/feedback/public") return handleFeedbackPublic(env, url);

    let m;
    if ((m = path.match(/^\/v1\/genes\/([^/]+)$/))) return handleGene(env, m[1]);
    if ((m = path.match(/^\/v1\/orthologs\/([^/]+)$/))) return handleOrthologs(env, m[1]);
    if ((m = path.match(/^\/v1\/benchmark\/([^/]+)$/))) return handleBenchmarkOne(env, m[1]);
    if ((m = path.match(/^\/v1\/triage\/([^/]+)$/))) return handleTriage(env, m[1]);

    return notFound("route_not_found");
  },
};
```

- [ ] **Step 2: Update `CORS_HEADERS` to allow POST**

Find the existing `CORS_HEADERS` constant near the top of the file:

```javascript
const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};
```

Replace `"Access-Control-Allow-Methods"` value with `"GET, POST, OPTIONS"`:

```javascript
const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};
```

- [ ] **Step 3: Commit**

```bash
git add cloudflare/workers/surfaceome_api/src/index.js
git commit -m "feat(api): register feedback routes + allow POST on /v1/feedback/submit"
```

---

## Task 9: Worker — deploy + integration smoke test

**Files:** none (deploy only).

- [ ] **Step 1: Deploy the Worker**

```bash
cd cloudflare/workers/surfaceome_api
set -a; source /Users/rebeccacarlson/Git/accessible-surfaceome/.env; set +a
npx --yes wrangler deploy
```

Expected output: a line like `Uploaded surfaceome-api ...`, plus a list
of bindings showing both `DB` and `FEEDBACK_DB`, plus the
`FEEDBACK_RATELIMIT` KV binding.

If deploy fails with auth, the token lacks `Workers Scripts:Edit`
scope. **Fallback:** ask the user to add the scope (Cloudflare dashboard
→ My Profile → API Tokens → edit token → add `Account → Workers
Scripts → Edit`), then re-run `npx wrangler deploy`.

- [ ] **Step 2: Smoke-test `POST /v1/feedback/submit` with a Turnstile dummy token**

Use Cloudflare's **Always passes** dummy site key + secret for local
testing. Override `TURNSTILE_SECRET_KEY` for a one-shot deploy by
running `npx wrangler secret put TURNSTILE_SECRET_KEY` and entering
`1x0000000000000000000000000000000AA`, OR test by submitting a real
form from the dev viewer (Task 16). Skip the curl smoke if the Turnstile
verify would fail in raw curl.

Quick existence check (no Turnstile needed):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.deliverome.org/surfaceome/v1/feedback/public?gene=SRC
```

Expected: `200`.

- [ ] **Step 3: Inspect logs**

```bash
npx --yes wrangler tail
```

Leave running while testing from the viewer (Task 16). Look for any
`Resend send failed` or `Resend send error` lines.

No commit — deploy only.

---

## Task 10: Viewer — expose env vars in next.config.mjs

**Files:**
- Modify: `viewer/next.config.mjs`

- [ ] **Step 1: Read the current file**

```bash
cat /Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/exciting-knuth-b9e3fe/viewer/next.config.mjs
```

- [ ] **Step 2: Add an `env` block exposing the three NEXT_PUBLIC values + a derived git SHA**

Add inside the existing config object (or extend it if `env` already
exists). Final shape:

```js
import { execSync } from "node:child_process";

const gitSha = (() => {
  if (process.env.NEXT_PUBLIC_GIT_SHA) return process.env.NEXT_PUBLIC_GIT_SHA;
  if (process.env.CF_PAGES_COMMIT_SHA) return process.env.CF_PAGES_COMMIT_SHA.slice(0, 8);
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString().trim();
  } catch {
    return "dev";
  }
})();

/** @type {import('next').NextConfig} */
const nextConfig = {
  // ... existing keys ...
  env: {
    NEXT_PUBLIC_GIT_SHA: gitSha,
    NEXT_PUBLIC_TURNSTILE_SITE_KEY:
      process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "",
    NEXT_PUBLIC_FEEDBACK_API_BASE:
      process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
      ?? "https://api.deliverome.org/surfaceome",
  },
};

export default nextConfig;
```

Adjust the syntax to match whatever the existing file looks like
(merge into the existing config object — don't replace it).

- [ ] **Step 3: Verify the dev server picks it up**

```bash
cd viewer
npm run dev
```

Then in another terminal:

```bash
curl -s http://localhost:3000/SRC/ | grep -o "NEXT_PUBLIC_TURNSTILE_SITE_KEY\|0x4AAAAAADWMXfjX7seRgQLJ" | head -5
```

(Won't show on the SSR'd page yet — there's no consumer. We'll wire the
consumer in Task 12.)

- [ ] **Step 4: Commit**

```bash
git add viewer/next.config.mjs
git commit -m "feat(viewer): expose NEXT_PUBLIC_TURNSTILE_SITE_KEY + NEXT_PUBLIC_GIT_SHA + NEXT_PUBLIC_FEEDBACK_API_BASE"
```

---

## Task 11: Viewer — FeedbackButton component

**Files:**
- Create: `viewer/components/FeedbackButton/FeedbackButton.tsx`
- Create: `viewer/components/FeedbackButton/FeedbackButton.module.css`

- [ ] **Step 1: Create the directory + button TSX**

```bash
mkdir -p viewer/components/FeedbackButton
```

`viewer/components/FeedbackButton/FeedbackButton.tsx`:

```tsx
"use client";

import styles from "./FeedbackButton.module.css";

interface FeedbackButtonProps {
  gene: string;
  uniprot: string;
}

/**
 * FeedbackButton — small "Submit feedback" link rendered inside the
 * gene-page breadcrumb `crumbActions` row, next to JSON / Markdown.
 *
 * Communicates with `<FeedbackModal>` via a `surfaceome:open-feedback`
 * CustomEvent on `window`, so the button can live in the page header
 * while the modal lives at the page level (above all card content).
 * Same pattern as `<EvidenceDrawer>` / `<EvidenceChip>`.
 */
export function FeedbackButton({ gene, uniprot }: FeedbackButtonProps) {
  return (
    <button
      type="button"
      className={styles.button}
      data-hint="Submit corrections or scientific input for this entry."
      onClick={() => {
        window.dispatchEvent(
          new CustomEvent("surfaceome:open-feedback", {
            detail: { gene, uniprot },
          }),
        );
      }}
    >
      Submit feedback
    </button>
  );
}
```

`viewer/components/FeedbackButton/FeedbackButton.module.css`:

```css
/*
 * FeedbackButton — visual parity with `<a className={styles.crumbAction}>`
 * in viewer/app/[symbol]/page.module.css. Rendered as a <button> so it's
 * keyboard-accessible without needing a real href; styled to match the
 * other affordances in the same row.
 */

.button {
  background: transparent;
  border: 0;
  padding: 0;
  margin: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: var(--line);
  text-underline-offset: 3px;
  font-size: 0.76rem;
  transition: color var(--dur-fast) var(--ease-out);
}

.button:hover,
.button:focus-visible {
  color: var(--accent);
  text-decoration-color: var(--accent);
}
```

- [ ] **Step 2: Commit**

```bash
git add viewer/components/FeedbackButton/FeedbackButton.tsx viewer/components/FeedbackButton/FeedbackButton.module.css
git commit -m "feat(viewer): add FeedbackButton — opens FeedbackModal via CustomEvent"
```

---

## Task 12: Viewer — FeedbackModal component

**Files:**
- Create: `viewer/components/FeedbackButton/FeedbackModal.tsx`
- Create: `viewer/components/FeedbackButton/FeedbackModal.module.css`

- [ ] **Step 1: Create the modal TSX**

`viewer/components/FeedbackButton/FeedbackModal.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import styles from "./FeedbackModal.module.css";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const FEEDBACK_API_BASE =
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
  ?? "https://api.deliverome.org/surfaceome";
const SITE_VERSION = process.env.NEXT_PUBLIC_GIT_SHA ?? "dev";

interface OpenDetail {
  gene: string;
  uniprot: string;
}

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id?: string) => void;
    };
  }
}

/**
 * FeedbackModal — UniProt-style "Submit updates or corrections" form.
 *
 * Mounted once at the page level (sibling of `<EvidenceDrawer>`). Listens
 * for a `surfaceome:open-feedback` CustomEvent from `<FeedbackButton>`
 * to know which gene to render the form for. POSTs to the Worker's
 * /v1/feedback/submit endpoint.
 */
export function FeedbackModal() {
  const [open, setOpen] = useState(false);
  const [gene, setGene] = useState("");
  const [uniprot, setUniprot] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [comment, setComment] = useState("");
  const [publicRequested, setPublicRequested] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const turnstileTokenRef = useRef<string | null>(null);
  const turnstileWidgetIdRef = useRef<string | null>(null);
  const turnstileContainerRef = useRef<HTMLDivElement | null>(null);

  // Open via CustomEvent.
  useEffect(() => {
    const onOpen = (e: Event) => {
      const detail = (e as CustomEvent<OpenDetail>).detail;
      setGene(detail.gene);
      setUniprot(detail.uniprot);
      setSubject(`Surfaceome ${detail.gene} (${detail.uniprot}) entry update request`);
      setSubmitted(false);
      setError(null);
      setOpen(true);
    };
    window.addEventListener("surfaceome:open-feedback", onOpen);
    return () => window.removeEventListener("surfaceome:open-feedback", onOpen);
  }, []);

  // Render Turnstile when the modal opens.
  useEffect(() => {
    if (!open) return;
    if (!TURNSTILE_SITE_KEY) return;
    const tryRender = () => {
      if (!window.turnstile || !turnstileContainerRef.current) return false;
      turnstileWidgetIdRef.current = window.turnstile.render(
        turnstileContainerRef.current,
        {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token: string) => {
            turnstileTokenRef.current = token;
          },
          "error-callback": () => { turnstileTokenRef.current = null; },
          "expired-callback": () => { turnstileTokenRef.current = null; },
        },
      );
      return true;
    };
    if (!tryRender()) {
      // Script not loaded yet — poll briefly.
      const interval = setInterval(() => {
        if (tryRender()) clearInterval(interval);
      }, 200);
      return () => clearInterval(interval);
    }
  }, [open]);

  if (!open) {
    return (
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="lazyOnload"
      />
    );
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const body = {
        gene, uniprot_acc: uniprot, name, email, subject, comment,
        public_requested: publicRequested,
        referrer: window.location.href,
        user_agent: navigator.userAgent,
        site_version: SITE_VERSION,
        turnstile_token: turnstileTokenRef.current ?? "",
      };
      const r = await fetch(`${FEEDBACK_API_BASE}/v1/feedback/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error ?? `submit_failed_${r.status}`);
      }
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "submit_failed");
      if (window.turnstile && turnstileWidgetIdRef.current) {
        window.turnstile.reset(turnstileWidgetIdRef.current);
      }
      turnstileTokenRef.current = null;
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="lazyOnload"
      />
      <div
        className={styles.backdrop}
        role="dialog"
        aria-modal="true"
        aria-labelledby="feedback-modal-title"
        onClick={() => setOpen(false)}
      >
        <div
          className={styles.panel}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className={styles.close}
            aria-label="Close"
            onClick={() => setOpen(false)}
          >
            ×
          </button>
          {submitted ? (
            <div className={styles.thanks}>
              <h2 id="feedback-modal-title" className={styles.title}>
                Thank you
              </h2>
              <p>
                We've received your submission and will reply by e-mail.
              </p>
              <button
                type="button"
                className={styles.submit}
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className={styles.form}>
              <h2 id="feedback-modal-title" className={styles.title}>
                Submit updates or corrections to Surfaceome
              </h2>
              <p className={styles.lede}>
                Our team will receive and review your message.
              </p>

              <label className={styles.field}>
                <span className={styles.label}>Name</span>
                <input
                  type="text" required maxLength={80}
                  value={name} onChange={(e) => setName(e.target.value)}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>E-mail</span>
                <input
                  type="email" required
                  value={email} onChange={(e) => setEmail(e.target.value)}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Subject</span>
                <input
                  type="text" required maxLength={200}
                  value={subject} onChange={(e) => setSubject(e.target.value)}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Message</span>
                <textarea
                  required maxLength={4000} rows={8}
                  placeholder="We'd love to hear from you. Scientific feedback, corrections, new citations, antibody clones you've validated, missing isoforms — anything that would make this entry more useful. Please include PMIDs, DOIs, or links where you can, so we can incorporate the update with provenance."
                  value={comment} onChange={(e) => setComment(e.target.value)}
                />
              </label>

              <details className={styles.additional}>
                <summary>Additional information</summary>
                <p className={styles.hint}>
                  This is sent with your message so we can help you.
                </p>
                <ul className={styles.metaList}>
                  <li>
                    <span className={styles.metaKey}>Referred from:</span>{" "}
                    <code>{typeof window !== "undefined" ? window.location.href : ""}</code>
                  </li>
                  <li>
                    <span className={styles.metaKey}>User browser:</span>{" "}
                    <code>{typeof navigator !== "undefined" ? navigator.userAgent : ""}</code>
                  </li>
                  <li>
                    <span className={styles.metaKey}>Website version:</span>{" "}
                    <code>{SITE_VERSION}</code>
                  </li>
                </ul>
              </details>

              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={publicRequested}
                  onChange={(e) => setPublicRequested(e.target.checked)}
                />
                <span>
                  Post my comment publicly on the gene page after our review.
                  Your name will be shown as attribution; e-mail will not.
                </span>
              </label>

              <p className={styles.privacy}>
                We collect your name and e-mail so we can reply to your
                feedback. We do not share your information with third
                parties. Email <a href="mailto:contact@deliverome.org">contact@deliverome.org</a>{" "}
                to request deletion at any time.
              </p>

              <div ref={turnstileContainerRef} className={styles.turnstile} />

              {error ? (
                <p className={styles.error}>
                  Submission failed: {error}. Please try again.
                </p>
              ) : null}

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.cancel}
                  onClick={() => setOpen(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.submit}
                  disabled={submitting}
                >
                  {submitting ? "Submitting…" : "Submit feedback"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Create the modal CSS**

`viewer/components/FeedbackButton/FeedbackModal.module.css`:

```css
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(31, 23, 24, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--space-4);
  overflow-y: auto;
}

.panel {
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  max-width: 560px;
  width: 100%;
  padding: var(--space-6) var(--space-6);
  box-shadow: var(--shadow-md);
  position: relative;
  max-height: 90vh;
  overflow-y: auto;
}

.close {
  position: absolute;
  top: 0.6rem;
  right: 0.8rem;
  background: transparent;
  border: 0;
  font-size: 1.5rem;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  padding: 0.2rem 0.4rem;
}
.close:hover { color: var(--ink); }

.title {
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 1.25rem;
  line-height: 1.15;
  margin: 0 0 var(--space-1);
  color: var(--ink);
}

.lede {
  margin: 0 0 var(--space-5);
  color: var(--muted);
  font-size: 0.88rem;
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.label {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
}

.field input,
.field textarea {
  font: inherit;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--ink);
  font-size: 0.9rem;
}

.field textarea {
  font-family: var(--font-sans);
  line-height: 1.5;
  resize: vertical;
  min-height: 8rem;
}

.field input:focus-visible,
.field textarea:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
  border-color: var(--accent);
}

.additional {
  font-size: 0.82rem;
  color: var(--muted);
  border-top: 1px solid var(--line-soft);
  padding-top: var(--space-3);
}
.additional summary {
  cursor: pointer;
  color: var(--ink-soft);
  font-weight: 500;
}
.hint { margin: 0.4rem 0 0.6rem; color: var(--muted); font-size: 0.8rem; }
.metaList {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.metaKey { color: var(--muted); }
.metaList code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ink-soft);
  word-break: break-all;
}

.checkbox {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  font-size: 0.85rem;
  line-height: 1.45;
  color: var(--ink);
}
.checkbox input { margin-top: 0.25rem; }

.privacy {
  font-size: 0.78rem;
  color: var(--muted);
  line-height: 1.5;
  margin: 0;
}

.turnstile {
  margin-top: var(--space-2);
  min-height: 65px;
}

.error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.cancel,
.submit {
  font: inherit;
  padding: 0.55rem 1.1rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  cursor: pointer;
  font-size: 0.85rem;
}

.cancel {
  background: transparent;
  color: var(--ink);
}
.cancel:hover { border-color: var(--muted); }

.submit {
  background: var(--accent-fill);
  color: var(--fg-on-dark);
  border-color: var(--accent-fill);
}
.submit:hover { background: var(--accent-deep); border-color: var(--accent-deep); }
.submit:disabled { opacity: 0.5; cursor: not-allowed; }

.thanks {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  text-align: center;
  padding: var(--space-4) 0;
}
.thanks .submit {
  align-self: center;
}
```

- [ ] **Step 3: Commit**

```bash
git add viewer/components/FeedbackButton/FeedbackModal.tsx viewer/components/FeedbackButton/FeedbackModal.module.css
git commit -m "feat(viewer): add FeedbackModal — UniProt-style form + Turnstile + Resend submit"
```

---

## Task 13: Viewer — wire FeedbackButton + FeedbackModal in [symbol]/page.tsx

**Files:**
- Modify: `viewer/app/[symbol]/page.tsx`

- [ ] **Step 1: Import + render**

Open `viewer/app/[symbol]/page.tsx`. Add the imports near the top
(alongside the other component imports):

```tsx
import { FeedbackButton } from "../../components/FeedbackButton/FeedbackButton";
import { FeedbackModal } from "../../components/FeedbackButton/FeedbackModal";
```

Find the `<span className={styles.crumbActions}>` block (around line 120
— it contains the JSON / Markdown links). Add `<FeedbackButton>` as a
third child:

```tsx
<span className={styles.crumbActions}>
  <a className={styles.crumbAction} ...>JSON ↗</a>
  <a className={styles.crumbAction} ...>Markdown (full) ↗</a>
  <FeedbackButton gene={rec.gene.hgnc_symbol} uniprot={rec.gene.uniprot_acc} />
</span>
```

Find the line right before `</Shell>` near the bottom. Add `<FeedbackModal />` as a sibling of `<EvidenceDrawer ... />`:

```tsx
      <EvidenceDrawer evidence={rec.evidence} />
      <FeedbackModal />
    </Shell>
```

- [ ] **Step 2: Verify it builds + the modal opens**

```bash
cd viewer
npm run dev
```

In a browser, open `http://localhost:3000/SRC/`. Click "Submit
feedback" in the breadcrumb row. The modal should open with the subject
pre-filled as `Surfaceome SRC (P12931) entry update request`.

- [ ] **Step 3: Commit**

```bash
git add viewer/app/[symbol]/page.tsx
git commit -m "feat(viewer): wire FeedbackButton + FeedbackModal into gene page"
```

---

## Task 14: Viewer — CommunityNotesCard component

**Files:**
- Create: `viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.tsx`
- Create: `viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.module.css`

- [ ] **Step 1: Create the card TSX**

```bash
mkdir -p viewer/components/surfaceome/CommunityNotesCard
```

`viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./CommunityNotesCard.module.css";

const FEEDBACK_API_BASE =
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
  ?? "https://api.deliverome.org/surfaceome";

interface Note {
  id: string;
  submitter_name: string;
  comment: string;
  approved_at: string;
}

interface CommunityNotesCardProps {
  gene: string;
  n: number;
}

/**
 * CommunityNotesCard — renders approved reader-submitted notes for a
 * gene, fetched client-side from /v1/feedback/public. Returns null when
 * empty so the section is invisible until the first note is published.
 */
export function CommunityNotesCard({ gene, n }: CommunityNotesCardProps) {
  const [notes, setNotes] = useState<Note[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(
      `${FEEDBACK_API_BASE}/v1/feedback/public?gene=${encodeURIComponent(gene)}`,
    )
      .then((r) => (r.ok ? r.json() : { notes: [] }))
      .then((j) => {
        if (!cancelled) setNotes(j.notes ?? []);
      })
      .catch(() => {
        if (!cancelled) setNotes([]);
      });
    return () => { cancelled = true; };
  }, [gene]);

  if (!notes || notes.length === 0) return null;

  return (
    <SectionCard
      n={n}
      eyebrow="Community notes"
      title="Reader-submitted notes"
      meta={`${notes.length} approved note${notes.length === 1 ? "" : "s"}`}
    >
      <ul className={styles.list}>
        {notes.map((note) => (
          <li key={note.id} className={styles.item}>
            <p className={styles.comment}>{note.comment}</p>
            <p className={styles.byline}>
              — {note.submitter_name} ·{" "}
              <time dateTime={note.approved_at}>
                {new Date(note.approved_at).toLocaleDateString(undefined, {
                  year: "numeric", month: "short", day: "numeric",
                })}
              </time>
            </p>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
```

- [ ] **Step 2: Create the CSS**

`viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.module.css`:

```css
.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.item {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding-left: var(--space-4);
  border-left: 2px solid var(--line);
}

.comment {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.55;
  color: var(--ink);
  max-width: 70ch;
  white-space: pre-wrap;
}

.byline {
  margin: 0;
  font-size: 0.78rem;
  color: var(--muted);
}
```

- [ ] **Step 3: Commit**

```bash
git add viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.tsx viewer/components/surfaceome/CommunityNotesCard/CommunityNotesCard.module.css
git commit -m "feat(viewer): add CommunityNotesCard — client-fetched approved notes"
```

---

## Task 15: Viewer — wire CommunityNotesCard into sections array

**Files:**
- Modify: `viewer/app/[symbol]/page.tsx`

- [ ] **Step 1: Import + add a section entry**

In `viewer/app/[symbol]/page.tsx`, add the import:

```tsx
import { CommunityNotesCard } from "../../components/surfaceome/CommunityNotesCard/CommunityNotesCard";
```

Find the `sections` array. Append a new entry at the **end** (so it's
the last numbered section, after Evidence ledger):

```tsx
    {
      kind: "community",
      label: "Community notes",
      render: (n) => (
        <CommunityNotesCard gene={rec.gene.hgnc_symbol} n={n} />
      ),
    },
```

- [ ] **Step 2: Verify it builds and renders nothing on a gene with no notes**

```bash
cd viewer
npm run dev
```

Open `http://localhost:3000/SRC/`. The Community notes section should
be **invisible** (no card, no eyebrow) because there are no approved
notes yet. But the AnchorNav strip will still render the link — that's
acceptable; once notes land, the section appears in place.

If you want the AnchorNav link to also hide when empty: that's a
follow-up task and out of scope here.

- [ ] **Step 3: Commit**

```bash
git add viewer/app/[symbol]/page.tsx
git commit -m "feat(viewer): add Community notes section to gene-page sections array"
```

---

## Task 16: End-to-end verification + push

**Files:** none (verification + git push only).

- [ ] **Step 1: Build the viewer to confirm no SSG / type breakage**

```bash
cd viewer
npm run build
```

Expected: `✓ Generating static pages (9/9)` with no errors. Both
`/SRC` and `/GPR75` should be in the SSG output.

- [ ] **Step 2: Open the viewer + submit a real feedback message**

```bash
npm run dev
```

In a browser:
1. Open `http://localhost:3000/SRC/`.
2. Click "Submit feedback" in the breadcrumb row.
3. Fill in name, e-mail, message. Subject is pre-filled.
4. Check the "Post my comment publicly" box.
5. Solve the Turnstile widget.
6. Submit. Expect the "Thank you" confirmation.

- [ ] **Step 3: Check the maintainer mailbox for the notification**

The e-mail to `MAINTAINER_EMAIL` should arrive within a few seconds and
contain:
- Gene + submitter info + the comment text
- Additional information block (referrer, user agent, version)
- Two buttons: "Approve as public" and "Discard"

- [ ] **Step 4: Click "Approve as public"**

The magic link opens an HTML confirmation page that reads "Approved &
published". Refresh `http://localhost:3000/SRC/`. The Community notes
section should now appear at the bottom of the page with the note you
just submitted.

- [ ] **Step 5: Test the Discard path**

Submit another test message (don't check public). The e-mail has only a
"Discard" button. Click it. Confirmation page reads "Discarded". The
note does not appear on the gene page.

- [ ] **Step 6: Push the branch to update the open PR**

```bash
cd /Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/exciting-knuth-b9e3fe
git push origin claude/heuristic-leavitt-feedback-spec:claude/heuristic-leavitt-80fcd3
```

Expected: `cceec522..<new-sha>  claude/heuristic-leavitt-feedback-spec -> claude/heuristic-leavitt-80fcd3`.

- [ ] **Step 7: Update Worker README with the new endpoints**

Append a "Feedback endpoints" section to
`cloudflare/workers/surfaceome_api/README.md` covering:
- The three new endpoints (`POST /v1/feedback/submit`,
  `GET /v1/feedback/moderate`, `GET /v1/feedback/public`).
- That the magic-link approval is HMAC-signed and idempotent.
- Pointer to the design spec for full detail.

```bash
git add cloudflare/workers/surfaceome_api/README.md
git commit -m "docs(api): document feedback endpoints in Worker README"
git push origin claude/heuristic-leavitt-feedback-spec:claude/heuristic-leavitt-80fcd3
```

---

## Self-review (post-write)

**Spec coverage**

| Spec section | Implementing task(s) |
|---|---|
| Prerequisites | Task 1 (D1 schemas), Task 2 (wrangler.toml), Task 3 (secrets) |
| Architecture diagram | Tasks 4-8 (Worker), Tasks 11-15 (viewer) |
| Data model (private) | Task 1 step 1 + step 3 |
| Data model (public) | Task 1 step 2 + step 3 |
| Worker routes | Task 5 (submit), Task 6 (moderate), Task 7 (public), Task 8 (wiring) |
| Bindings + secrets | Task 2 (config), Task 3 (push) |
| Frontend: FeedbackButton | Task 11 |
| Frontend: FeedbackModal | Task 12 |
| Frontend: CommunityNotesCard | Task 14 |
| Frontend: page wire | Tasks 13, 15 |
| Git-SHA exposure | Task 10 |
| Security: Turnstile / rate-limit / HMAC / sanitization | Task 4 (helpers), Task 5 (submit), Task 6 (moderate) |
| Privacy notice | Task 12 (inline string in modal) |
| Error handling matrix | Tasks 5, 6 (each branch is in the handler) |
| Verification | Task 16 |

**Placeholder scan:** searched for "TODO", "TBD", "fill in details",
"handle edge cases" — none present.

**Type consistency:** `feedback_public` schema (Task 1) matches the
shape SELECT'd in `handleFeedbackPublic` (Task 7) and consumed by
`<CommunityNotesCard>` (Task 14). The `feedback` schema matches the
INSERT in `handleFeedbackSubmit` (Task 5) and the SELECT/UPDATE in
`handleFeedbackModerate` (Task 6). Magic-link signing uses
`hmacSign(secret, id + ":" + action)` in both Task 5 (sign) and Task 6
(verify) — formats match.

**Scope check:** single coherent feature, fits in one plan. No
decomposition needed.
