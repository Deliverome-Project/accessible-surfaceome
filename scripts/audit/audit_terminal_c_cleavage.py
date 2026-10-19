"""Every ``terminal_c`` row in ``tag_site_public``, against the C-terminal
cleavage annotations — does the lane propose a tag at a residue maturation
removes?

The terminal lane decides from the DeepTMHMM string alone: the chain ends
extracellular, so it proposes a C-terminal tag. For a GPI-anchored protein the
precursor C-terminus is removed at the omega site and replaced by the anchor, so
that position is not on the mature protein at all. The string cannot see the
difference.

Reports GPI and non-GPI separately, because the fix is only defensible for the
population it was measured on. The NetGPI column is CORROBORATION, deliberately
not a source: its omega sites come in whichever form was submitted rather than
the canonical frame these records are numbered against (GPC5 reads 27 of 572),
and resolving that is the sha256-of-sequence problem rather than a column read.

``--gpi-set`` points at ``gpi_set.tsv`` from the library-design work (159 genes,
``deliverome-analysis``, commit d541e6a6). Without it the NetGPI columns are
blank and the UniProt-only verdict still stands on its own.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tag_sites import features as F
from accessible_surfaceome.tools._shared.http import open_default_client

log = logging.getLogger("audit_terminal_c")

OUT = Path("data/analysis/tag_site_gpi_terminal/terminal_c_cleavage.tsv")
COLS = [
    "gene_symbol", "uniprot_acc", "site_id", "provenance", "insert_after_residue",
    "uniprot_propeptide", "uniprot_gpi_omega", "cleaved_span", "refused",
    "in_netgpi", "netgpi_omega", "netgpi_likelihood",
]


def load_gpi(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open() as fh:
        return {
            r["gene_symbol"]: r
            for r in csv.DictReader(fh, delimiter="\t")
            if r.get("gpi_anchored") == "1"
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gpi-set", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    gpi = load_gpi(args.gpi_set)
    log.info("NetGPI anchored genes: %d", len(gpi))

    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(
            "SELECT gene_symbol, uniprot_acc, site_id, provenance, insert_after_residue "
            "FROM tag_site_public WHERE site_kind='terminal_c' ORDER BY gene_symbol;", []
        )
    if args.limit:
        rows = rows[: args.limit]
    log.info("terminal_c rows: %d across %d genes",
             len(rows), len({r["gene_symbol"] for r in rows}))

    out: list[dict[str, object]] = []
    with open_default_client() as http:
        for i, r in enumerate(rows, 1):
            acc = r["uniprot_acc"]
            after = r["insert_after_residue"]
            pp = om = span = None
            try:
                feats = F.fetch_uniprot_features(acc, http=http)
                # The row's residue IS the precursor length for a deterministic
                # terminal_c site; a literature row may carry None.
                length = int(after) if after else 0
                if length:
                    pp = F.c_terminal_propeptide(feats, length)
                    span = F.cleaved_c_terminus(feats, length)
                om = F.gpi_omega_site(feats)
            except Exception as ex:  # noqa: BLE001 — absent means "not annotated"
                log.warning("  %s (%s): %s", r["gene_symbol"], acc, type(ex).__name__)
            g = gpi.get(r["gene_symbol"]) or {}
            out.append({
                **{k: r.get(k) for k in
                   ("gene_symbol", "uniprot_acc", "site_id", "provenance",
                    "insert_after_residue")},
                "uniprot_propeptide": f"{pp[0]}-{pp[1]}" if pp else "",
                "uniprot_gpi_omega": om or "",
                "cleaved_span": f"{span[0]}-{span[1]}" if span else "",
                "refused": 1 if span else 0,
                "in_netgpi": 1 if g else 0,
                "netgpi_omega": g.get("omega_site", ""),
                "netgpi_likelihood": g.get("best_anchored_likelihood", ""),
            })
            if i % 100 == 0:
                log.info("  ...%d/%d", i, len(rows))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t")
        w.writeheader()
        w.writerows(out)  # type: ignore[arg-type]

    det = [o for o in out if o["provenance"] == "deterministic_computed"]
    ref = [o for o in det if o["refused"]]
    gpi_ref = [o for o in ref if o["in_netgpi"]]
    gpi_rows = [o for o in det if o["in_netgpi"]]
    log.info(
        "\n=== %s ===\n"
        "  deterministic terminal_c rows              %5d\n"
        "    refused (C-terminus inside a cleaved span) %5d\n"
        "      of those, NetGPI-anchored               %5d\n"
        "      of those, NOT in the NetGPI set         %5d\n"
        "  NetGPI-anchored deterministic rows          %5d\n"
        "    not refused (UniProt silent)              %5d",
        args.out, len(det), len(ref), len(gpi_ref), len(ref) - len(gpi_ref),
        len(gpi_rows), len(gpi_rows) - len(gpi_ref),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
