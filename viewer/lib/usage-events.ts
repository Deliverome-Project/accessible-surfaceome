/**
 * Anonymous click events for the viewer (see `UsageBeacon`).
 *
 * One event per click on a link or button: the page path, what kind of
 * control it was and the control's visible label. No cookie, identifier,
 * query string or form value is ever sent, and nothing is sent when the
 * browser asks not to be tracked. The Worker's `POST /v1/events` stores only
 * the aggregate fields; `/privacy` describes this, so keep the two in step.
 */

export type UsageEventKind = "link" | "external" | "button";

export type UsageEvent = {
  path: string;
  kind: UsageEventKind;
  label: string;
};

const CONTROL_SELECTOR = "a[href], button, summary, [role='button'], [role='tab'], [data-track]";
const LABEL_MAX = 80;

/** The control a click landed on, or null when it wasn't on one. */
export function clickedControl(target: EventTarget | null): Element | null {
  if (!target || typeof (target as Element).closest !== "function") return null;
  const el = (target as Element).closest(CONTROL_SELECTOR);
  if (!el || el.closest("[data-track-ignore]")) return null;
  return el;
}

/**
 * Describe a clicked control as an event, or null when it has no usable
 * label. `data-track` names a control explicitly; otherwise its accessible
 * name (aria-label, title) or visible text is used.
 */
export function describeControl(el: Element, path: string, origin: string): UsageEvent | null {
  const raw =
    el.getAttribute("data-track") ??
    el.getAttribute("aria-label") ??
    el.getAttribute("title") ??
    el.textContent ??
    "";
  const label = raw.replace(/\s+/g, " ").trim().slice(0, LABEL_MAX);
  if (!label || label.includes("@")) return null;
  let kind: UsageEventKind = "button";
  const href = el.tagName === "A" ? el.getAttribute("href") : null;
  if (href !== null) {
    let external = false;
    try {
      external = new URL(href, origin).origin !== origin;
    } catch {
      external = false;
    }
    kind = external ? "external" : "link";
  }
  return { path, kind, label };
}

/** Global Privacy Control or Do Not Track set → send nothing. */
export function trackingDeclined(nav: { doNotTrack?: string | null; globalPrivacyControl?: boolean }): boolean {
  return nav.globalPrivacyControl === true || nav.doNotTrack === "1";
}
