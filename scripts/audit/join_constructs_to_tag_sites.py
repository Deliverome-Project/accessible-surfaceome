"""Join the constructs we have BUILT against the sites we have PROPOSED.

Two registries, split by artefact type, with no link in either direction: the
Reagent Inventory records what was built, `tag_site_public` records what the
pipeline proposed. That split has already cost something concrete. P-0007 is a
built-and-received SpyTag-ALFA construct at TFRC V291 — a residue THIS pipeline
proposes, and for which `tag_fit` returns "ALFA, DogTag". So our own table
recommends a different chemistry at the exact position a plasmid already sits
at, and on 2026-10-18 a review recommended dropping SpyTag003 from six
about-to-be-ordered plasmids because the SpyTag-in-loops reference table was
missing that counterexample while the plasmid sat in a freezer.

A proposed site that already has a construct is the most informative row in the
table — it is the only kind with a physical result attached — and it is
currently invisible. This makes it visible.

    uv run python scripts/audit/join_constructs_to_tag_sites.py
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.paths import REPO_ROOT  # noqa: E402

INVENTORY = REPO_ROOT / "data/tag_sites/reagent_inventory_constructs.tsv"
OUT = REPO_ROOT / "data/analysis/construct_site_join/construct_vs_proposed.tsv"

#: "loop, after 146" / "cassette after residue 32" -> 146 / 32. An explicit
#: "after N" is the only form read as a junction, because it is the only one
#: that states the convention.
_AFTER = re.compile(r"after (?:residue )?(\d+)", re.I)
#: "V291 (preceding)" -> residue 291, inserted BEFORE it. A different convention
#: from "after N", and the ambiguity is not cosmetic: under "preceding" the
#: junction is after 290, one residue off what "after 291" would mean. Reading
#: one as the other is exactly the off-by-one that moved p0033 from after-162 to
#: after-161 in this same batch.
_PRECEDING = re.compile(r"([A-Z])(\d+)\s*\(preceding\)", re.I)


def construct_residue(location: str) -> tuple[int | None, str]:
    """``(junction residue, convention)`` from a free-text tag location."""
    if m := _AFTER.search(location):
        return int(m.group(1)), "after"
    if m := _PRECEDING.search(location):
        # Reported as the NAMED residue, with the convention flagged. Not
        # silently decremented: whether the cassette lands after N-1 or after N
        # is a question for whoever built it, and guessing is how off-by-ones
        # enter a plasmid.
        return int(m.group(2)), "preceding (ambiguous: after N-1 or after N?)"
    return None, "no residue stated"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, default=INVENTORY)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with args.inventory.open(newline="") as fh:
        constructs = list(csv.DictReader(fh, delimiter="\t"))
    genes = sorted({c["gene_symbol"] for c in constructs})
    logging.info("%d constructs across %d genes", len(constructs), len(genes))

    marks = ", ".join("?" * len(genes))
    with D1Client.public() as pub:
        sites = pub.query(
            f"SELECT gene_symbol, site_id, provenance, site_kind, det_path, "
            f"insert_after_residue, residue_label, tag_type, confidence "
            f"FROM tag_site_public WHERE gene_symbol IN ({marks});",
            genes,
        )
    by_gene: dict[str, list[dict]] = {}
    for s in sites:
        by_gene.setdefault(s["gene_symbol"], []).append(s)
    logging.info("%d proposed sites across those genes", len(sites))

    rows = []
    for c in constructs:
        res, convention = construct_residue(c["tag_location"])
        gene_sites = by_gene.get(c["gene_symbol"], [])
        exact = [s for s in gene_sites if res is not None
                 and s["insert_after_residue"] == res]
        near = [s for s in gene_sites if res is not None
                and s["insert_after_residue"] is not None
                and 0 < abs(int(s["insert_after_residue"]) - res) <= 3]
        rows.append({
            "construct_id": c["construct_id"],
            "status": c["status"],
            "gene_symbol": c["gene_symbol"],
            "tag_location": c["tag_location"],
            "junction_residue": res if res is not None else "",
            "convention": convention,
            "built_tag": c["tag_fusion"],
            "match": ("exact" if exact else "within3" if near else
                      "no residue" if res is None else "none"),
            "proposed_site_id": ";".join(s["site_id"] for s in (exact or near)),
            "proposed_tag_type": ";".join(
                sorted({str(s["tag_type"]) for s in (exact or near)})),
            "proposed_det_path": ";".join(
                sorted({str(s["det_path"]) for s in (exact or near)})),
            "proposed_site_kind": ";".join(
                sorted({str(s["site_kind"]) for s in (exact or near)})),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0])
    with args.out.open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    print("\n" + "=" * 78)
    print("CONSTRUCTS vs PROPOSED SITES")
    print("=" * 78)
    for kind in ("exact", "within3", "none", "no residue"):
        hit = [r for r in rows if r["match"] == kind]
        print(f"  {kind:12s} {len(hit):3d}")
    print("\n  constructs whose junction is a site we proposed:")
    for r in rows:
        if r["match"] in ("exact", "within3"):
            # Only meaningful for an INTERNAL site. `tag_fit` deliberately
            # RESERVES SpyTag003 for termini, so a terminal SpyTag003 build
            # agrees with our logic rather than diverging from it — flagging
            # those would manufacture five disagreements that do not exist.
            internal = "internal" in r["proposed_site_kind"]
            differs = (internal and "DogTag" in r["proposed_tag_type"]
                       and "pytag" in r["built_tag"])
            print(f"    {r['construct_id']}  {r['gene_symbol']:8s} "
                  f"after {r['junction_residue']:<5} [{r['match']:7s}] "
                  f"{r['proposed_site_kind'] or '-':10s} "
                  f"built={r['built_tag'][:26]:26s} proposed={r['proposed_tag_type']}"
                  + ("   <- CHEMISTRY DIFFERS" if differs else ""))
    print("\n  NOTE: a terminal arm cannot match on residue — our terminal sites")
    print("        carry no insert_after_residue — so an N-term row below is a join")
    print("        artefact, not a disagreement about position.")
    print("\n  constructs at a residue we did NOT propose:")
    for r in rows:
        if r["match"] == "none":
            print(f"    {r['construct_id']}  {r['gene_symbol']:8s} "
                  f"after {r['junction_residue']:<5} {r['tag_location'][:50]}")
    print(f"\n  wrote {args.out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
