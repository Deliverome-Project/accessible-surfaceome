"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import styles from "./FeedbackModal.module.css";

const API_BASE =
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE
  ?? "https://api.deliverome.org/surfaceome";
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const SITE_VERSION = process.env.NEXT_PUBLIC_GIT_SHA ?? "unknown";

// Opt-in "remember my name + e-mail on this device" convenience. These keys are
// written to localStorage ONLY when the visitor checks the box — first-party,
// never sent anywhere until they submit, and cleared the moment they uncheck.
const LS_NAME = "surfaceome:feedback:name";
const LS_EMAIL = "surfaceome:feedback:email";

// Best-effort localStorage — private mode / blocked storage throws on access, so
// every read and write is guarded and degrades to "don't remember".
function readRemembered(): { name: string; email: string } | null {
  try {
    const name = localStorage.getItem(LS_NAME);
    const email = localStorage.getItem(LS_EMAIL);
    if (name || email) return { name: name ?? "", email: email ?? "" };
  } catch {
    /* storage unavailable */
  }
  return null;
}

function writeRemembered(name: string, email: string): void {
  try {
    localStorage.setItem(LS_NAME, name);
    localStorage.setItem(LS_EMAIL, email);
  } catch {
    /* storage unavailable — remembering is best-effort */
  }
}

function clearRemembered(): void {
  try {
    localStorage.removeItem(LS_NAME);
    localStorage.removeItem(LS_EMAIL);
  } catch {
    /* storage unavailable */
  }
}

