"""Scan zero-site genes for clips that look like a REAL tag insertion. $0.

The "211 rescuable genes" estimate counted boosted clips — clips naming an
extracellular residue — and spot-checking four genes showed that signal is
mostly false positives (an scFv hinge, a vaccine epitope, a cleavage site in a
different protein). Four genes is not a basis for writing off 211, so this asks
the question properly and at scale.

For each gene it replays the pool from cache (no model calls) and looks for the
conjunction that a real site needs: tag-insertion LANGUAGE and a residue number
in the same clip, with the gene's own name nearby. Then it reports whether
those clips were inside the selector's menu — which separates "the model never
saw it" from "the model saw it and said no".

    uv run python scripts/probes/scan_rescuable.py --genes A,B,C
    uv run python scripts/probes/scan_rescuable.py --from-d1 --limit 40
"""

from __future__ import annotations

import argparse
import json
import logging
import re
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
    load_discovery_cache,
)
from accessible_surfaceome.agents.tag_site.runner import tag_site_relevance  # noqa: E402
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    load as load_triage_cache,
)
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    split as split_triage,
)
from accessible_surfaceome.agents.tag_site.triage_cache import (  # noqa: E402
    triage_prompt_sha,
)
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.tools._shared.http import open_default_client  # noqa: E402
from accessible_surfaceome.tools._shared.retraction_watch import (  # noqa: E402
    empty as empty_retraction,
)

log = logging.getLogger("scan")

#: Language a paper uses when it actually puts a tag INTO a protein.
_INSERT = re.compile(
    r"\b(inserted?|insertion|introduc\w+|engineered|knock(?:ed)?[- ]in|fused?|"
    r"appended|tagged)\b",
    re.I,
)
#: A tag, named. Generic enough to catch the common ones without inventing.
_TAG = re.compile(
    r"\b(HA|FLAG|3xFLAG|myc|V5|ALFA|SNAP|CLIP|Halo|GFP|EGFP|sfGFP|SEP|mCherry|"
    r"BBS|Strep[- ]?tag|His6|6xHis|epitope tag|spaghetti monster)\b"
)
#: A residue position, after/at a number.
_RES = re.compile(r"\b(?:residues?|position|after|aa\.?)\s*\d{1,4}\b", re.I)


def zero_site_genes(limit: int) -> list[str]:
    with D1Client() as d1:
        rows = d1.query(
            "SELECT gene_symbol FROM tag_site_run "
            "WHERE run_id='tag_site_library_v1' AND n_sites=0 AND n_clips >= 200 "
            "ORDER BY n_clips DESC LIMIT ?;",
            [limit],
        )
    return [r["gene_symbol"] for r in rows]


def scan(gene: str, http, show: int = 2) -> dict | None:
    import regenerate_tag_site_lit as G

    try:
        rec = G.fetch_record(gene)
        acc, seq, topo = G.extract_from_record(rec)
    except Exception as exc:  # noqa: BLE001
        log.warning("%s: no record (%s)", gene, str(exc)[:60])
        return None
    papers = load_discovery_cache(gene, cache_dir=DISCOVERY_CACHE_DIR)
    _todo, reused = split_triage(
        papers, load_triage_cache(gene), prompt_sha=triage_prompt_sha()
    )
    if not reused:
        return None
    pool, _ = build_pool(
        reused,
        papers,
        http=http,
        retraction_index=empty_retraction(),
        relevance=tag_site_relevance(seq) if seq else None,
    )
    ranked = sorted(
        pool.items(), key=lambda kv: getattr(kv[1], "score", 0.0) or 0.0, reverse=True
    )
    rank = {k: i for i, (k, _) in enumerate(ranked)}

    hits = []
    for k, c in pool.items():
        q = getattr(c, "quote", "") or ""
        # All three, and the gene itself named — a tag, an insertion verb, and
        # a position. Any two of them is how the false positives got in.
        if (
            _TAG.search(q)
            and _INSERT.search(q)
            and _RES.search(q)
            and gene.upper() in q.upper()
        ):
            hits.append((rank[k], k, q))
    hits.sort()
    inside = sum(1 for r, _, _ in hits if r < _MAX_CLIP_MENU)
    return {
        "gene": gene,
        "pool": len(pool),
        "hits": len(hits),
        "in_menu": inside,
        "cut": len(hits) - inside,
        "examples": [(r, q[:190]) for r, _, q in hits[:show]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--genes")
    ap.add_argument("--from-d1", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    genes = (
        args.genes.split(",")
        if args.genes
        else zero_site_genes(args.limit)
        if args.from_d1
        else []
    )
    if not genes:
        log.error("pass --genes or --from-d1")
        return 2

    http = open_default_client()
    results = []
    for i, g in enumerate(genes, 1):
        r = scan(g, http)
        if not r:
            continue
        results.append(r)
        flag = "  <-- CANDIDATE" if r["hits"] else ""
        log.info(
            "[%2d/%d] %-12s pool=%-5d tag+insert+residue clips=%-3d in_menu=%-3d cut=%-3d%s",
            i,
            len(genes),
            g,
            r["pool"],
            r["hits"],
            r["in_menu"],
            r["cut"],
            flag,
        )
        for rk, q in r["examples"]:
            log.info("            rank %-5d %s", rk, q)

    cand = [r for r in results if r["hits"]]
    log.info("")
    log.info(
        "=== %d/%d genes have >=1 tag+insertion+residue clip naming the gene ===",
        len(cand),
        len(results),
    )
    log.info(
        "    of those, %d had such a clip CUT before the selector saw it",
        sum(1 for r in cand if r["cut"]),
    )
    print(json.dumps(results, indent=2)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
