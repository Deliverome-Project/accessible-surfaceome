# Per-gene feedback button — design

## Context

The Surfaceome viewer publishes per-gene records assembled by an LLM
deep-dive agent over five public databases. The records are
authoritative-feeling but not error-free: synonyms drift, antibody
validations come and go, new citations land daily, and the agent
occasionally crosses an isoform boundary. Today a reader who spots
something off has no path to tell us. This spec adds one — modeled on
UniProt's `entry update request` form, with one extension: an optional
"post publicly" path so substantive notes can become visible to other
readers of the same gene.

Two flows ride on the same submission:

1. **Private feedback (default)** — a reader sends us a note about the
   entry. We get it, we reply, we may fold it into the next record
   refresh. This is UniProt's flow.
2. **Public note (opt-in via checkbox)** — the reader explicitly asks
   us to publish their note alongside the gene record after our review.
   We approve via a magic link in the notification email; once
   approved, the note shows up in a "Community notes" section on the
   gene page.

## Prerequisites (one-time setup)

These are external setup steps the maintainer performs before the
implementation can land; they're not in the implementation plan
itself.

- **Resend account + verified sender.** Sign up at resend.com; add
  `deliverome.org` as a verified domain (SPF + DKIM TXT records on the
  Cloudflare DNS zone). Capture the API key for `RESEND_API_KEY`.
- **Cloudflare Turnstile site key.** Create a Turnstile site in the
  Cloudflare dashboard scoped to `surfaceome.deliverome.org`; capture
  the site key (public, embedded in the modal) and secret key (private,
  for the Worker).
- **KV namespace.** `npx wrangler kv namespace create FEEDBACK_RATELIMIT`
  — capture the namespace ID for the new `[[kv_namespaces]]` entry.
- **`MAGIC_LINK_SECRET`.** Generate a 32-byte secret:
  `openssl rand -base64 32`. Goes in via `npx wrangler secret put`.
- **`MAINTAINER_EMAIL`.** The address that receives notification e-mails;
  same `wrangler secret put` pattern.

Compliance scope: this is a low-risk contact form for a research
project; the inline privacy notice is the practical minimum, not an
audited Privacy Policy. If the project later needs a formal policy
(journal submission, institutional review, etc.), promote the inline
statement to a `/privacy` page.

## Architecture

```
[Gene page]
   │
   ├─ <FeedbackButton>  (breadcrumb actions row, next to JSON / Markdown)
   │       │
   │       ▼
   │  <FeedbackModal>   (name, email, subject, message, additional info,
   │                     public-checkbox, Turnstile)
   │       │
   │       │   POST /v1/feedback/submit
   │       ▼
   │  ┌─────────────────────────────────────────────────────────────┐
   │  │ Worker (surfaceome-api, extended)                           │
   │  │  1. verify Turnstile token (siteverify)                     │
   │  │  2. rate-limit: 5 / IP / hour (Workers KV)                  │
   │  │  3. INSERT into FEEDBACK_DB.feedback (private)              │
   │  │  4. Resend → maintainer email                               │
   │  │       subject:  "[surfaceome] {gene} ({uniprot}) update"    │
   │  │       body:     submitter, comment, additional-info block,  │
   │  │                 magic-link buttons                          │
   │  │       buttons:  [Approve as public]   (if public_requested) │
   │  │                 [Discard]                                   │
   │  │  5. → 200 { ok: true, id }                                  │
   │  └─────────────────────────────────────────────────────────────┘
   │
   │   maintainer clicks magic link in email
   │       │
   │       │   GET /v1/feedback/moderate?id=...&action=public|discard&t=<hmac>
   │       ▼
   │  ┌─────────────────────────────────────────────────────────────┐
   │  │ Worker                                                      │
   │  │  - verify HMAC(secret, id, action)                          │
   │  │  - UPDATE feedback SET status, moderated_at                 │
   │  │  - on approve_public: INSERT into                           │
   │  │      surfaceome_public.feedback_public  (sanitized subset)  │
   │  │  - returns small HTML page: "Approved & published" / "Done" │
   │  └─────────────────────────────────────────────────────────────┘
   │
   └─ <CommunityNotes>  (bottom of gene page, above DataSourcesFooter)
            │
            │   GET /v1/feedback/public?gene=SYMBOL
            ▼
       Worker selects approved notes; viewer renders comment +
       attribution + date.
```

