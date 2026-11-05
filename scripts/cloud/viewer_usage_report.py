"""Report which pages and controls viewer visitors click most.

Reads the anonymous click events the viewer beacons to the Worker's
``POST /v1/events`` (Workers Analytics Engine dataset
``surfaceome_viewer_events``; see ``handleUsageEvent`` in
``cloudflare/workers/surfaceome_api/src/index.js``). A click row is page kind,
gene, element kind (link / external / button) and the control's label, with
no visitor identifier. A ``pageview`` row carries a visitor hash in place of
the label, from a salt that changes every UTC day, so distinct hashes give
daily unique visitors and nothing longer-lived: a person who comes back
tomorrow counts again, so don't add days up into a "monthly uniques".

Analytics Engine samples at high volume; ``SUM(_sample_interval)`` turns
sampled rows back into an estimated click count. It keeps 3 months of data.

Needs ``CLOUDFLARE_ACCOUNT_ID`` and a ``CLOUDFLARE_API_TOKEN`` with
**Account → Account Analytics → Read**.

Usage::

    uv run python scripts/cloud/viewer_usage_report.py              # last 30 days
    uv run python scripts/cloud/viewer_usage_report.py --days 7 --top 40
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from accessible_surfaceome.env import load_env

DATASET = "surfaceome_viewer_events"
# blob1 = page kind, blob2 = gene, blob3 = element kind, blob4 = label.
CLICKS = "blob3 != 'pageview'"
QUERIES = {
    "Daily unique visitors": (
        "SELECT toDate(timestamp) AS day, COUNT(DISTINCT blob4) AS unique_visitors, "
        "SUM(_sample_interval) AS page_views "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND blob3 = 'pageview' "
        "GROUP BY day ORDER BY day"
    ),
    "Clicks per day": (
        "SELECT toDate(timestamp) AS day, SUM(_sample_interval) AS clicks "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND " + CLICKS + " "
        "GROUP BY day ORDER BY day"
    ),
    "Clicks by page": (
        "SELECT blob1 AS page, SUM(_sample_interval) AS clicks "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND " + CLICKS + " "
        "GROUP BY page ORDER BY clicks DESC LIMIT {top}"
    ),
    "Top controls": (
        "SELECT blob1 AS page, blob3 AS kind, blob4 AS label, SUM(_sample_interval) AS clicks "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND " + CLICKS + " "
        "GROUP BY page, kind, label ORDER BY clicks DESC LIMIT {top}"
    ),
    # Catalog filters (named `Preset: …` / `Filter: …` in the viewer) record
    # the click's direction, so "→ on" counts a filter being applied. Labels
    # from before 2026-11-05 carry no direction and don't appear here.
    "Filters turned on": (
        "SELECT blob4 AS filter, SUM(_sample_interval) AS times_on "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND " + CLICKS + " "
        "AND (blob4 LIKE 'Filter:% → on' OR blob4 LIKE 'Preset:% → on') "
        "GROUP BY filter ORDER BY times_on DESC LIMIT {top}"
    ),
    "Genes with the most clicks": (
        "SELECT blob2 AS gene, SUM(_sample_interval) AS clicks "
        "FROM {ds} WHERE timestamp > NOW() - INTERVAL '{days}' DAY AND blob2 != '' AND "
        + CLICKS
        + " "
        "GROUP BY gene ORDER BY clicks DESC LIMIT {top}"
    ),
}


def run_sql(client: httpx.Client, account: str, sql: str) -> list[dict]:
    r = client.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/analytics_engine/sql",
        content=sql,
    )
    if r.status_code != 200:
        raise SystemExit(
            f"Analytics Engine query failed ({r.status_code}): {r.text[:500]}"
        )
    return r.json().get("data", [])


def print_table(title: str, rows: list[dict]) -> None:
    print(f"\n== {title}")
    if not rows:
        print("(no events)")
        return
    cols = list(rows[0])
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report which pages and controls viewer visitors click most."
    )
    ap.add_argument("--days", type=int, default=30, help="look-back window (max 90)")
    ap.add_argument("--top", type=int, default=25, help="rows per ranked table")
    args = ap.parse_args(argv)
    load_env()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        print(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set",
            file=sys.stderr,
        )
        return 2
    days = max(1, min(args.days, 90))
    with httpx.Client(
        headers={"Authorization": f"Bearer {token}"}, timeout=60
    ) as client:
        for title, sql in QUERIES.items():
            print_table(
                title,
                run_sql(
                    client, account, sql.format(ds=DATASET, days=days, top=args.top)
                ),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
