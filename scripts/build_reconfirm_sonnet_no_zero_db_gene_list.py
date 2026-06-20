"""Build the gene list for the Sonnet-no / zero-DB re-confirm sweep.

Pulls the public catalog
(``https://api.deliverome.org/surfaceome/v1/catalog``) and filters to
genes where the canonical v2 Sonnet+ncbi sweep voted ``no``, no surface
database flagged the gene (``db == 0``), AND Sonnet's ``no``-reason is
one of the *ambiguous* buckets — the slice where a re-sample is most
likely to expose a borderline call.

Excluded by design (confidently intracellular, ~80% of the candidate
pool — re-sampling is poor ROI):
  * cytoplasmic
  * nuclear
  * mitochondrial_internal

Included (the buckets where KLK2-style misses live, plus low-volume
catch-alls so the slice has full closed-enum coverage of "ambiguous"):
  * secreted_only            — KLK2's bucket (secreted protein with
                                tissue-contextual surface display)
  * endomembrane_resident    — vesicle / ER / Golgi proteins that can
                                surface-traffic under specific states
  * inner_leaflet_anchored   — Src-family-like kinases where the lipid
                                anchor can be misread as "intracellular"
  * pmhc_only_intracellular  — pMHC-presented intracellular antigens
  * other                    — catch-all that should be re-examined
  * nuclear_envelope         — small bucket; surfacing is rare but possible

Output:
  ``data/processed/reconfirm_sonnet_no_zero_db_v1/gene_list.tsv``
  with columns the triage_runner reads (``gene_symbol``) plus context
  columns for human review (``uniprot_acc``, ``prior_reason``,
  ``n_db_votes``).

Run:
  ``uv run python scripts/build_reconfirm_sonnet_no_zero_db_gene_list.py``
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import httpx

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
SONNET_MODEL = "claude-sonnet-4-6"
AMBIGUOUS_REASONS = frozenset(
    {
        "secreted_only",
        "endomembrane_resident",
        "inner_leaflet_anchored",
        "pmhc_only_intracellular",
        "other",
        "nuclear_envelope",
    }
)

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data/processed/reconfirm_sonnet_no_zero_db_v1/gene_list.tsv"


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching catalog from {CATALOG_URL} …")
    resp = httpx.get(CATALOG_URL, timeout=60.0)
    resp.raise_for_status()
    catalog = resp.json()
    models: list[str] = catalog["models"]
    sonnet_idx = models.index(SONNET_MODEL)

    rows: list[dict[str, str | int]] = []
    for r in catalog["rows"]:
        if r.get("db", 0) != 0:
            continue
        tr = r.get("tr") or []
        if sonnet_idx >= len(tr):
            continue
        slot = tr[sonnet_idx]
        if not slot:
            continue
        verdict, reason = slot[0], slot[1]
        if verdict != "no":
            continue
        if reason not in AMBIGUOUS_REASONS:
            continue
        rows.append(
            {
                "gene_symbol": r["symbol"],
                "uniprot_acc": r.get("uniprot") or "",
                "prior_reason": reason,
                "n_db_votes": 0,
            }
        )

    rows.sort(key=lambda x: x["gene_symbol"])

    fieldnames = ["gene_symbol", "uniprot_acc", "prior_reason", "n_db_votes"]
    with OUT_PATH.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r["prior_reason"]] = by_reason.get(r["prior_reason"], 0) + 1
    print(f"Wrote {len(rows)} genes → {OUT_PATH.relative_to(ROOT)}")
    print(f"Breakdown: {json.dumps(by_reason, sort_keys=True)}")


if __name__ == "__main__":
    main()