// Augment window for the Turnstile global the loader-script defines.
declare global {
  interface Window {
    turnstile?: {
      render: (
        el: HTMLElement | string,
        opts: { sitekey: string; callback: (token: string) => void;
                "error-callback"?: () => void;
                "expired-callback"?: () => void; },
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

const TURNSTILE_SCRIPT_ID = "cf-turnstile-script";

function ensureTurnstileScript() {
  if (typeof document === "undefined") return;
  if (document.getElementById(TURNSTILE_SCRIPT_ID)) return;
  const s = document.createElement("script");
  s.id = TURNSTILE_SCRIPT_ID;
  s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
  s.async = true;
  s.defer = true;
  document.head.appendChild(s);
}

type Phase = "form" | "submitting" | "success" | "error";

interface OpenDetail {
  gene: string;
  uniprotAcc: string | null;
}

export function FeedbackModal() {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [gene, setGene] = useState<string>("");
  const [uniprotAcc, setUniprotAcc] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [comment, setComment] = useState("");
  const [publicRequested, setPublicRequested] = useState(false);
  // Opt-in: remember name + e-mail in this browser for next time (default off).
  const [remember, setRemember] = useState(false);

  // Turnstile token (filled by the widget's callback)
  const turnstileTokenRef = useRef<string>("");
  const widgetIdRef = useRef<string>("");
  const widgetSlotRef = useRef<HTMLDivElement | null>(null);

  // Listen for the open event.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<OpenDetail>).detail;
      if (!detail) return;
      setGene(detail.gene);
      setUniprotAcc(detail.uniprotAcc);
      setSubject(
        `Surfaceome ${detail.gene}${
          detail.uniprotAcc ? ` (${detail.uniprotAcc})` : ""
        } entry update request`,
      );
      setPhase("form");
      setErrorMsg("");
      // Prefill from a prior opt-in "remember" (if the visitor chose it before).
      const saved = readRemembered();
      if (saved) {
        setName(saved.name);
        setEmail(saved.email);
        setRemember(true);
      }
      setOpen(true);
    };
    window.addEventListener("surfaceome:open-feedback", handler);
    return () => window.removeEventListener("surfaceome:open-feedback", handler);
  }, []);

  // Inject Turnstile script + render widget when modal becomes visible.
  useEffect(() => {
    if (!open || phase !== "form" || !SITE_KEY) return;
    ensureTurnstileScript();

    let cancelled = false;
    const tryRender = () => {
      if (cancelled) return;
      const ts = window.turnstile;
      const slot = widgetSlotRef.current;
      if (!ts || !slot) {
        window.setTimeout(tryRender, 120);
        return;
      }
      // Clear any prior widget (modal can re-open multiple times).
      if (widgetIdRef.current) {
        try { ts.remove(widgetIdRef.current); } catch {}
        widgetIdRef.current = "";
      }
      slot.innerHTML = "";
      widgetIdRef.current = ts.render(slot, {
        sitekey: SITE_KEY,
        callback: (token: string) => { turnstileTokenRef.current = token; },
        "error-callback": () => { turnstileTokenRef.current = ""; },
        "expired-callback": () => { turnstileTokenRef.current = ""; },
      });
    };
    tryRender();
    return () => { cancelled = true; };
  }, [open, phase]);

  // Reset and close.
  const handleClose = useCallback(() => {
    setOpen(false);
    // Defer the reset so the close animation isn't visibly wiping fields.
    window.setTimeout(() => {
      setPhase("form");
      setErrorMsg("");
      setName("");
      setEmail("");
      setSubject("");
      setComment("");
      setPublicRequested(false);
      setRemember(false);
      turnstileTokenRef.current = "";
      if (widgetIdRef.current && window.turnstile) {
        try { window.turnstile.remove(widgetIdRef.current); } catch {}
        widgetIdRef.current = "";
      }
    }, 200);
  }, []);

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, handleClose]);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (phase === "submitting") return;

    // Validate the simple stuff client-side. Server re-validates.
    if (!name.trim()) return setErrorMsg("Please enter your name.") as unknown as void;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      return setErrorMsg("Please enter a valid e-mail.") as unknown as void;
    if (!subject.trim()) return setErrorMsg("Subject is required.") as unknown as void;
    if (!comment.trim()) return setErrorMsg("Please write your message.") as unknown as void;
    if (!turnstileTokenRef.current)
      return setErrorMsg("Please complete the verification widget.") as unknown as void;

    setErrorMsg("");
    setPhase("submitting");

    const body = {
      gene,
      uniprot_acc: uniprotAcc,
      name: name.trim(),
      email: email.trim(),
      subject: subject.trim(),
      comment: comment.trim(),
      public_requested: publicRequested,
      referrer: typeof window !== "undefined" ? window.location.href : "",
      user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "",
      site_version: SITE_VERSION,
      turnstile_token: turnstileTokenRef.current,
    };

    try {
      const r = await fetch(`${API_BASE}/v1/feedback/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        const err = j?.error ?? `Server returned ${r.status}.`;
        setErrorMsg(prettyError(err));
        setPhase("error");
        // Reset turnstile so they can retry.
        turnstileTokenRef.current = "";
        if (widgetIdRef.current && window.turnstile) {
          try { window.turnstile.reset(widgetIdRef.current); } catch {}
        }
        return;
      }
      // Honor the opt-in: persist on success if checked, else make sure nothing
      // lingers. Only reached after a successful submit, so we never store an
      // address the visitor didn't actually send.
      if (remember) writeRemembered(name.trim(), email.trim());
      else clearRemembered();
      setPhase("success");
    } catch (err) {
      setErrorMsg("We couldn't reach the server. Please try again in a moment.");
      setPhase("error");
    }
  };

  if (!open) return null;
  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className={styles.dialog}>
        {phase === "success" ? (
          <>
            <h2 id="feedback-modal-title" className={styles.title}>
              Thank you
            </h2>
            <p className={styles.lede}>
              We've received your submission and will reply by e-mail.
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                onClick={handleClose}
                className={styles.submit}
              >
                Close
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <h2 id="feedback-modal-title" className={styles.title}>
              Submit updates or corrections to Surfaceome
            </h2>
            <p className={styles.lede}>
              Our team will receive and review your message.
            </p>

            <div className={styles.field}>
              <label htmlFor="feedback-name">Name <span aria-hidden>*</span></label>
              <input
                id="feedback-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={80}
                required
                autoComplete="name"
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="feedback-email">E-mail <span aria-hidden>*</span></label>
              <input
                id="feedback-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </div>

            <label className={styles.checkbox}>
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => {
                  const on = e.target.checked;
                  setRemember(on);
                  // Uncheck clears immediately, so leaving without submitting
                  // still wipes any previously-remembered values.
                  if (!on) clearRemembered();
                }}
              />
              <span>
                Remember my name and e-mail in this browser to prefill this form
                next time.
              </span>
            </label>

            <div className={styles.field}>
              <label htmlFor="feedback-subject">Subject <span aria-hidden>*</span></label>
              <input
                id="feedback-subject"
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={200}
                required
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="feedback-comment">Message <span aria-hidden>*</span></label>
              <textarea
                id="feedback-comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={4000}
                rows={7}
                required
                placeholder={
                  "We'd love to hear from you. Scientific feedback, " +
                  "corrections, new citations, antibody clones you've " +
                  "validated, missing isoforms — anything that would make " +
                  "this entry more useful. Please include PMIDs, DOIs, or " +
                  "links where you can, so we can incorporate the update " +
                  "with provenance."
                }
              />
            </div>

            <div className={styles.additional}>
              <p className={styles.additionalLabel}>Additional information</p>
              <p className={styles.additionalHint}>
                This is sent with your message so we can help you.
              </p>
              <ul className={styles.additionalList}>
                <li>
                  <span>Referred from:</span>{" "}
                  <code>
                    {typeof window !== "undefined" ? window.location.href : ""}
                  </code>
                </li>
                <li>
                  <span>User browser:</span>{" "}
                  <code>
                    {typeof navigator !== "undefined" ? navigator.userAgent : ""}
                  </code>
                </li>
                <li>
                  <span>Website version:</span>{" "}
                  <code>{SITE_VERSION}</code>
                </li>
              </ul>
            </div>

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
              feedback. We do not share your information with third parties. If
              you check &ldquo;remember&rdquo; above, your name and e-mail are
              saved only in this browser (never sent anywhere until you submit)
              to prefill this form next time; unchecking it clears them. Email{" "}
              <a href="mailto:surfaceome-viewer@deliverome.org">
                surfaceome-viewer@deliverome.org
              </a>{" "}
              to request deletion at any time.
            </p>

            <div ref={widgetSlotRef} className={styles.turnstile} />

            {errorMsg ? (
              <p className={styles.error} role="alert">{errorMsg}</p>
            ) : null}

            <div className={styles.actions}>
              <button
                type="button"
                onClick={handleClose}
                className={styles.cancel}
                disabled={phase === "submitting"}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={styles.submit}
                disabled={phase === "submitting"}
              >
                {phase === "submitting" ? "Submitting…" : "Submit feedback"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function prettyError(code: string): string {
  switch (code) {
    case "invalid_gene": return "We couldn't identify the gene for this submission.";
    case "invalid_name": return "Please enter your name (up to 80 characters).";
    case "invalid_email": return "Please enter a valid e-mail address.";
    case "invalid_subject": return "Please add a subject (up to 200 characters).";
    case "invalid_comment": return "Please write your message (up to 4000 characters).";
    case "turnstile_failed": return "Verification failed. Please reload and try again.";
    case "rate_limited": return "Too many submissions from this address — please try again later.";
    default: return `Submission failed (${code}). Please try again.`;
  }
}