**Approach:** extend the existing `cloudflare/workers/surfaceome_api/`
Worker. Single deploy, reuses CORS / error helpers / route shape. The
existing 845-line file gains ~200 lines for the three endpoints.

**Why not a separate Worker:** doubles wrangler.toml + secret +
deployment work. The existing Worker is the natural home — same domain,
same D1 pattern, same CORS posture.

## Data model

Two D1 tables. The private one carries PII and audit trail; the public
one is the sanitized subset the gene page renders. Both follow the
project's existing private/public mirror pattern (see `gene_identifier`
/ `gene_identifier_public`).

```sql
-- cloudflare/d1_schema.sql  (PRIVATE — surfaceome_agents DB)
CREATE TABLE IF NOT EXISTS feedback (
  id               TEXT PRIMARY KEY,         -- crypto.randomUUID()
  gene_symbol      TEXT NOT NULL,            -- e.g. "SRC"
  uniprot_acc      TEXT,                     -- e.g. "P12931", captured at submit
  submitter_name   TEXT NOT NULL,
  submitter_email  TEXT NOT NULL,
  subject          TEXT NOT NULL,            -- editable; becomes email subject
  comment          TEXT NOT NULL,            -- raw; max 4000 chars
  public_requested INTEGER NOT NULL DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'pending',
                   -- pending / approved_public / approved_private / discarded
  referrer         TEXT,                     -- gene-page URL submitter saw
  user_agent       TEXT,                     -- navigator.userAgent
  site_version     TEXT,                     -- git SHA at build time
  ip_hash          TEXT,                     -- SHA-256(CF-Connecting-IP + day-salt)
  approve_token    TEXT NOT NULL,            -- HMAC base64url; lives in magic-link
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  moderated_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_gene
  ON feedback(gene_symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_status
  ON feedback(status, created_at DESC);

-- cloudflare/d1_public_schema.sql  (PUBLIC mirror — surfaceome_public DB)
CREATE TABLE IF NOT EXISTS feedback_public (
  id              TEXT PRIMARY KEY,          -- same id as private row
  gene_symbol     TEXT NOT NULL,
  submitter_name  TEXT NOT NULL,             -- attribution; e-mail never published
  comment         TEXT NOT NULL,             -- sanitized at insert time
  approved_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_public_gene
  ON feedback_public(gene_symbol, approved_at DESC);
```

Private DB never exposes `submitter_email`, `ip_hash`, `user_agent`, or
unapproved rows. Public DB carries only the safe subset.

## Worker routes

All three live in `cloudflare/workers/surfaceome_api/src/index.js`. The
existing 405 method-gate (line 812) loosens to allow POST on the
submit endpoint only.

### `POST /v1/feedback/submit`

Body (JSON):
```json
{
  "gene":             "SRC",
  "uniprot_acc":      "P12931",
  "name":             "Submitter Name",
  "email":            "user@example.com",
  "subject":          "Surfaceome SRC (P12931) entry update request",
  "comment":          "...",
  "public_requested": false,
  "referrer":         "https://surfaceome.deliverome.org/SRC",
  "user_agent":       "Mozilla/5.0 ...",
  "site_version":     "8faeb338",
  "turnstile_token":  "..."
}
```

Steps:
1. **Verify Turnstile token** via `https://challenges.cloudflare.com/turnstile/v0/siteverify` with `env.TURNSTILE_SECRET_KEY`. Reject 400 on failure.
2. **Validate fields**: name 1–80, email regex, subject 1–200, comment 1–4000, gene matches `^[A-Z0-9-]{1,30}$`.
3. **Rate-limit**: SHA-256(`CF-Connecting-IP` + per-day salt) as the KV key; refuse 429 above 5 submissions / hour.
4. **Insert** into `FEEDBACK_DB.feedback` with `id = crypto.randomUUID()` and `approve_token = base64url(HMAC-SHA256(env.MAGIC_LINK_SECRET, id))`.
5. **Send email** via Resend (`https://api.resend.com/emails`):
   - From: `feedback@deliverome.org` (verified Resend sender)
   - To: maintainer (env var `MAINTAINER_EMAIL`)
   - Reply-To: submitter's email so the maintainer's reply goes back to them
   - Subject: the submitter's subject
   - Body: comment + additional info block (referrer / user agent / version) + magic-link buttons
