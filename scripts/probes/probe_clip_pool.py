"""Replay a gene's clip pool from cache — no network, no model calls, $0.

I claimed the pools "were never persisted, so a rescue needs a re-run". That is
wrong in the way that matters. The pool is not stored AS a pool, but every
input to it is: the discovery cache holds the papers, the triage cache holds
each paper's verdict, and `data/external/tool_cache.sqlite` (~4 GB, 49k rows
incl. 12.6k PMC full texts) plus `blob_cache/` hold the bodies. `build_pool` is
deterministic over those, so the exact pool a run saw can be rebuilt for free.

That is the difference between "we must re-run 211 genes to find out" and "we
can look right now".

Prints the pool, which clips named an extracellular residue, and — the question
that matters — whether those clips survived the top-``_MAX_CLIP_MENU`` cut that
decides what the selector is allowed to see.

    uv run python scripts/probes/probe_clip_pool.py ADAM17
    uv run python scripts/probes/probe_clip_pool.py CD274 --show 12
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accessible_surfaceome.agents._support.literature_clips import (  # noqa: E402
    _MAX_CLIP_MENU,
    build_pool,
)
from accessible_surfaceome.agents.tag_site.literature_discovery import (  # noqa: E402
    DISCOVERY_CACHE_DIR,
    boost_residue_clips,
    load_discovery_cache,
)
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    load as load_triage_cache,
)
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    split as split_triage,
)
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    triage_prompt_sha,
)
from accessible_surfaceome.agents.tag_site.runner import tag_site_relevance  # noqa: E402
from accessible_surfaceome.tools._shared.http import open_default_client  # noqa: E402
from accessible_surfaceome.tools._shared.retraction_watch import empty as empty_retraction  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gene")
    ap.add_argument("--show", type=int, default=8, help="boosted clips to print")
    args = ap.parse_args()

    import regenerate_tag_site_lit as G

    rec = G.fetch_record(args.gene)
    acc, seq, topo = G.extract_from_record(rec)

    papers = load_discovery_cache(args.gene, cache_dir=DISCOVERY_CACHE_DIR)
    cached = load_triage_cache(args.gene)
    todo, reused = split_triage(papers, cached, prompt_sha=triage_prompt_sha())
    print(f"{args.gene} ({acc})  len={len(seq)}")
    print(f"  papers discovered   : {len(papers)}")
    print(f"  triage verdicts      : {len(reused)} cached, {len(todo)} would need a model call")
    if todo:
        print("  -> not fully replayable from cache; showing what is")

    http = open_default_client()
    # `relevance` is NOT optional for a faithful replay: it ranks sentences
    # ahead of the per-section cap, so without it the cap keeps each section's
    # opening sentences and discards its findings — a different pool than the
    # run actually saw, which is exactly the clips a rescue question is about.
    pool, _actions = build_pool(
        reused,
        papers,
        http=http,
        retraction_index=empty_retraction(),
        relevance=tag_site_relevance(seq) if seq else None,
    )
    print(f"  CLIP POOL REBUILT    : {len(pool)} clips  (no model calls)")

    boosted = boost_residue_clips(pool, sequence=seq, topology=topo) if seq and topo else {}
    print(f"  clips naming an extracellular residue: {len(boosted)}")

    # The cut that decides what the selector is even allowed to consider.
    ranked = sorted(
        pool.items(), key=lambda kv: getattr(kv[1], "score", 0.0) or 0.0, reverse=True
    )
    menu = {k for k, _ in ranked[:_MAX_CLIP_MENU]}
    seen = sum(1 for k in boosted if k in menu)
    print()
    print(f"  menu cap (_MAX_CLIP_MENU) = {_MAX_CLIP_MENU} of {len(pool)} "
          f"({100 * _MAX_CLIP_MENU / max(len(pool), 1):.0f}% of the pool)")
    print(f"  boosted clips INSIDE the menu : {seen}/{len(boosted)}")
    print(f"  boosted clips CUT before the model ever saw them: {len(boosted) - seen}")
    print()
    for key, residues in list(boosted.items())[: args.show]:
        clip = pool[key]
        where = "in menu " if key in menu else "CUT     "
        print(f"   [{where}] {getattr(clip, 'source_id', key)} @{sorted(residues)[:6]}")
        print(f"              {(getattr(clip, 'quote', '') or '')[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
