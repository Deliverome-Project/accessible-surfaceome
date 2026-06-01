"""Apply the Surfaceome API's edge **cache rule** to the Cloudflare zone.

The public read-only Worker (``api.deliverome.org/surfaceome/*``) is
shielded from cost / availability abuse — **not** access (the data is
publish-intended) — by two layers, split by where they're cheapest to run:

* **The cache rule** (this script) — phase ``http_request_cache_settings``,
  makes the cache key **ignore the query string** for the route. This kills
  the cache-busting amplification vector: without it, ``?_=<random>`` makes
  every request a cache miss → a D1 query + Worker CPU per hit. TTLs stay
  governed by the Worker's own ``Cache-Control`` (``respect_origin``).
  Cache Rules are available on **every plan**, so this is the default.

* **Per-IP rate limiting** — handled IN THE WORKER via the native Workers
  Rate Limiting binding (``env.RATE_LIMITER.limit()``; see
  ``src/index.js`` + ``wrangler.toml``). That path is free on every plan
  and needs no zone ruleset. Cloudflare's zone-level **WAF Rate Limiting
  Rules** (the ``http_ratelimit`` phase below) are a **Pro/Business+**
  feature — so this script only touches them when you explicitly pass
  ``--only ratelimit`` on a zone that has the feature. On Free, skip it;
  the Worker limiter covers you.

The applier is **idempotent and non-destructive**: it reads the existing
entrypoint ruleset for the phase, drops only the rules it previously
created (tagged with ``MANAGED_PREFIX`` in their description), re-adds the
current managed rules, and preserves every other rule untouched.
Re-running never duplicates.

Auth: ``CLOUDFLARE_API_TOKEN`` (needs **Zone → Cache Rules → Edit** on the
deliverome.org zone — and **Zone → Rate Limiting Rules → Edit** only if you
use ``--only ratelimit`` on Pro+) + ``CLOUDFLARE_ZONE_ID`` (the
deliverome.org zone UUID).

Run::

    uv run python scripts/apply_cf_edge_rules.py            # dry-run the cache rule
    uv run python scripts/apply_cf_edge_rules.py --execute  # apply the cache rule
    uv run python scripts/apply_cf_edge_rules.py --only ratelimit --execute  # Pro+ only
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

from accessible_surfaceome.env import load_env

API_ROOT = "https://api.cloudflare.com/client/v4"

# Marker that identifies rules this script owns. Re-runs strip rules whose
# description starts with this and re-add the current set, so the script is
# idempotent without clobbering hand-authored rules in the same phase.
MANAGED_PREFIX = "[managed:surfaceome-api]"

# The route the Worker serves under (see wrangler.toml [[routes]]).
ROUTE_HOST = "api.deliverome.org"
ROUTE_PREFIX = "/surfaceome/"

# Expression matching every request under the Worker route.
ROUTE_EXPR = (
    f'(http.host eq "{ROUTE_HOST}" and '
    f'starts_with(http.request.uri.path, "{ROUTE_PREFIX}"))'
)
# The CPU-heavy endpoints: the genome-wide catalog + the TSV exports.
HEAVY_EXPR = (
    f'(http.host eq "{ROUTE_HOST}" and '
    f'(http.request.uri.path eq "/surfaceome/v1/catalog" or '
    f'ends_with(http.request.uri.path, ".tsv")))'
)

# --- thresholds (generous — bound cost, don't gate access) -----------------
# The legit viewer makes a handful of calls per page; a figure script a few
# dozen over its run. These ceilings sit far above that.
GENERAL_REQUESTS = 1200      # per IP per period on the whole route
HEAVY_REQUESTS = 120         # per IP per period on catalog + *.tsv
RATELIMIT_PERIOD = 60        # seconds
MITIGATION_TIMEOUT = 60      # seconds to keep blocking once tripped


def _cache_rules() -> list[dict]:
    """Cache-settings rules: ignore the query string in the cache key."""
    return [
        {
            "description": f"{MANAGED_PREFIX} ignore query string in cache key",
            "expression": ROUTE_EXPR,
            "action": "set_cache_settings",
            "action_parameters": {
                # Stay cacheable; let the Worker's Cache-Control set TTLs.
                "cache": True,
                "edge_ttl": {"mode": "respect_origin"},
                "browser_ttl": {"mode": "respect_origin"},
                # The crux: exclude ALL query-string params from the cache
                # key, so `?_=random` collapses onto the canonical object.
                "cache_key": {
                    "ignore_query_strings_order": True,
                    "custom_key": {"query_string": {"exclude": "*"}},
                },
            },
        },
    ]


def _ratelimit_rules() -> list[dict]:
    """WAF rate-limit rules (Pro+ only): tighter on heavy endpoints first.

    NOTE: on Free/Pro-without-WAF-rate-limiting, this phase is unavailable
    and per-IP limiting is done in the Worker instead (the native Rate
    Limiting binding). Only applied via an explicit ``--only ratelimit``.
    """
    base_rl = {
        "characteristics": ["ip.src", "cf.colo.id"],
        "period": RATELIMIT_PERIOD,
        "mitigation_timeout": MITIGATION_TIMEOUT,
    }
    return [
        {
            "description": f"{MANAGED_PREFIX} heavy-endpoint rate limit "
            "(catalog + tsv)",
            "expression": HEAVY_EXPR,
            "action": "block",
            "ratelimit": {**base_rl, "requests_per_period": HEAVY_REQUESTS},
        },
        {
            "description": f"{MANAGED_PREFIX} general route rate limit",
            "expression": ROUTE_EXPR,
            "action": "block",
            "ratelimit": {**base_rl, "requests_per_period": GENERAL_REQUESTS},
        },
    ]


PHASES = {
    "cache": ("http_request_cache_settings", _cache_rules),
    "ratelimit": ("http_ratelimit", _ratelimit_rules),
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_entrypoint_rules(
    client: httpx.Client, zone: str, phase: str, token: str
) -> list[dict]:
    """Existing rules in a phase's entrypoint ruleset, or [] if none exist."""
    resp = client.get(
        f"{API_ROOT}/zones/{zone}/rulesets/phases/{phase}/entrypoint",
        headers=_headers(token),
    )
    if resp.status_code == 404:
        return []  # no entrypoint ruleset yet for this phase
    resp.raise_for_status()
    return resp.json().get("result", {}).get("rules", []) or []


