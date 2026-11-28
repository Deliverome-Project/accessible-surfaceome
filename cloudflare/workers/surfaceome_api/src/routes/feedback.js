// Community feedback submission, email moderation (signed GET + POST), and public list.

import { CACHE_TTL_SHORT, badRequest, checkSymbol, htmlResponse, json } from "../lib/http.js";

import { hmacSign, sha256Hex, timingSafeEqualStr } from "../lib/crypto.js";

import { checkRateLimit } from "../lib/cache.js";

// === Feedback flow helpers ================================================
// All functions in this block support the three /v1/feedback/* endpoints
// added below. They never leak PII or unsanitized HTML across the
// public/private boundary.

// Hex-encode an ArrayBuffer or Uint8Array.

export function sanitizeComment(s) {
  return String(s ?? "")
    .replace(/<[^>]*>/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .trim()
    .slice(0, 4000);
}

// Cheap email-shape check. Real validation lives at the auth layer
// (we never auto-trust the address); this is just "does it look like
// an email at all".
export function looksLikeEmail(s) {
  return typeof s === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

// HTML-escape a string for safe embedding in the moderate-confirmation
// page and the Resend email body.
export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Verify a Cloudflare Turnstile token against the siteverify endpoint.
// Returns true on success, false on failure (does NOT throw — caller
// decides response code).
export async function verifyTurnstile(token, secret, remoteIp) {
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
// `prefix` and `max` let another endpoint keep its own counter in the same KV
// (the L1 review page uses "l1rl", 30/hour); the defaults are the feedback form's.

export async function sendFeedbackEmail({ apiKey, from, to, replyTo, subject, html }) {
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
export function feedbackEmailHtml({ rec, base, approvePublicUrl, discardUrl }) {
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

export async function handleFeedbackSubmit(request, env, url) {
  // Parse + validate body.
  let body;
  try {
    body = await request.json();
  } catch {
    return badRequest("invalid_json");
  }
  const gene = String(body.gene ?? "").trim();
  // Allow lowercase to match mixed-case HGNC symbols (e.g. C11orf24), same as handleFeedbackPublic.
  if (!/^[A-Za-z0-9-]{1,30}$/.test(gene)) return badRequest("invalid_gene");
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
  const prefix = url.pathname.startsWith("/surfaceome/") ? "/surfaceome" : "";
  const base = `${url.protocol}//${url.host}${prefix}`;
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

// HTML confirmation page (no JS — either shows the outcome or a POST confirm form).
export function moderateHtmlPage({ title, message, accent = "#922038", form = null }) {
  const formHtml = form
    ? `<form method="POST" action="" style="margin-top:1.5em">
    <input type="hidden" name="id" value="${escapeHtml(form.id)}" />
    <input type="hidden" name="action" value="${escapeHtml(form.action)}" />
    <input type="hidden" name="t" value="${escapeHtml(form.t)}" />
    <button type="submit" style="background:${accent};color:#fff;border:0;border-radius:6px;padding:0.65em 1.25em;font-size:1rem;cursor:pointer">${escapeHtml(form.buttonLabel)}</button>
  </form>`
    : `<p class="hint">You can close this tab.</p>`;
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
  ${formHtml}
</body></html>`;
}


export async function verifyModerateRequest(env, { id, action, t }) {
  if (!id || !action || !t) {
    return {
      error: htmlResponse(
        moderateHtmlPage({
          title: "Invalid link",
          message: "This moderation link is missing required parameters.",
        }),
        { status: 400 },
      ),
    };
  }
  if (action !== "public" && action !== "discard") {
    return {
      error: htmlResponse(
        moderateHtmlPage({
          title: "Invalid link",
          message: "Unknown action.",
        }),
        { status: 400 },
      ),
    };
  }
  const expected = await hmacSign(env.MAGIC_LINK_SECRET, `${id}:${action}`);
  if (!timingSafeEqualStr(expected, t)) {
    return {
      error: htmlResponse(
        moderateHtmlPage({
          title: "Invalid link",
          message: "This link is invalid or has been tampered with.",
        }),
        { status: 403 },
      ),
    };
  }

  const row = await env.FEEDBACK_DB.prepare(
    "SELECT id, gene_symbol, submitter_name, comment, status FROM feedback WHERE id = ?",
  ).bind(id).first();
  if (!row) {
    return {
      error: htmlResponse(
        moderateHtmlPage({
          title: "Not found",
          message: "We couldn't find that submission.",
        }),
        { status: 404 },
      ),
    };
  }
  if (row.status !== "pending") {
    return {
      error: htmlResponse(
        moderateHtmlPage({
          title: "Already handled",
          message: `This submission was already marked "${row.status}".`,
        }),
      ),
    };
  }
  return { row, id, action, t };
}

// GET never mutates D1 so email link-scanners (Safe Links, Proofpoint, etc.)
// cannot auto-approve or auto-discard pending submissions on prefetch.
export async function handleFeedbackModerate(env, url) {
  const id = url.searchParams.get("id");
  const action = url.searchParams.get("action");
  const t = url.searchParams.get("t");
  const checked = await verifyModerateRequest(env, { id, action, t });
  if (checked.error) return checked.error;
  const { row } = checked;
  const isDiscard = action === "discard";
  return htmlResponse(
    moderateHtmlPage({
      title: isDiscard ? "Confirm discard" : "Confirm publish",
      message: isDiscard
        ? `Discard the submission about ${row.gene_symbol} from ${row.submitter_name}?`
        : `Approve and publish ${row.submitter_name}'s note on ${row.gene_symbol} to the public gene page?`,
      accent: isDiscard ? "#6f5d5a" : "#922038",
      form: {
        id,
        action,
        t,
        buttonLabel: isDiscard ? "Confirm discard" : "Confirm & publish",
      },
    }),
  );
}

export async function handleFeedbackModeratePost(request, env, url) {
  let id = url.searchParams.get("id");
  let action = url.searchParams.get("action");
  let t = url.searchParams.get("t");
  const ct = request.headers.get("Content-Type") ?? "";
  if (ct.includes("application/x-www-form-urlencoded")) {
    const params = new URLSearchParams(await request.text());
    id = params.get("id") ?? id;
    action = params.get("action") ?? action;
    t = params.get("t") ?? t;
  }
  const checked = await verifyModerateRequest(env, { id, action, t });
  if (checked.error) return checked.error;
  const { row } = checked;

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

export async function handleFeedbackPublic(env, url) {
  const gene = url.searchParams.get("gene");
  // Allow lowercase: some HGNC symbols are mixed-case (the Cxorf class,
  // e.g. C11orf24), and gene_symbol is matched COLLATE NOCASE below.
  if (!gene || !/^[A-Za-z0-9-]{1,30}$/.test(gene)) {
    return badRequest("invalid_gene");
  }
  const rows = await env.DB.prepare(
    `SELECT id, submitter_name, comment, approved_at
     FROM feedback_public
     WHERE gene_symbol = ? COLLATE NOCASE
     ORDER BY approved_at DESC
     LIMIT 50`,
  ).bind(gene).all();
  return json({ gene, notes: rows.results }, { ttl: CACHE_TTL_SHORT });
}
