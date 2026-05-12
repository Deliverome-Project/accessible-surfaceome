"""Gold-standard resolver-collision audit.

For every gene_symbol with a non-null verdict under
``run_id=genome_full_sonnet_ncbi_v1`` in D1's ``triage_run`` table,
query UniProt with ``size=25`` and compare what the OLD resolver
(``_uniprot_search_by_symbol`` with ``size=1``, no primary-name
preference) vs the NEW resolver (prefer entries where the queried
symbol is the primary gene name) would return. Any disagreement is
a true contamination — the cell was answered against the wrong
protein during the genome-wide sweep.

Output: ``data/analysis/resolver_definitive_audit.tsv`` with one
row per collision: ``gene_symbol, old_uniprot, old_primary_name,
new_uniprot``. Feed this TSV into
``scripts/fix_resolver_collisions.py`` to do the targeted re-run.

Parallelism: ThreadPoolExecutor with 8 workers. UniProt rate-limits
unauthenticated callers around ~25 req/s; 8 workers + the existing
``RateLimiter`` saturates the budget without 429s. Full sweep takes
~15-30 min depending on cache state.

This is a read-only audit — no D1 mutations, no agent invocations.
"""
from __future__ import annotations

import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import _TTL, _entry_primary_symbol

load_env()

with D1Client() as d1:
    rows = d1.query(
        "SELECT DISTINCT gene_symbol FROM triage_run "
        "WHERE run_id = ? AND predicted_verdict IS NOT NULL;",
        ["genome_full_sonnet_ncbi_v1"],
    )
symbols = sorted({r["gene_symbol"] for r in rows})
print(f"Auditing {len(symbols):,} unique gene_symbols (parallel, 8 workers)", flush=True)

http = open_default_client()  # CachedHTTP is thread-safe (sqlite cache + thread-safe limiter)
print_lock = threading.Lock()
done = [0]
diffs: list[dict[str, str]] = []
no_result: list[str] = []
errors: list[tuple[str, str]] = []
start = time.time()


def check(sym: str) -> tuple[str, str, dict[str, str] | None]:
    """Return (kind, sym, payload). kind ∈ {'diff','same','no_result','error'}."""
    try:
        payload = http.get_json(
            "https://rest.uniprot.org/uniprotkb/search",
            source="uniprot",
            ttl_days=_TTL["uniprot"],
            params={
                "query": f"gene_exact:{sym} AND organism_id:9606 AND reviewed:true",
                "fields": "accession,gene_names",
                "format": "json",
                "size": "25",
            },
        )
    except Exception as e:
        return ("error", sym, {"msg": str(e)[:80]})
    results = (payload or {}).get("results") or []
    if not results:
        return ("no_result", sym, None)
    old_pick = results[0]["primaryAccession"]
    target = sym.upper()
    new_pick: str | None = None
    for entry in results:
        primary = (_entry_primary_symbol(entry) or "").upper()
        if primary == target:
            new_pick = entry["primaryAccession"]
            break
    if new_pick is None:
        new_pick = old_pick
    if new_pick != old_pick:
        old_primary = (_entry_primary_symbol(results[0]) or "?").upper()
        return ("diff", sym, {
            "gene_symbol": sym,
            "old_uniprot": old_pick,
            "old_primary_name": old_primary,
            "new_uniprot": new_pick,
        })
    return ("same", sym, None)


with ThreadPoolExecutor(max_workers=8) as ex:
    futures = {ex.submit(check, sym): sym for sym in symbols}
    for fut in as_completed(futures):
        kind, sym, payload = fut.result()
        if kind == "diff":
            assert payload is not None
            diffs.append(payload)
        elif kind == "no_result":
            no_result.append(sym)
        elif kind == "error":
            assert payload is not None
            errors.append((sym, payload["msg"]))
        with print_lock:
            done[0] += 1
            if done[0] % 1000 == 0:
                elapsed = time.time() - start
                rate = done[0] / elapsed if elapsed > 0 else 0
                eta = (len(symbols) - done[0]) / rate if rate > 0 else 0
                print(
                    f"  [{done[0]:>6}/{len(symbols)}]  diffs={len(diffs)}  "
                    f"no_result={len(no_result)}  errors={len(errors)}  "
                    f"rate={rate:.0f}/s  eta={eta:.0f}s",
                    flush=True,
                )

print()
print(f"Audited:    {len(symbols):,}")
print(f"Diffs:      {len(diffs):,}  ← old vs new resolver disagree")
print(f"No result:  {len(no_result):,}  ← UniProt has no entry; same as before")
print(f"Errors:     {len(errors):,}")

out = REPO_ROOT / "data/analysis/resolver_definitive_audit.tsv"
if diffs:
    diffs.sort(key=lambda d: d["gene_symbol"])
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(diffs[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(diffs)
    print(f"Wrote {out.relative_to(REPO_ROOT)}")

if errors:
    print()
    print("Errors (first 10):")
    for sym, msg in errors[:10]:
        print(f"  {sym}: {msg}")
