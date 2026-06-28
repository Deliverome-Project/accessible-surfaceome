"""Build a per-UniProt SURFACE-Bind summary JSON.

Downloads the per-protein-per-site data tables from the SURFACE-Bind
GitHub repo (https://github.com/hamedkhakzad/SURFACE-Bind/tree/main/database)
and aggregates them per UniProt accession into a single JSON keyed by
acc, with each entry carrying both per-protein aggregates and the
per-site arrays (anchor residue, BSA, α/β seeds, hydrophobicity).

Sources:

* ``results_no_TM.csv`` — primary per-site data. One row per protein
  with parallel arrays indexed by site. Authoritative for which
  proteins are in SURFACE-Bind and which sites are scored — the
  ``seed_count_*.txt`` files have a slightly looser superset.
* ``seed_count_a.txt`` / ``seed_count_b.txt`` — used to recover the
  ``chain`` identifier (which doesn't appear in results_no_TM.csv).

The resulting file is checked into the repo at
``data/external/surface_bind/surface_bind_summary.json`` so the
orchestrator can do an O(1) in-memory lookup at record-build time
without a per-gene network call. ~2700 entries (mostly with per-site
arrays) totals ~1 MB on disk, well below the LFS threshold.

Re-run periodically (when SURFACE-Bind ships updates) — the script
is idempotent and the diff against the committed copy shows what
changed.

Schema per entry (keys are UniProt accessions):

.. code-block:: json

    {
      "P00533": {
        "n_sites": 8,
        "n_seeds_alpha": 956,
        "n_seeds_beta": 54404,
        "n_seeds_total": 55360,
        "chain": "A",
        "main_class": "Receptors",
        "sub_class": "Kinase",
        "protein_name": "Epidermal growth factor receptor",
        "sites": [
          {"site_id": 0, "anchor_residue": 743, "area_a2": 1523.93,
           "n_seeds_alpha": 1, "n_seeds_beta": 878, "hydrophobicity": 6.7},
          ...
        ],
        "pdbs": ["1IVO", "1M14", ...]
      },
      ...
    }

A separate top-level ``__meta__`` carries source provenance.

Run::

    uv run python scripts/build_surface_bind_summary.py
"""

from __future__ import annotations

import ast
import csv
import io
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = (
    REPO_ROOT / "data" / "external" / "surface_bind" / "surface_bind_summary.json"
)

# Raw-file URLs on the SURFACE-Bind GitHub repo (main branch). The
# files are tracked in plain git (not LFS), so the raw.githubusercontent
# URL serves them as text directly.
_BASE = "https://raw.githubusercontent.com/hamedkhakzad/SURFACE-Bind/main/database"
_SEED_COUNT_ALPHA_URL = f"{_BASE}/seed_count_a.txt"
_SEED_COUNT_BETA_URL = f"{_BASE}/seed_count_b.txt"
# Per-site detail: anchor residue + BSA + α/β seed counts + hydrophobicity
# per site, plus protein classification + PDB list per UniProt.
_RESULTS_URL = f"{_BASE}/results_no_TM_pnames.csv"

_CITATION = (
    "Balbi PEM, Sadek A, Marchand A, et al. Mapping targetable sites on the "
    "human surfaceome for the design of novel binders. PNAS 2026. "
    "doi:10.1073/pnas.2506269123"
)