def _strip_managed(rules: list[dict]) -> list[dict]:
    """Drop rules this script owns, keeping every hand-authored rule."""
    return [
        r for r in rules if not str(r.get("description", "")).startswith(MANAGED_PREFIX)
    ]


def _put_entrypoint(
    client: httpx.Client, zone: str, phase: str, token: str, rules: list[dict]
) -> dict:
    resp = client.put(
        f"{API_ROOT}/zones/{zone}/rulesets/phases/{phase}/entrypoint",
        headers=_headers(token),
        json={"rules": rules},
    )
    if resp.status_code >= 400:
        raise SystemExit(
            f"PUT {phase} entrypoint failed ({resp.status_code}):\n"
            f"{json.dumps(resp.json(), indent=2)}"
        )
    return resp.json()


def _apply_phase(
    client: httpx.Client,
    zone: str,
    token: str,
    which: str,
    *,
    execute: bool,
) -> None:
    phase, build = PHASES[which]
    managed = build()
    existing = _get_entrypoint_rules(client, zone, phase, token)
    preserved = _strip_managed(existing)
    # Managed rules first so HEAVY (more specific) is evaluated before the
    # general route rule; hand-authored rules keep their relative order after.
    final_rules = managed + preserved

    print(f"\n=== phase {which} ({phase}) ===")
    print(
        f"  existing rules: {len(existing)} "
        f"({len(existing) - len(preserved)} managed, {len(preserved)} other)"
    )
    print(f"  applying: {len(managed)} managed + {len(preserved)} preserved")
    for r in managed:
        print(f"    + {r['description']}")

    if not execute:
        print("  --- DRY RUN — would PUT this rules array: ---")
        print(json.dumps(final_rules, indent=2))
        return

    _put_entrypoint(client, zone, phase, token, final_rules)
    print("  ✓ applied")


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="apply to the zone (default: dry-run, print payloads only)",
    )
    ap.add_argument(
        "--only",
        choices=["cache", "ratelimit"],
        default=None,
        help="apply only one phase. Default applies just the cache rule "
        "(rate limiting lives in the Worker); pass --only ratelimit to "
        "apply the Pro+ WAF rate-limit rules instead.",
    )
    args = ap.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    missing = [
        n
        for n, v in (("CLOUDFLARE_API_TOKEN", token), ("CLOUDFLARE_ZONE_ID", zone))
        if not v
    ]
    if missing:
        print(
            f"missing env: {', '.join(missing)}. Set them in .env "
            "(token needs Zone → Cache Rules + Rate Limiting Rules → Edit).",
            file=sys.stderr,
        )
        return 1

    # Default to the cache rule only — it's available on every plan and is
    # the high-leverage anti-amplification measure. Per-IP rate limiting is
    # in the Worker (native binding); the WAF rate-limit phase is Pro+ and
    # only applied on explicit --only ratelimit.
    which = [args.only] if args.only else ["cache"]
    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"{mode} — zone {zone[:8]}… · phases: {', '.join(which)}")

    with httpx.Client(timeout=30) as client:
        for w in which:
            _apply_phase(client, zone, token, w, execute=args.execute)

    if not args.execute:
        print("\nDry run only. Re-run with --execute to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