6. Return `200 { ok: true, id }`.

### `GET /v1/feedback/moderate?id=<id>&action=<public|discard>&t=<hmac>`

1. **Verify HMAC**: compute `HMAC-SHA256(env.MAGIC_LINK_SECRET, id + action)`, constant-time-compare against `t`. Reject 403 on mismatch.
2. **Look up row** in `FEEDBACK_DB.feedback`. If row is already moderated (status ≠ `pending`), short-circuit with "Already handled" page (idempotent).
3. **On `action=public`**:
   - `UPDATE feedback SET status='approved_public', moderated_at=…`
   - Sanitize comment (HTML-strip via simple regex; comment renders as plaintext in the viewer anyway, but defense-in-depth)
   - `INSERT INTO surfaceome_public.feedback_public (id, gene_symbol, submitter_name, comment, approved_at)` — needs second DB binding inside the Worker for the cross-write; see "Bindings" below
4. **On `action=discard`**: `UPDATE feedback SET status='discarded', moderated_at=…`. No public-DB insert.
5. **Return a tiny HTML confirmation page** (so the maintainer sees "Approved & published" / "Discarded" in their browser, not raw JSON).

### `GET /v1/feedback/public?gene=SYMBOL`

```sql
SELECT id, submitter_name, comment, approved_at
FROM feedback_public
WHERE gene_symbol = ?
ORDER BY approved_at DESC
LIMIT 50;
```

Returns `{ gene, notes: [...] }`. Same CORS + cache posture as other GETs; short TTL (60s) since notes can land mid-day.

## Bindings + secrets (wrangler.toml)

The Worker grows two D1 bindings, one KV binding, and three secrets.

```toml
# existing
[[d1_databases]]
binding       = "DB"
database_name = "surfaceome_public"
database_id   = "<existing UUID>"

# new — feedback writes go here (private DB with PII)
[[d1_databases]]
binding       = "FEEDBACK_DB"
database_name = "surfaceome_agents"
database_id   = "<surfaceome_agents UUID>"

# new — rate-limit counters (5/hour/IP-hash)
[[kv_namespaces]]
binding = "FEEDBACK_RATELIMIT"
id      = "<KV namespace ID>"

# new — Resend, Turnstile, magic-link signing
# set via: npx wrangler secret put RESEND_API_KEY
#                                  TURNSTILE_SECRET_KEY
#                                  MAGIC_LINK_SECRET
#                                  MAINTAINER_EMAIL
```

Existing wrangler.toml.example must be updated to document the new
bindings (without leaking real IDs, same `REPLACE_WITH_*` pattern as
the existing `database_id`).

## Frontend

### `<FeedbackButton>` (gene page)

New component `viewer/components/FeedbackButton/FeedbackButton.tsx`,
rendered inline in `viewer/app/[symbol]/page.tsx` inside the existing
`crumbActions` span — same `crumbAction` styling as the JSON /
Markdown links so it sits visually with them:

```tsx
<span className={styles.crumbActions}>
  <a className={styles.crumbAction} href={`/data/surfaceome/${sym}.json`}>JSON ↗</a>
  <a className={styles.crumbAction} href={`/data/surfaceome/${sym}.md`}>Markdown (full) ↗</a>
  <FeedbackButton gene={sym} uniprot={rec.gene.uniprot_acc} />
</span>
```

Button label: `Submit feedback`. Click → opens the modal.

### `<FeedbackModal>`

Client component. Mounted next to `<EvidenceDrawer>` at the page level
so it sits above all card content (like the drawer). Hidden by
default; opened via the same CustomEvent pattern the EvidenceDrawer
uses (`surfaceome:open-feedback`) so the button can fire it without
prop-drilling.

