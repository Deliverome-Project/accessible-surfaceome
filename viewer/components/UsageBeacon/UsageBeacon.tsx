"use client";

import { useEffect } from "react";
import { clickedControl, describeControl, trackingDeclined } from "../../lib/usage-events";

const API_BASE = (
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE ??
  "https://api.deliverome.org/surfaceome"
).replace(/\/+$/, "");

/**
 * Sends one anonymous event per click on a link or button (see
 * lib/usage-events.ts). Mounted once in the root layout; renders nothing.
 * `sendBeacon` with a text/plain body is a CORS "simple" request, so there is
 * no preflight and the beacon survives the click navigating away.
 */
export function UsageBeacon() {
  useEffect(() => {
    if (trackingDeclined(navigator as Navigator & { globalPrivacyControl?: boolean })) return;
    if (typeof navigator.sendBeacon !== "function") return;
    const onClick = (e: MouseEvent) => {
      const el = clickedControl(e.target);
      if (!el) return;
      const ev = describeControl(el, window.location.pathname, window.location.origin);
      if (!ev) return;
      try {
        navigator.sendBeacon(`${API_BASE}/v1/events`, new Blob([JSON.stringify(ev)], { type: "text/plain" }));
      } catch {
        // Never let analytics break a click.
      }
    };
    document.addEventListener("click", onClick, { capture: true, passive: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);
  return null;
}
