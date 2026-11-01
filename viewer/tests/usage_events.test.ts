import assert from "node:assert/strict";
import { test } from "node:test";
import { clickedControl, describeControl, trackingDeclined } from "../lib/usage-events";

const ORIGIN = "https://surfaceome.deliverome.org";

/** Minimal Element stand-in: just the members usage-events reads. */
function el(
  tag: string,
  attrs: Record<string, string> = {},
  text = "",
  opts: { ignored?: boolean; control?: boolean } = {},
) {
  const node = {
    tagName: tag,
    textContent: text,
    getAttribute: (k: string) => (k in attrs ? attrs[k] : null),
    closest: (sel: string) => {
      if (sel === "[data-track-ignore]") return opts.ignored ? node : null;
      return opts.control === false ? null : node;
    },
  };
  return node as unknown as Element;
}

test("internal link uses its visible text, whitespace collapsed", () => {
  assert.deepEqual(describeControl(el("A", { href: "/EGFR/" }, "  EGFR \n "), "/", ORIGIN), {
    path: "/",
    kind: "link",
    label: "EGFR",
  });
});

test("off-site link is external", () => {
  const ev = describeControl(el("A", { href: "https://pubmed.ncbi.nlm.nih.gov/1/" }, "PMID 1"), "/EGFR/", ORIGIN);
  assert.equal(ev?.kind, "external");
});

test("data-track beats aria-label, title and text", () => {
  const ev = describeControl(
    el("A", { href: "https://orcid.org/0000-0001", title: "ORCID: 0000-0001", "data-track": "ORCID" }, "ORCID ↗"),
    "/EGFR/",
    ORIGIN,
  );
  assert.equal(ev?.label, "ORCID");
});

test("button uses aria-label when there is no data-track", () => {
  const ev = describeControl(el("BUTTON", { "aria-label": "Close dialog" }, "×"), "/", ORIGIN);
  assert.deepEqual(ev, { path: "/", kind: "button", label: "Close dialog" });
});

test("long labels are truncated and e-mail shaped labels dropped", () => {
  assert.equal(describeControl(el("BUTTON", {}, "x".repeat(200)), "/", ORIGIN)?.label.length, 80);
  assert.equal(describeControl(el("A", { href: "mailto:a@b.org" }, "a@b.org"), "/", ORIGIN), null);
  assert.equal(describeControl(el("BUTTON", {}, "   "), "/", ORIGIN), null);
});

test("clicks outside a control, or inside data-track-ignore, are skipped", () => {
  assert.equal(clickedControl(null), null);
  assert.equal(clickedControl(el("DIV", {}, "", { control: false })), null);
  assert.equal(clickedControl(el("BUTTON", {}, "x", { ignored: true })), null);
  assert.ok(clickedControl(el("BUTTON", {}, "x")));
});

test("Global Privacy Control or Do Not Track turns tracking off", () => {
  assert.equal(trackingDeclined({ globalPrivacyControl: true }), true);
  assert.equal(trackingDeclined({ doNotTrack: "1" }), true);
  assert.equal(trackingDeclined({ doNotTrack: "0" }), false);
  assert.equal(trackingDeclined({}), false);
});
