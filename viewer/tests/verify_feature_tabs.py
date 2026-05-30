"""Feature-tab ↔ chip connection test.

Asserts the structural contract behind the three "feature" tabs on a
gene page: the LLM `rec.filters` summary chips that used to live inside
the §01 "Summary metrics" card are now surfaced under three standalone
top-level tabs — Biology (03), Expression (04), Risks (05) — each tab
carrying its own chip row *and* the expanded prose/evidence card that
maps to that chip category.

The "connection" this guards is the binding between a chip category and
its tab: each `ul[data-feature-chips="<cat>"]` chip row must render
inside the matching `section[data-section-id="<cat>"]`, and the old
LLM chip groups must no longer appear under the deterministic
"Summary metrics" (metrics) section.

Run against a live dev server (the viewer SSGs every section into the
DOM up front and only CSS-hides the inactive ones, so no tab clicking
is needed):

    /Users/rebeccacarlson/opt/miniconda3/bin/python \
        viewer/tests/verify_feature_tabs.py http://localhost:3005/EGFR
"""

import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3005/EGFR"

# category -> (expected tab number, expected chip substrings).
# The substrings are STATIC chip labels (present regardless of the
# gene's data values), scoped to the category's chip row.
EXPECT = {
    "biology": (
        "03",
        ["known ligand", "co-receptor", "restricted membrane subdomain"],
    ),
    "expression": (
        "04",
        ["level", "breadth", "Overexpression precedent"],
    ),
    "risks": (
        "05",
        [
            "shed form",
            "secreted form",
            "low endogenous expression",
            "epitope masking",
        ],
    ),
}


def main() -> int:
    failures: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        page_errors: list[str] = []
        pg.on("pageerror", lambda e: page_errors.append(str(e)))
        pg.on(
            "console",
            lambda m: page_errors.append(f"console.{m.type}: {m.text}")
            if m.type == "error"
            else None,
        )
        pg.goto(URL, wait_until="networkidle")

        # --- tab strip: the three feature tabs exist, correctly numbered,
        #     and no stale "Attributes" tab survives. ---
        tabs = pg.eval_on_selector_all(
            "a[role='tab']",
            """els => els.map(a => ({
                id: (a.getAttribute('href') || '').replace('#section-', ''),
                num: (a.querySelector("[class*='num']")?.textContent || '').trim(),
                label: (a.querySelector("[class*='label']")?.textContent || '').trim(),
            }))""",
        )
        by_id = {t["id"]: t for t in tabs}
        labels = {t["label"] for t in tabs}
        print("=== tabs ===")
        for t in tabs:
            print(f"  {t['num']:>2}  {t['label']:<32} (#section-{t['id']})")

        if "Attributes" in labels:
            failures.append("stale 'Attributes' tab still present")

        # --- per-category: chip row lives inside the matching section,
        #     carries the expected static chip labels. ---
        for cat, (want_num, want_chips) in EXPECT.items():
            tab = by_id.get(cat)
            if tab is None:
                failures.append(f"[{cat}] no tab with href #section-{cat}")
            elif tab["num"] != want_num:
                failures.append(
                    f"[{cat}] tab numbered {tab['num']!r}, expected {want_num!r}"
                )

            # The chip row must be a descendant of its own section.
            chip_text = pg.evaluate(
                """(cat) => {
                    const sec = document.querySelector(
                        `section[data-section-id="${cat}"]`);
                    if (!sec) return {found: false, inSection: false, text: ''};
                    const row = sec.querySelector(
                        `ul[data-feature-chips="${cat}"]`);
                    // also confirm there's no copy of this chip row OUTSIDE
                    // the section (e.g. left behind in Summary metrics).
                    const all = document.querySelectorAll(
                        `ul[data-feature-chips="${cat}"]`);
                    return {
                        found: !!row,
                        inSection: !!row,
                        count: all.length,
                        text: row ? row.innerText : '',
                    };
                }""",
                cat,
            )
            if not chip_text["found"]:
                failures.append(
                    f"[{cat}] no ul[data-feature-chips={cat}] inside its section"
                )
            else:
                if chip_text["count"] != 1:
                    failures.append(
                        f"[{cat}] expected exactly 1 chip row, found "
                        f"{chip_text['count']}"
                    )
                for sub in want_chips:
                    if sub.lower() not in chip_text["text"].lower():
                        failures.append(
                            f"[{cat}] chip row missing {sub!r} "
                            f"(got: {chip_text['text']!r})"
                        )

        # --- the deterministic "Summary metrics" (metrics) section must
        #     no longer carry ANY feature-chip rows. ---
        metrics_chip_rows = pg.eval_on_selector_all(
            "section[data-section-id='metrics'] [data-feature-chips]",
            "els => els.length",
        )
        print(f"\n  feature-chip rows under metrics = {metrics_chip_rows} (expect 0)")
        if metrics_chip_rows != 0:
            failures.append(
                f"metrics section still has {metrics_chip_rows} feature-chip rows"
            )

        if page_errors:
            failures.append(f"page errors: {page_errors}")

        b.close()

    print("\n=== verdict ===")
    if failures:
        for f in failures:
            print("  FAIL:", f)
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
