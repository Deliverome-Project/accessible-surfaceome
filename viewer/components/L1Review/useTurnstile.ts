"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Cloudflare Turnstile for the L1 review page's writes. Same site key and loader script
// as the feedback form (FeedbackModal); the Worker verifies each token against the
// matching secret. Tokens are single use and expire after ~5 minutes, so `take()` hands
// out the current one and resets the widget, which fetches the next in the background.
//
// `appearance: "interaction-only"` keeps the widget invisible unless Cloudflare wants
// the reviewer to click something, so it costs no space on the page.

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const SCRIPT_ID = "cf-turnstile-script"; // shared with FeedbackModal: loaded once
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

// Local view of the global (FeedbackModal declares a narrower one on Window).
interface TurnstileApi {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId: string) => void;
}
const api = (): TurnstileApi | undefined =>
  (window as unknown as { turnstile?: TurnstileApi }).turnstile;

export type TurnstileStatus = "off" | "loading" | "ready" | "error";

export function useTurnstile() {
  const slotRef = useRef<HTMLDivElement | null>(null);
  const tokenRef = useRef("");
  const widgetRef = useRef("");
  const [status, setStatus] = useState<TurnstileStatus>(SITE_KEY ? "loading" : "off");
  // True only while Cloudflare shows an interactive challenge; the page folds the
  // widget's slot away otherwise, including the "Success" tick after a pass.
  const [needsClick, setNeedsClick] = useState(false);

  useEffect(() => {
    if (!SITE_KEY) return;
    if (!document.getElementById(SCRIPT_ID)) {
      const s = document.createElement("script");
      s.id = SCRIPT_ID;
      s.src = SCRIPT_SRC;
      s.async = true;
      s.defer = true;
      document.head.appendChild(s);
    }
    let cancelled = false;
    const tryRender = () => {
      if (cancelled) return;
      const ts = api();
      if (!ts || !slotRef.current) {
        window.setTimeout(tryRender, 150);
        return;
      }
      widgetRef.current = ts.render(slotRef.current, {
        sitekey: SITE_KEY,
        appearance: "interaction-only",
        action: "l1-review",
        callback: (t: string) => {
          tokenRef.current = t;
          setStatus("ready");
          setNeedsClick(false);
        },
        "before-interactive-callback": () => setNeedsClick(true),
        "after-interactive-callback": () => setNeedsClick(false),
        "error-callback": () => {
          tokenRef.current = "";
          setStatus("error");
          setNeedsClick(false);
        },
        "expired-callback": () => {
          tokenRef.current = "";
          setStatus("loading");
          if (widgetRef.current) api()?.reset(widgetRef.current);
        },
      });
    };
    tryRender();
    return () => {
      cancelled = true;
      if (widgetRef.current) {
        try {
          api()?.remove(widgetRef.current);
        } catch {
          /* already gone */
        }
        widgetRef.current = "";
      }
    };
  }, []);

  /** The current token (or "" if none yet); the widget then fetches a fresh one. */
  const take = useCallback((): string => {
    const t = tokenRef.current;
    tokenRef.current = "";
    if (widgetRef.current) {
      setStatus("loading");
      try {
        api()?.reset(widgetRef.current);
      } catch {
        /* widget gone; the next render will retry */
      }
    }
    return t;
  }, []);

  return { slotRef, take, status, needsClick };
}

/** What the review panel needs from the page's Turnstile widget. */
export type ReviewAuth = { take: () => string; status: TurnstileStatus };
