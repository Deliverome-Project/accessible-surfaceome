"""Resolver-collision audit v2 — mimic the OLD resolver query exactly.

The v1 audit (scripts/audit_resolver_collisions.py) detected
contamination by running ``size=25, fields=accession,gene_names``
twice — once to compute the "old" pick (results[0]) and once to
compute the "new" pick (first primary-name match). This collapses
any cases where UniProt's result ordering differs between the OLD
resolver's exact query (``size=1, fields=accession``) and the
NEW resolver's query.

RGR was missed by v1 for exactly this reason:

  OLD query (size=1, fields=accession)        → Q8IZJ4 (RGL4)
  NEW query (size=25, fields=accession,gene_names) results[0] → P47804 (RGR)
  NEW query first-primary-match                → P47804 (RGR)

So v1 saw "results[0] = P47804 = first-primary-match" → considered
RGR clean. But the genome-wide sweep used the OLD query and got
RGL4. Fix: run the OLD query and the NEW resolver logic
independently for every gene_symbol; compare what the runner WOULD
have returned vs what it now returns.

Output: ``data/analysis/resolver_definitive_audit_v2.tsv``.
Same shape as v1: gene_symbol, old_uniprot, old_primary_name, new_uniprot.
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


def _old_resolver_pick(sym: str, *, http) -> str | None:
    """Run the OLD resolver's exact query (size=1, fields=accession only)."""
    payload = http.get_json(
        "https://rest.uniprot.org/uniprotkb/search",
        source="uniprot",
        ttl_days=_TTL["uniprot"],
        params={
            "query": f"gene_exact:{sym} AND organism_id:9606 AND reviewed:true",
            "fields": "accession",
            "format": "json",
            "size": "1",
        },
    )
    results = (payload or {}).get("results") or []
    return results[0]["primaryAccession"] if results else None


def _new_resolver_pick(sym: str, *, http) -> tuple[str | None, str]:
    """Run the NEW resolver query and apply the prefer-primary logic.

    Returns (accession, primary_name_of_old_pick). The second element is
    only meaningful when the two resolvers disagree — it tells us which
    wrong protein the OLD resolver was feeding the agent.
    """
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
    results = (payload or {}).get("results") or []
    if not results:
        return None, "?"
    target = sym.upper()
    new_pick: str | None = None
    primary_of_first = (_entry_primary_symbol(results[0]) or "?").upper()
    for entry in results:
        if (_entry_primary_symbol(entry) or "").upper() == target:
            new_pick = entry["primaryAccession"]
            break
    if new_pick is None:
        # No primary-name match → new resolver falls back to results[0]
        # of the size=25 query (same as v1 audit).
        new_pick = results[0]["primaryAccession"]
    return new_pick, primary_of_first


with D1Client() as d1:
    rows = d1.query(
        "SELECT DISTINCT gene_symbol FROM triage_run "
        "WHERE run_id = ? AND predicted_verdict IS NOT NULL;",
        ["genome_full_sonnet_ncbi_v1"],
    )
symbols = sorted({r["gene_symbol"] for r in rows})
print(f"Auditing v2: {len(symbols):,} unique gene_symbols (parallel, 8 workers)", flush=True)

http = open_default_client()
print_lock = threading.Lock()
done = [0]
diffs: list[dict[str, str]] = []
no_result: list[str] = []
errors: list[tuple[str, str]] = []
start = time.time()


def check(sym: str) -> tuple[str, str, dict[str, str] | None]:
    try:
        old_pick = _old_resolver_pick(sym, http=http)
        new_pick, old_primary_name = _new_resolver_pick(sym, http=http)
    except Exception as e:
        return ("error", sym, {"msg": str(e)[:80]})
    if old_pick is None:
        return ("no_result", sym, None)
    if new_pick == old_pick:
        return ("same", sym, None)
    return ("diff", sym, {
        "gene_symbol": sym,
        "old_uniprot": old_pick,
        "old_primary_name": old_primary_name,
        "new_uniprot": new_pick or "",
    })


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
print(f"No result:  {len(no_result):,}")
print(f"Errors:     {len(errors):,}")

out = REPO_ROOT / "data/analysis/resolver_definitive_audit_v2.tsv"
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
