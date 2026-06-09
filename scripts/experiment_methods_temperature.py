#!/usr/bin/env python
"""Temperature-sensitivity experiment for the methods builder.

Loads a gene's existing A1 claim ledger from D1 intermediates, then
re-calls `build_methods` N times at temperature=1.0 (default) and
N times at temperature=0.0, using the SAME inputs each time. Reports
the variance in `accessibility_relevance` classifications across runs.

This is the empirical test before flipping the methods builder to
temperature=0 globally — does temp=0 actually stabilize the output?

Usage:
    uv run python scripts/experiment_methods_temperature.py TGOLN2

Cost: ~$0.05 per methods-builder call × 6 calls = ~$0.30 per gene.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders.methods import build_methods
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import EvidenceClaim, IdentifierBundle


def _load_intermediates(gene_symbol: str) -> dict[str, Any]:
    """Pull the most-recent intermediates blob for a gene."""
    with D1Client(D1Config.from_env()) as c:
        rows = c.query(
            "SELECT intermediates_json FROM agent_run_intermediates "
            "WHERE gene_symbol = ? ORDER BY created_at DESC LIMIT 1",
            [gene_symbol],
        )
    if not rows:
        raise SystemExit(f"No intermediates row for {gene_symbol}")
    return json.loads(rows[0]["intermediates_json"])


def _patch_messages_create_with_temperature(
    client: Anthropic, temperature: float
) -> None:
    """Monkey-patch client.messages.create to inject a temperature param.

    Builders today don't expose a temperature kwarg; this is a one-off
    experiment patch so we don't have to plumb the kwarg through
    `build_methods` → `call_builder` → `messages.create` just to A/B
    the setting. Restored by re-creating the client.
    """
    original = client.messages.create

    def patched(**kwargs: Any) -> Any:
        kwargs.setdefault("temperature", temperature)
        return original(**kwargs)

    client.messages.create = patched  # type: ignore[assignment]


def _summarize_methods(methods: list[Any]) -> tuple[Counter, list[tuple[str, str]]]:
    """Tally accessibility_relevance + return (cite -> relevance) pairs."""
    rel = Counter(m.accessibility_relevance for m in methods)
    cite_relevance: list[tuple[str, str]] = []
    for m in methods:
        for cite in (m.cited_evidence_ids or []):
            cite_relevance.append((cite, m.accessibility_relevance))
    return rel, sorted(cite_relevance)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol (e.g. TGOLN2)")
    parser.add_argument("--n", type=int, default=3, help="Reps per condition")
    args = parser.parse_args()

    load_env()
    blob = _load_intermediates(args.gene)

    claims = [
        EvidenceClaim.model_validate(c)
        for c in blob["plan_trim_select"]["a1"]["claims"]
    ]
    bundle_dict = blob.get("bundle")
    bundle = IdentifierBundle.model_validate(bundle_dict) if bundle_dict else None
    if bundle is None:
        print("WARNING: no bundle in intermediates; passing None")

    print(f"=== {args.gene}: {len(claims)} A1 claims loaded ===\n")

    for temperature in (1.0, 0.0):
        print(f"\n### temperature = {temperature} ({args.n} reps) ###\n")
        rep_outputs = []
        for rep in range(args.n):
            client = get_client()
            _patch_messages_create_with_temperature(client, temperature)
            usage: list[UsageRecord] = []
            methods = build_methods(
                claims=claims,
                client=client,
                usage_sink=usage,
                context={"gene": args.gene, "bundle": bundle},
            )
            rel, cites = _summarize_methods(methods)
            rep_outputs.append((rel, cites))
            print(
                f"  rep {rep + 1}: "
                f"n_methods={len(methods)}  "
                f"breakdown={dict(rel)}  "
                f"cost=${sum(u.cost_usd for u in usage):.3f}"
            )

        # Variance check across reps
        breakdowns = [tuple(sorted(r.items())) for r, _ in rep_outputs]
        all_same = len(set(breakdowns)) == 1
        print(
            f"  → reps agree on breakdown? {'✓ YES' if all_same else '✗ NO (stochastic)'}"
        )

        if not all_same:
            # Show which cite-relevance pairs differed
            cite_sets = [set(c) for _, c in rep_outputs]
            all_pairs = set().union(*cite_sets)
            print("  cite-relevance pairs where reps disagree:")
            for pair in sorted(all_pairs):
                present_in = [1 if pair in cs else 0 for cs in cite_sets]
                if 0 < sum(present_in) < len(cite_sets):
                    print(f"    {pair}: rep-presence={present_in}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
