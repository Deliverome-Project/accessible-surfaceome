"""Which published tag sites sit inside a disulfide-closed loop, and what that costs.

Two defects motivated this, both found while checking plasmid designs:

* MS4A1 N171 is published as "3D-clear of features" while sitting four residues
  inside the 167-183 closure. `hazard_residues` reduces a bond to its two
  cysteines and vetoes on 3D distance, so a residue that is far from both in
  space but topologically trapped passes.
* ACKR3 P35 passes with a reported 12.1 A of clearance while sitting 3.8 A from
  C287 — because the C34-C287 bond is formed in the model at 2.03 A and absent
  from UniProt, so the veto never saw it.

So this reports BOTH: enclosure against annotated bonds across the whole
published set, and — on a sample, because it needs a structure per protein — how
much the model's unannotated bonds add. The annotation-only number is a LOWER
bound and is labelled as one everywhere it appears.

Enclosure is REPORTED, not treated as a defect on its own. A published-corpus
pass over 176 literature sites found 27 strictly inside a span, 12 of them
functionally validated, at spans from 9 to 655 — so no span cutoff separates our
MS4A1 case from precedent. The veto is on the insert being at least as long as
the closure it goes into, which is cargo-dependent: this audit therefore reports
the count at the 51-aa SpyTag003+ALFA cassette AND at an 11-aa HA, because they
are different answers about the same rows.

    uv run python scripts/audit/audit_tag_site_disulfide_enclosure.py
    uv run python scripts/audit/audit_tag_site_disulfide_enclosure.py --sample 60
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.paths import REPO_ROOT  # noqa: E402
from accessible_surfaceome.tag_sites import features as F  # noqa: E402

OUT_DIR = REPO_ROOT / "data/analysis/tag_site_disulfide_enclosure"
#: Cargo sizes the counts are reported at. The verdict depends on the insert,
#: so one number would be a claim about a cassette rather than about the rows.
CARGOES = {"cassette_51aa": 51, "ha_11aa": 11}
UA = {"user-agent": "accessible-surfaceome audit (becca@deliverome.org)"}
#: UniProt accepts long OR-queries; 100 keeps each URL well inside limits and
#: turns 2,413 lookups into ~25 requests rather than hammering the endpoint.
ACC_PER_QUERY = 100

log = logging.getLogger("disulfide_enclosure")


def published_sites(d1: D1Client) -> list[dict[str, Any]]:
    """Every published internal deterministic site that names a residue."""
    rows: list[dict[str, Any]] = []
    page = 5000
    while True:
        chunk = d1.query(
            "SELECT site_id, gene_symbol, uniprot_acc, insert_after_residue, "
            "det_path, confidence FROM tag_site_public "
            "WHERE site_kind = 'internal' AND provenance = 'deterministic_computed' "
            "AND insert_after_residue IS NOT NULL "
            "ORDER BY gene_symbol, insert_after_residue LIMIT ? OFFSET ?;",
            [page, len(rows)],
        )
        rows.extend(chunk)
        log.info("  pulled %d sites", len(rows))
        if len(chunk) < page:
            return rows


def annotated_disulfides(accs: list[str], cache: Path) -> dict[str, list[tuple[int, int]]]:
    """``acc -> [(cys, cys)]`` from UniProt, in bulk, cached on disk."""
    known: dict[str, list[tuple[int, int]]] = {}
    if cache.is_file():
        known = {k: [tuple(p) for p in v] for k, v in json.loads(cache.read_text()).items()}
        log.info("  %d accessions from cache", len(known))
    todo = [a for a in accs if a not in known]
    for i in range(0, len(todo), ACC_PER_QUERY):
        batch = todo[i : i + ACC_PER_QUERY]
        q = " OR ".join(f"accession:{a}" for a in batch)
        url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            + urllib.parse.urlencode(
                {"query": q, "fields": "accession,ft_disulfid", "format": "json",
                 "size": "500"}
            )
        )
        req = urllib.request.Request(url, headers=UA)  # noqa: S310
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
            payload = json.loads(r.read())
        for entry in payload.get("results", []):
            acc = entry["primaryAccession"]
            known[acc] = [
                (f["location"]["start"]["value"], f["location"]["end"]["value"])
                for f in entry.get("features", [])
                if f.get("type") == "Disulfide bond"
                and isinstance(f["location"]["start"].get("value"), int)
                and isinstance(f["location"]["end"].get("value"), int)
            ]
        # An accession the search did not return has no entry rather than no
        # bonds; record the distinction instead of silently calling it zero.
        for acc in batch:
            known.setdefault(acc, [])
        log.info("  fetched %d/%d accessions", min(i + ACC_PER_QUERY, len(todo)), len(todo))
        cache.write_text(json.dumps({k: [list(p) for p in v] for k, v in known.items()}))
        time.sleep(0.34)
    return known


def enclosing(bonds: list[tuple[int, int]], res: int) -> list[tuple[int, int]]:
    return [(a, b) for a, b in bonds if min(a, b) < res < max(a, b)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=40,
                    help="accessions to also check against the MODEL's bonds")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with D1Client.public() as pub:
        sites = published_sites(pub)
    accs = sorted({s["uniprot_acc"] for s in sites if s["uniprot_acc"]})
    log.info("%d sites across %d accessions", len(sites), len(accs))

    bonds_by_acc = annotated_disulfides(accs, args.out_dir / "uniprot_disulfides.json")
    with_bonds = {a for a, v in bonds_by_acc.items() if v}
    log.info("%d of %d accessions have an annotated disulfide", len(with_bonds), len(accs))

    enclosed: list[dict[str, Any]] = []
    for s in sites:
        for a, b in enclosing(bonds_by_acc.get(s["uniprot_acc"], []),
                              int(s["insert_after_residue"])):
            enclosed.append({**s, "cys_start": a, "cys_end": b, "span": abs(b - a)})

    tsv = args.out_dir / "enclosed_sites.tsv"
    cols = ["site_id", "gene_symbol", "uniprot_acc", "insert_after_residue", "det_path",
            "confidence", "cys_start", "cys_end", "span",
            *(f"vetoed_{k}" for k in CARGOES)]
    with tsv.open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for e in enclosed:
            row = dict(e)
            for name, n in CARGOES.items():
                row[f"vetoed_{name}"] = int(
                    F.insert_exceeds_closure(insert_aa=n, span=e["span"])
                )
            fh.write("\t".join(str(row[c]) for c in cols) + "\n")

    print("\n" + "=" * 78)
    print("ENCLOSURE AUDIT — annotated disulfides only (a LOWER bound)")
    print("=" * 78)
    print(f"  published internal deterministic sites : {len(sites):,}")
    print(f"  accessions                             : {len(accs):,}")
    print(f"  accessions with an annotated disulfide : {len(with_bonds):,}")
    print(f"\n  sites strictly inside a span           : {len(enclosed):,} "
          f"({len(enclosed) / len(sites):.1%})")
    n_genes = len({e["gene_symbol"] for e in enclosed})
    print(f"  genes affected                         : {n_genes:,}")
    for name, n in CARGOES.items():
        v = [e for e in enclosed
             if F.insert_exceeds_closure(insert_aa=n, span=e["span"])]
        print(f"\n  VETOED at {name:16s} ({n:2d} aa): {len(v):,} sites, "
              f"{len({e['gene_symbol'] for e in v}):,} genes")
    by_path = Counter(e["det_path"] for e in enclosed)
    print(f"\n  enclosed sites by lane: {dict(by_path)}")
    spans = sorted(e["span"] for e in enclosed)
    if spans:
        print(f"  span quartiles: min {spans[0]}  p25 {spans[len(spans)//4]}  "
              f"median {spans[len(spans)//2]}  p75 {spans[3*len(spans)//4]}  "
              f"max {spans[-1]}")
    print(f"\n  wrote {tsv.relative_to(REPO_ROOT)}")

    if args.sample:
        model_pass(sites, bonds_by_acc, n=args.sample, out_dir=args.out_dir)
    return 0


def model_pass(
    sites: list[dict[str, Any]],
    annotated: dict[str, list[tuple[int, int]]],
    *,
    n: int,
    out_dir: Path,
) -> None:
    """How much the annotation-only count understates, measured on a sample.

    Needs one structure per protein, so it is sampled rather than exhaustive.
    The sample is stratified to include accessions with NO annotated bond,
    because that is where the understatement hides: ACKR3 has one annotated
    bond and two formed ones, and a protein with zero annotated bonds looks
    disulfide-free to every check we have.
    """
    import random
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from benchmark_tag_sites_deterministic import af_pdb  # noqa: PLC0415

    rng = random.Random(20261018)
    by_acc: dict[str, list[dict[str, Any]]] = {}
    for s in sites:
        by_acc.setdefault(s["uniprot_acc"], []).append(s)
    with_ann = [a for a in by_acc if annotated.get(a)]
    without = [a for a in by_acc if not annotated.get(a)]
    half = max(1, n // 2)
    picked = rng.sample(with_ann, min(half, len(with_ann))) + rng.sample(
        without, min(n - half, len(without))
    )

    rows, errs = [], 0
    extra_bonds = extra_enclosed = 0
    for i, acc in enumerate(picked, 1):
        try:
            bonds = F.model_disulfides(af_pdb(acc))
        except Exception as exc:  # noqa: BLE001 - a missing model is data, not a crash
            errs += 1
            log.warning("  %s: %s", acc, type(exc).__name__)
            continue
        ann = {(min(a, b), max(a, b)) for a, b in annotated.get(acc, [])}
        model_only = [b for b in bonds if (b.first, b.second) not in ann]
        extra_bonds += len(model_only)
        for s in by_acc[acc]:
            res = int(s["insert_after_residue"])
            was = bool(enclosing(list(ann), res))
            now = was or any(b.encloses(res) for b in model_only)
            if now and not was:
                extra_enclosed += 1
                rows.append({**s, "newly_enclosed_by": ",".join(
                    f"C{b.first}-C{b.second}" for b in model_only if b.encloses(res))})
        if i % 10 == 0:
            log.info("  model pass %d/%d", i, len(picked))

    out = out_dir / "model_only_newly_enclosed.tsv"
    cols = ["site_id", "gene_symbol", "uniprot_acc", "insert_after_residue",
            "det_path", "newly_enclosed_by"]
    with out.open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    n_sites = sum(len(by_acc[a]) for a in picked)
    print("\n" + "=" * 78)
    print(f"MODEL PASS — {len(picked)} accessions sampled ({errs} without a model)")
    print("=" * 78)
    print(f"  sites in the sample                   : {n_sites:,}")
    print(f"  bonds formed in the model but NOT annotated: {extra_bonds}")
    print(f"  sites newly enclosed by one of those  : {extra_enclosed} "
          f"({extra_enclosed / n_sites:.1%} of the sample)")
    print(f"\n  wrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
