"""Third-party per-residue tag/insertion-site predictions, one row per protein.

Three published predictors are scored against the same cohort our deterministic
lanes run on, so their disagreements are measurable rather than anecdotal:

* **ProDomino** (Nature Methods 2025) — ESM-2 3B embeddings + an MLP head, no
  structure at all. Trained on natural intradomain insertion events.
* **EpicTope** — conservation, secondary structure, disordered binding and RSA
  combined "least-worst" (min across features over a 7-residue window).
* **INDELi-E** (Lehner lab) — ESM-1v substitution scores plus secondary
  structure; predicts 1-aa indel tolerance, so its insert size is much smaller
  than an epitope tag and it is the loosest proxy of the three.

Scores are a BYTE PER RESIDUE, hex-encoded, exactly as `disorder_public` stores
pLDDT and RSA. A 1,651-residue protein is ~3.3 kB of hex instead of ~13 kB of
JSON floats, every row stays far under D1's 2 MB cap, and nothing is lost: these
are probabilities whose useful resolution is about two decimal places.

LICENCE IS A COLUMN, not a footnote, because the three differ and the
difference is load-bearing. INDELi-E is CC BY 4.0 and EpicTope's GPL-3.0 covers
its code rather than the data it emits, so both may be published. ProDomino is
CC BY-NC 4.0 and its predictions inherit that restriction — it belongs in the
private database unless someone decides otherwise with the licence in view.
Every consumer can read the terms off the row rather than having to know them.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS tag_site_prediction (
    uniprot_acc       TEXT NOT NULL,
    gene_symbol       TEXT,
    predictor         TEXT NOT NULL,
    predictor_version TEXT,
    model_config      TEXT,
    protein_length    INTEGER,
    n_scores          INTEGER,
    scores_hex        TEXT NOT NULL,
    score_min         REAL,
    score_max         REAL,
    licence           TEXT NOT NULL,
    citation          TEXT,
    run_id            TEXT,
    created_at        TEXT NOT NULL,
    PRIMARY KEY (uniprot_acc, predictor)
);
"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tsp_predictor ON tag_site_prediction (predictor);",
    "CREATE INDEX IF NOT EXISTS idx_tsp_gene ON tag_site_prediction (gene_symbol);",
)

_COLS = (
    "uniprot_acc",
    "gene_symbol",
    "predictor",
    "predictor_version",
    "model_config",
    "protein_length",
    "n_scores",
    "scores_hex",
    "score_min",
    "score_max",
    "licence",
    "citation",
    "run_id",
    "created_at",
)

_ensured: set[int] = set()


def ensure_table(client: D1Client) -> None:
    if id(client) in _ensured:
        return
    client.query(DDL, [])
    for idx in INDEXES:
        client.query(idx, [])
    _ensured.add(id(client))


def encode_scores(scores: list[float], *, lo: float = 0.0, hi: float = 1.0) -> str:
    """Per-residue scores -> one hex byte each, over the half-open range [lo, hi].

    The default [0,1] is the probability case (ProDomino, EpicTope). INDELi-E
    emits a roughly [-0.2, 3.2] ESM-derived score, so it passes its own range.

    ``lo``/``hi`` MUST be a constant of the predictor, never per-protein: a
    per-protein range would make byte 128 mean a different score in every row,
    so no threshold could be applied across the cohort. Whatever is used is
    recorded in the row's ``model_config`` as ``encoding=linear:lo=..:hi=..``,
    which is what :func:`decode_scores` needs to invert it.
    """
    span = hi - lo
    return bytes(
        max(0, min(255, round((float(s) - lo) / span * 255))) for s in scores
    ).hex()


def decode_scores(scores_hex: str, *, lo: float = 0.0, hi: float = 1.0) -> list[float]:
    """Inverse of :func:`encode_scores`. Index 0 is residue 1.

    Pass the same ``lo``/``hi`` the row was encoded with — read them off its
    ``model_config``, don't assume the [0,1] default.
    """
    span = hi - lo
    return [lo + b / 255.0 * span for b in bytes.fromhex(scores_hex)]


def encoding_config(lo: float, hi: float) -> str:
    """The ``model_config`` fragment that makes a row's bytes decodable."""
    return f"encoding=linear:lo={lo}:hi={hi}"


def row_for(
    record: dict[str, Any],
    *,
    predictor: str,
    licence: str,
    citation: str = "",
    predictor_version: str = "",
    model_config: str = "",
    run_id: str = "",
    lo: float = 0.0,
    hi: float = 1.0,
) -> dict[str, Any]:
    """One prediction row. ``record`` is {gene_symbol, uniprot_acc, length, scores}.

    ``lo``/``hi`` are the encoding range (see :func:`encode_scores`); they are
    appended to ``model_config`` so the row carries what it takes to decode it.
    """
    scores = record["scores"]
    cfg = encoding_config(lo, hi)
    model_config = f"{model_config}; {cfg}" if model_config else cfg
    return {
        "uniprot_acc": record["uniprot_acc"],
        "gene_symbol": record.get("gene_symbol"),
        "predictor": predictor,
        "predictor_version": predictor_version,
        "model_config": model_config,
        "protein_length": record.get("length"),
        "n_scores": len(scores),
        "scores_hex": encode_scores(scores),
        "score_min": round(min(scores), 5) if scores else None,
        "score_max": round(max(scores), 5) if scores else None,
        "licence": licence,
        "citation": citation,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def publish(rows: list[dict[str, Any]], *, client: D1Client) -> int:
    """UPSERT by (uniprot_acc, predictor). Idempotent."""
    if not rows:
        return 0
    ensure_table(client)
    cols = ", ".join(_COLS)
    marks = ", ".join(["?"] * len(_COLS))
    n = 0
    for row in rows:
        client.query(
            f"INSERT OR REPLACE INTO tag_site_prediction ({cols}) VALUES ({marks});",
            [row[c] for c in _COLS],
        )
        n += 1
    return n
