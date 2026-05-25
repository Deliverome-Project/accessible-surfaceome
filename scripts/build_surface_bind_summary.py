"""Build a per-UniProt SURFACE-Bind summary JSON.

Downloads :mod:`seed_count_a.txt` and :mod:`seed_count_b.txt` from the
SURFACE-Bind GitHub repo
(https://github.com/hamedkhakzad/SURFACE-Bind/tree/main/database) and
aggregates them per UniProt accession into a single JSON keyed by acc.

The resulting file is checked into the repo at
``data/external/surface_bind/surface_bind_summary.json`` so the
orchestrator can do an O(1) in-memory lookup at record-build time
without a per-gene network call. ~2500 entries × ~5 numeric fields →
~500 KB on disk, well below the LFS threshold.

Re-run periodically (when SURFACE-Bind ships updates) — the script
is idempotent and the diff against the committed copy shows what
changed.

Schema per entry (keys are UniProt accessions):

.. code-block:: json

    {
      "P00533": {
        "n_sites": 9,
        "n_seeds_alpha": 956,
        "n_seeds_beta": 54404,
        "n_seeds_total": 55360,
        "chain": "A"
      },
      ...
    }

A separate top-level ``__meta__`` carries source provenance.

Run::

    uv run python scripts/build_surface_bind_summary.py
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = (
    REPO_ROOT / "data" / "external" / "surface_bind" / "surface_bind_summary.json"
)

# Raw-file URLs on the SURFACE-Bind GitHub repo (main branch). The
# files are tracked in plain git (not LFS), so the raw.githubusercontent
# URL serves them as text directly.
_BASE = "https://raw.githubusercontent.com/hamedkhakzad/SURFACE-Bind/main/database"
_SEED_COUNT_ALPHA_URL = f"{_BASE}/seed_count_a.txt"
_SEED_COUNT_BETA_URL = f"{_BASE}/seed_count_b.txt"

_CITATION = (
    "Marchand A, Khakzad H, et al. Mapping targetable sites on the "
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


def _aggregate(
    alpha: dict[str, dict[str, int]],
    beta: dict[str, dict[str, int]],
) -> dict[str, dict[str, Any]]:
    """Merge α and β per-site dicts into per-UniProt summary entries.

    The site count is the union of α and β site ids (typically the
    same set, but defensive). Seed totals sum across all sites in
    each backbone-class file. UniProt acc is the prefix before the
    chain-letter suffix.
    """
    out: dict[str, dict[str, Any]] = {}
    all_keys = set(alpha) | set(beta)
    for acc_chain in sorted(all_keys):
        # Split "P00533_A" → acc="P00533", chain="A"
        if "_" not in acc_chain:
            continue
        acc, chain = acc_chain.rsplit("_", 1)
        a_sites = alpha.get(acc_chain, {})
        b_sites = beta.get(acc_chain, {})
        n_sites = len(set(a_sites) | set(b_sites))
        n_alpha = sum(a_sites.values())
        n_beta = sum(b_sites.values())
        # When a UniProt acc has multiple chains in the dataset
        # (rare — most are single-chain), keep the first chain seen
        # and log; the cohort is human surfaceome so the canonical
        # chain dominates.
        if acc in out:
            logger.info(
                "multiple chains for %s; keeping %s, ignoring %s",
                acc, out[acc]["chain"], chain,
            )
            continue
        out[acc] = {
            "n_sites": n_sites,
            "n_seeds_alpha": n_alpha,
            "n_seeds_beta": n_beta,
            "n_seeds_total": n_alpha + n_beta,
            "chain": chain,
        }
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    logger.info("fetching SURFACE-Bind seed-count files")
    alpha_text = _fetch_text(_SEED_COUNT_ALPHA_URL)
    beta_text = _fetch_text(_SEED_COUNT_BETA_URL)

    alpha = _parse_seed_counts(alpha_text)
    beta = _parse_seed_counts(beta_text)
    logger.info("parsed %d alpha entries, %d beta entries", len(alpha), len(beta))

    summary = _aggregate(alpha, beta)
    logger.info("aggregated %d unique UniProt entries", len(summary))

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