Form structure mirrors UniProt's `entry update request` layout:

```
┌─ Submit updates or corrections to Surfaceome ─────────────────────┐
│ Our team will receive and review your message.                    │
│                                                                    │
│ Name *           [________________________]                       │
│ E-mail *         [________________________]                       │
│ Subject *        [Surfaceome SRC (P12931) entry update request ]  │
│                  (pre-filled, editable)                           │
│                                                                    │
│ Message *                                                          │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ We'd love to hear from you. Scientific feedback,             │ │
│ │ corrections, new citations, antibody clones you've           │ │
│ │ validated, missing isoforms — anything that would make this  │ │
│ │ entry more useful. Please include PMIDs, DOIs, or links      │ │
│ │ where you can, so we can incorporate the update with         │ │
│ │ provenance.                                                  │ │
│ │                                                              │ │
│ │ [user types here]                                            │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ Additional information                                             │
│ ─────────────────────                                              │
│ This is sent with your message so we can help you.                │
│  • Referred from:   https://surfaceome.deliverome.org/SRC         │
│  • User browser:    Mozilla/5.0 (Macintosh; Intel Mac OS X ...)   │
│  • Website version: 8faeb338                                      │
│                                                                    │
│ [ ] Post my comment publicly on the gene page after our review.   │
│     Your name will be shown as attribution; e-mail will not.      │
│                                                                    │
│ We collect your name and e-mail so we can reply to your           │
│ feedback. We do not share your information with third parties.    │
│ Email contact@deliverome.org to request deletion at any time.     │
│                                                                    │
│ [Cloudflare Turnstile widget]                                      │
│                                                                    │
│              [Cancel]      [Submit feedback]                       │
└────────────────────────────────────────────────────────────────────┘
```

Field semantics:

| Field             | Required | Notes                                                       |
| ----------------- | -------- | ----------------------------------------------------------- |
| Name              | yes      | 1–80 chars                                                   |
| E-mail            | yes      | RFC-ish regex                                                |
| Subject           | yes      | pre-filled `"Surfaceome {SYMBOL} ({UNIPROT_ACC}) entry update request"`, editable |
| Message           | yes      | up to 4000 chars                                             |
| Public checkbox   | no       | default off; explains attribution rules                      |
| Additional info   | shown read-only; auto-captured: referrer, navigator.userAgent, `NEXT_PUBLIC_GIT_SHA` |

After successful POST: modal swaps to a confirmation panel — "Thank
you. We've received your submission and will reply by e-mail." with a
Close button. On failure: show the server's error string under the
submit button, leave the form filled.

### `<CommunityNotes>`

New component `viewer/components/surfaceome/CommunityNotesCard/`.
Renders inside a `<SectionCard>` at the very bottom of the gene-page
section list (after the Evidence ledger, before `DataSourcesFooter`).

Behavior:
- Client component (uses fetch + state)
- On mount: `fetch('/v1/feedback/public?gene=SYMBOL')`
- Renders empty (`return null`) when notes list is empty
- Renders each note as plaintext comment + attribution byline ("— Submitter Name · YYYY-MM-DD")
- No edit / delete affordance for readers; moderation lives in maintainer's email + D1

`SECTION` array in `viewer/app/[symbol]/page.tsx` gains:

```ts
{ kind: "community", label: "Community notes",
  render: (n) => <CommunityNotesCard gene={rec.gene.hgnc_symbol} n={n} /> }
```

### Git-SHA exposure

`NEXT_PUBLIC_GIT_SHA` set in `viewer/next.config.mjs`:

```js
env: {
  NEXT_PUBLIC_GIT_SHA: process.env.GIT_SHA
    ?? execSync('git rev-parse --short HEAD').toString().trim(),
}
```

Read in the modal via `process.env.NEXT_PUBLIC_GIT_SHA`. Cloudflare
Pages already injects `CF_PAGES_COMMIT_SHA`; that's the fallback in CI.

## Security

