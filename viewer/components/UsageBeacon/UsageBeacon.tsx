"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { clickedControl, describeControl, trackingDeclined } from "../../lib/usage-events";

const API_BASE = (
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE ??
  "https://api.deliverome.org/surfaceome"
).replace(/\/+$/, "");

function send(ev: object) {
  try {
    navigator.sendBeacon(`${API_BASE}/v1/events`, new Blob([JSON.stringify(ev)], { type: "text/plain" }));
  } catch {
    // Never let analytics break the page.
  }
}

function canSend(): boolean {
  return (
    !trackingDeclined(navigator as Navigator & { globalPrivacyControl?: boolean }) &&
    typeof navigator.sendBeacon === "function"
  );
}

/**
 * Sends one anonymous event per page view and per click on a link or button
 * (see lib/usage-events.ts). Mounted once in the root layout; renders nothing.
 * `sendBeacon` with a text/plain body is a CORS "simple" request, so there is
 * no preflight and the beacon survives the click navigating away.
 */
export function UsageBeacon() {
  const pathname = usePathname();

  // The page's path only; the Worker turns it into a daily visitor count.
  useEffect(() => {
    if (canSend()) send({ path: window.location.pathname, kind: "pageview" });
  }, [pathname]);

  useEffect(() => {
    if (!canSend()) return;
    const onClick = (e: MouseEvent) => {
      const el = clickedControl(e.target);
      if (!el) return;
      const ev = describeControl(el, window.location.pathname, window.location.origin);
      if (ev) send(ev);
    };
    document.addEventListener("click", onClick, { capture: true, passive: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);
  return null;
}