def _fetch_text(url: str) -> str:
    """Fetch a raw GitHub file as text. Errors propagate (no caching
    — this is a one-shot build script, not a hot-path fetcher)."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _parse_seed_counts(text: str) -> dict[str, dict[str, int]]:
    """Parse a ``seed_count_*.txt`` body into ``{acc_chain: {site_n: count}}``.

    Format: ``{UNIPROT}_{CHAIN}[_beta];site_N;{count}`` one per line.
    The ``_beta`` suffix only appears on β-strand files; we strip it
    here so the caller can merge α / β under the same acc_chain key.
    """
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if len(parts) != 3:
            logger.warning("malformed line: %r", line)
            continue
        acc_chain, site_id, count_s = parts
        # Strip the `_beta` suffix that distinguishes the β file format
        # — both α and β files use the same `{ACC}_{CHAIN}` stem.
        if acc_chain.endswith("_beta"):
            acc_chain = acc_chain[: -len("_beta")]
        try:
            count = int(count_s)
        except ValueError:
            logger.warning("non-integer count in %r", line)
            continue
        out[acc_chain][site_id] = count
    return out


def _acc_to_chain(
    alpha: dict[str, dict[str, int]],
    beta: dict[str, dict[str, int]],
) -> dict[str, str]:
    """Recover UniProt-acc → chain mapping from the seed-count file
    keys (``{ACC}_{CHAIN}`` format)."""
    out: dict[str, str] = {}
    for acc_chain in sorted(set(alpha) | set(beta)):
        if "_" not in acc_chain:
            continue
        acc, chain = acc_chain.rsplit("_", 1)
        if acc not in out:
            out[acc] = chain
    return out


def _parse_array(s: str) -> list[Any]:
    """Parse a Python-literal array string (``[1, 2, 3]``) from the
    results CSV. Empty / malformed inputs return an empty list."""
    s = (s or "").strip()
    if not s or s == "[]":
        return []
    try:
        val = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return []
    return list(val) if isinstance(val, (list, tuple)) else []


def _parse_results(text: str, chain_lookup: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Parse ``results_no_TM_pnames.csv`` into per-UniProt entries
    with both per-protein aggregates and the per-site array.

    The CSV uses ``;`` as the delimiter (the pnames variant; the
    non-pnames variant uses ``,`` but its protein-name column has
    embedded commas that break naive CSV parsing). Per-site arrays
    are stored as Python-literal strings in cells.
    """
    out: dict[str, dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    for row in reader:
        acc = (row.get("acc") or "").strip()
        if not acc:
            continue
        anchors = _parse_array(row.get("binding_sites", ""))
        areas = _parse_array(row.get("area_a2", ""))
        alphas = _parse_array(row.get("alpha_seeds", ""))
        betas = _parse_array(row.get("beta_seeds", ""))
        hydros = _parse_array(row.get("hydrophobicity", ""))
        pdbs = _parse_array(row.get("pdbs", ""))

        n_sites = len(anchors)
        # Defensive: if the parallel arrays have different lengths, that's
        # a data-quality flag — log and trim to the shortest so per-site
        # records stay consistent.
        if not all(len(a) == n_sites for a in (areas, alphas, betas, hydros)):
            logger.warning(
                "%s: per-site array length mismatch "
                "(anchors=%d areas=%d alphas=%d betas=%d hydros=%d); trimming",
                acc, n_sites, len(areas), len(alphas), len(betas), len(hydros),
            )
            n_sites = min(len(anchors), len(areas), len(alphas), len(betas), len(hydros))

        sites = [
            {
                "site_id": i,
                "anchor_residue": int(anchors[i]),
                "area_a2": float(areas[i]),
                "n_seeds_alpha": int(alphas[i]),
                "n_seeds_beta": int(betas[i]),
                "hydrophobicity": float(hydros[i]),
            }
            for i in range(n_sites)
        ]
        out[acc] = {
            "n_sites": n_sites,
            "n_seeds_alpha": sum(s["n_seeds_alpha"] for s in sites),
            "n_seeds_beta": sum(s["n_seeds_beta"] for s in sites),
            "n_seeds_total": sum(
                s["n_seeds_alpha"] + s["n_seeds_beta"] for s in sites
            ),
            "chain": chain_lookup.get(acc),
            "main_class": (row.get("main_class") or "").strip() or None,
            "sub_class": (row.get("sub_class_1") or "").strip() or None,
            "protein_name": (row.get("protein_names") or "").strip() or None,
            "sites": sites,
            "pdbs": [str(p) for p in pdbs],
        }
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    logger.info("fetching SURFACE-Bind data files")
    alpha_text = _fetch_text(_SEED_COUNT_ALPHA_URL)
    beta_text = _fetch_text(_SEED_COUNT_BETA_URL)
    results_text = _fetch_text(_RESULTS_URL)

    alpha = _parse_seed_counts(alpha_text)
    beta = _parse_seed_counts(beta_text)
    chain_lookup = _acc_to_chain(alpha, beta)

    summary = _parse_results(results_text, chain_lookup)
    n_with_sites = sum(1 for v in summary.values() if v["n_sites"] > 0)
    logger.info(
        "parsed %d UniProt entries from results_no_TM (%d with at least "
        "one scored site, %d in seed_count files for chain xref)",
        len(summary), n_with_sites, len(chain_lookup),
    )

    payload: dict[str, Any] = {
        "__meta__": {
            "source": "SURFACE-Bind v1 (hamedkhakzad/SURFACE-Bind main branch)",
            "source_urls": {
                "alpha": _SEED_COUNT_ALPHA_URL,
                "beta": _SEED_COUNT_BETA_URL,
            },
            "citation": _CITATION,
            "license": "see SURFACE-Bind LICENSE (https://github.com/hamedkhakzad/SURFACE-Bind/blob/main/LICENSE)",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "n_entries": len(summary),
        },
        **summary,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    logger.info("wrote %s (%d bytes)", OUTPUT_PATH, OUTPUT_PATH.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