- **Turnstile** verifies every submission server-side; bot traffic drops to ~0.
- **Rate limit**: KV-backed 5 submissions / IP-hash / hour; daily IP salt rotation so the hash isn't a long-term identifier.
- **HMAC magic link** signs `id + action` with a 32-byte secret (env). Token is base64url, 43 chars. Constant-time compare on verify.
- **Idempotent moderation**: re-clicking a magic link after a row is already moderated returns "Already handled" without re-applying — survives double-clicks and email forwards.
- **Comment sanitization**: HTML stripped at insert into `feedback_public`. Viewer renders as plaintext (`<p>{comment}</p>`) — no `dangerouslySetInnerHTML`.
- **PII isolation**: e-mail / IP / user-agent never crosses into `surfaceome_public`. The public DB is also the one the existing API + viewer have direct access to; the private DB is firewall'd behind the Worker's POST/moderate paths only.
- **Resend From-address**: `feedback@deliverome.org`, with Reply-To set to submitter's e-mail. Domain must have SPF + DKIM records (Resend provides values) so the notification doesn't land in spam.

## Privacy notice

Inline single-sentence statement under the form (no separate Privacy
Policy page, no consent checkbox). Covers the three GDPR essentials
for a low-risk contact form: what we collect, why, deletion path.

> We collect your name and e-mail so we can reply to your feedback. We
> do not share your information with third parties. Email
> contact@deliverome.org to request deletion at any time.

If the project later needs a formal Privacy Policy (e.g. for a journal
submission), promote this sentence to a `/privacy` page and update the
form footer to link to it.

## Error handling + edge cases

| Case                                                    | Behavior                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Turnstile token invalid / expired                       | 400 with message "Verification expired — please reload and try again"                  |
| Rate limit exceeded                                     | 429 with message "Too many submissions from this address — please try again later"     |
| Field validation fails (empty, too long, malformed)     | 400 with field-specific message                                                         |
| Resend API failure                                      | Submission is still persisted in D1; user sees 202 "Received; e-mail delivery delayed". Maintainer can replay outbound from D1 next time. |
| Magic-link token invalid                                | 403 HTML page "This link has expired or is invalid"                                     |
| Magic-link clicked twice                                | Second click returns idempotent "Already handled" page (no re-INSERT into public mirror)|
| `feedback_public` write fails after `feedback` UPDATE   | Logged via `console.error`; maintainer can replay from private DB row (status flipped, public row missing) |
| Submitter omits public-posting checkbox                 | Email contains only [Discard] magic link, no [Approve as public]                       |
| Worker can't reach Turnstile siteverify                 | 503 — soft-fail with retry-after; do not insert                                         |
| `feedback_public` empty for a gene                      | `<CommunityNotes>` renders nothing (no empty-state UI; section invisible)              |
| Browser missing `navigator.userAgent`                   | `user_agent` field stored empty                                                          |

## Verification

1. Apply schemas via `D1Client.query()` (per CLAUDE.md, the wrangler-less path): each `CREATE TABLE` / `CREATE INDEX` as separate calls.
2. Set wrangler secrets locally (dev D1 + KV) and run `npx wrangler dev` against the Worker. Use `curl` to hit:
   - `POST /v1/feedback/submit` with a valid Turnstile dev token → expect 200, row in D1, e-mail in Resend dashboard.
   - `GET /v1/feedback/moderate?...&action=public` from the link in the e-mail → expect HTML "Approved & published".
   - `GET /v1/feedback/public?gene=SRC` → expect the approved note.
3. From `viewer/` run `npm run dev`, open `/SRC`, click "Submit feedback", fill the form, watch the network panel + dev D1.
4. End-to-end with `npm run build` to confirm SSG isn't broken by the new client components.
5. `bash scripts/check-py.sh` for the Python side (unaffected, but tripwires might catch schema-binding drift if introduced).

## Scope explicitly out

- A standalone `/privacy` page.
- A "Community notes" view in the catalog table (only on gene pages).
- Edit / delete affordance for submitters.
- Threading or replies between submitter and reader.
- Notification of submitter when their note is published.
- Moderation queue UI for the maintainer (D1 dashboard suffices today).
- Markdown / link rendering inside the comment body (plaintext only).
