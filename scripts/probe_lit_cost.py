"""Meter the real per-gene cost of the internalization LITERATURE pass.

Wraps ``client.messages.create`` (the single primitive every stage funnels
through via ``messages_create_with_backoff``) to tally token usage per model,
runs ``annotate_literature`` on a representative gene slice WITHOUT persisting or
publishing (pure measurement, nothing touches D1), and projects the full-cohort
cost. Reuses the repo pricing table (``agents/_support/pricing.py``) + adds the
web_search per-request surcharge the token table doesn't cover.

    uv run python scripts/probe_lit_cost.py                 # 1 heavy anchor + 4 random cohort genes
    uv run python scripts/probe_lit_cost.py --genes EGFR TFRC NECTIN4
    uv run python scripts/probe_lit_cost.py --n-random 6 --seed 7
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from collections import defaultdict

from accessible_surfaceome.agents._support.pricing import (
    PRICING,
    UsageRecord,
    cost_for_usage,
)
from accessible_surfaceome.env import load_env

# web_search_20250305 billing: $10 per 1,000 searches = $0.01 / request. Not in
# the token pricing table (it's a server-tool surcharge), so add it explicitly.
WEB_SEARCH_USD_PER_REQUEST = 0.01
COHORT_SIZE = 3357  # genes with a seq record (the lit sweep cohort)
_DATED = re.compile(r"-\d{8}$")


def _price_key(model: str) -> str:
    """Normalize an SDK model id to a PRICING key (strip a trailing -YYYYMMDD)."""
    m = _DATED.sub("", model)
    return m if m in PRICING else model


def main(argv: list[str] | None = None) -> int:
    load_env()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--genes",
        nargs="+",
        default=None,
        help="Explicit gene list (overrides sampling).",
    )
    p.add_argument(
        "--n-random",
        type=int,
        default=4,
        help="Random cohort genes to sample (default 4).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--anchor", default="EGFR", help="Known-heavy gene to anchor the upper bound."
    )
    args = p.parse_args(argv)

    from accessible_surfaceome.agents._support.client import get_client
    from accessible_surfaceome.agents.internalization.literature_runner import (
        annotate_literature,
    )
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.tools._shared.http import open_default_client

    # Choose genes: explicit, else anchor + random sample of the seq cohort.
    if args.genes:
        genes = [g.upper() for g in args.genes]
    else:
        with D1Client.public() as d1:
            rows = d1.query(
                "SELECT gene_symbol FROM surface_internalization WHERE schema_version='0.3.0';",
                [],
            )
        cohort = sorted({r["gene_symbol"] for r in rows if r.get("gene_symbol")})
        rng = random.Random(args.seed)
        sample = rng.sample([g for g in cohort if g != args.anchor], args.n_random)
        genes = [args.anchor, *sample]

    client = get_client()
    http = open_default_client()

    # --- the meter: wrap client.messages.create, tally per-model usage ---
    # tokens[model] = [input, output, cache_write, cache_read]; web[model] = requests
    tokens: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    web: dict[str, int] = defaultdict(int)
    orig_create = client.messages.create

    def metered_create(*a, **k):
        resp = orig_create(*a, **k)
        model = k.get("model") or getattr(resp, "model", "?")
        u = getattr(resp, "usage", None)
        if u is not None:
            t = tokens[model]
            t[0] += getattr(u, "input_tokens", 0) or 0
            t[1] += getattr(u, "output_tokens", 0) or 0
            t[2] += getattr(u, "cache_creation_input_tokens", 0) or 0
            t[3] += getattr(u, "cache_read_input_tokens", 0) or 0
            stu = getattr(u, "server_tool_use", None)
            web[model] += getattr(stu, "web_search_requests", 0) or 0 if stu else 0
        return resp

    client.messages.create = metered_create  # type: ignore[method-assign]

    def snapshot() -> tuple[dict[str, list[int]], dict[str, int]]:
        return ({m: list(v) for m, v in tokens.items()}, dict(web))

    def cost_between(a, b) -> float:
        (ta, wa), (tb, wb) = a, b
        total = 0.0
        for m, tb_v in tb.items():
            ta_v = ta.get(m, [0, 0, 0, 0])
            delta = [tb_v[i] - ta_v[i] for i in range(4)]
            if any(delta):
                rec = UsageRecord(
                    input_tokens=delta[0],
                    output_tokens=delta[1],
                    cache_creation_input_tokens=delta[2],
                    cache_read_input_tokens=delta[3],
                )
                total += cost_for_usage(rec, _price_key(m))
        for m, wv in wb.items():
            total += (wv - wa.get(m, 0)) * WEB_SEARCH_USD_PER_REQUEST
        return total

    print(
        f"metering {len(genes)} genes (serial, persist=False, no D1 write): {', '.join(genes)}\n"
    )
    per_gene: list[tuple[str, float, float, str, int]] = []
    for i, g in enumerate(genes, 1):
        before = snapshot()
        t0 = time.monotonic()
        try:
            rec = annotate_literature(
                g,
                client=client,
                http=http,
                use_web_search=True,
                persist=False,
                model_priors=[],
            )
            grade = rec.literature.overall_grade if rec.literature else "?"
            fetched = rec.literature.n_papers_fetched if rec.literature else 0
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(genes)}] {g}: FAILED {str(exc)[:120]}")
            continue
        c = cost_between(before, snapshot())
        dt = time.monotonic() - t0
        per_gene.append((g, c, dt, grade, fetched))
        print(
            f"  [{i}/{len(genes)}] {g:10} ${c:5.3f}  {dt:5.0f}s  lit={grade:9} fetched={fetched}"
        )

    if not per_gene:
        print("no genes measured")
        return 1

    costs = [c for _, c, _, _, _ in per_gene]
    costs_sorted = sorted(costs)
    n = len(costs_sorted)
    median = (
        costs_sorted[n // 2]
        if n % 2
        else (costs_sorted[n // 2 - 1] + costs_sorted[n // 2]) / 2
    )
    mean = sum(costs) / n
    anchor_cost = next(
        (c for gname, c, *_ in per_gene if gname == args.anchor.upper()), None
    )
    # typical = mean of the non-anchor (random) genes when we sampled
    typical_pool = (
        [c for gname, c, *_ in per_gene if gname != args.anchor.upper()]
        if not args.genes
        else costs
    )
    typical = sum(typical_pool) / len(typical_pool) if typical_pool else mean

    print("\n=== per-gene cost distribution ===")
    print(
        f"  min ${min(costs):.3f} | median ${median:.3f} | mean ${mean:.3f} | max ${max(costs):.3f}"
    )
    if anchor_cost is not None:
        print(f"  heavy anchor {args.anchor}: ${anchor_cost:.3f}")
    print(f"  typical (random-sample mean): ${typical:.3f}/gene")
    print("\n=== full-cohort projection ===")
    print(
        f"  {COHORT_SIZE} genes × typical ${typical:.3f}  ≈  ${typical * COHORT_SIZE:,.0f}"
    )
    print(
        f"  {COHORT_SIZE} genes × median  ${median:.3f}  ≈  ${median * COHORT_SIZE:,.0f}"
    )
    if anchor_cost is not None:
        print(
            f"  (upper bound if every gene ran as heavy as {args.anchor}: ${anchor_cost * COHORT_SIZE:,.0f})"
        )
    # wall-clock projection at a given concurrency
    mean_dt = sum(dt for _, _, dt, _, _ in per_gene) / n
    for conc in (12, 24, 40):
        hrs = mean_dt * COHORT_SIZE / conc / 3600
        print(
            f"  wall-clock @ concurrency {conc}: ~{hrs:.1f} h  (mean {mean_dt:.0f}s/gene)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
