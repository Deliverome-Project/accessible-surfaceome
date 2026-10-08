"""Per-residue disorder from ``disorder_public``, for the disorder tag-site lane.

The lane used a contiguous run of AlphaFold pLDDT below 70 as its flexibility proxy,
because the three published predictors were never connected to it. Measured against
Tedman's 112 screen-validated insertions, that proxy puts its top extracellular site a
median **40 aa** from his junction, while the predictors put theirs at **3 aa**:

    netsurfp-3.0         median  3 aa   86% within 5 aa
    metapredict          median  3 aa   74%
    alphafold-disorder   median  2 aa   76%
    pLDDT run (lane)     median 40 aa   15%

AlphaFold-disorder *is* 1 - pLDDT, so the gap is not the signal but how it is read: a
contiguous-run threshold versus a within-protein rank. Both are fixed here by scoring on
rank.

NetSurfP-3.0 is weighted highest because it is the predictor Tedman used, and it scores
its disorder over the first 400 residues only -- which is where a signal-peptide-proximal
tag goes, so the window is a match rather than a limitation.
"""

from __future__ import annotations

from typing import Any

PREDICTORS = ("netsurfp-3.0", "metapredict", "alphafold-disorder")
WEIGHTS = {"netsurfp-3.0": 2.0, "metapredict": 1.0, "alphafold-disorder": 1.0}
DISORDER_VERSION = "dis_2026_09_28"
_COLUMN = {"alphafold-disorder": "plddt_hex"}  # everything else stores disorder_hex


def _decode(hexstr: str, predictor: str) -> list[float]:
    """One byte per residue -> 0-1 disorder, inverting pLDDT."""
    raw = [b / 255.0 for b in bytes.fromhex(hexstr)]
    return [1.0 - v for v in raw] if predictor == "alphafold-disorder" else raw


def within_protein_percentile(track: list[float]) -> list[float]:
    """Each residue's rank in its own protein, 0-100.

    The predictors disagree about absolute disorder far more than about rank -- at the
    same residues NetSurfP-3.0 reads 0.93 where metapredict reads 0.61 -- so averaging
    raw scores would hand the decision to whichever tool is most confident.
    """
    if not track:
        return []
    ordered = sorted(track)
    n = len(ordered)
    out = []
    for v in track:
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if ordered[mid] < v:
                lo = mid + 1
            else:
                hi = mid
        out.append(100.0 * lo / n)
    return out


def fetch_tracks(client: Any, accessions: list[str], *, version: str = DISORDER_VERSION
                 ) -> dict[str, dict[str, list[float]]]:
    """``{accession: {predictor: per-residue disorder}}`` for the given accessions."""
    out: dict[str, dict[str, list[float]]] = {}
    for predictor in PREDICTORS:
        col = _COLUMN.get(predictor, "disorder_hex")
        for i in range(0, len(accessions), 50):
            chunk = accessions[i : i + 50]
            marks = ",".join("?" * len(chunk))
            rows = client.query(
                f"SELECT uniprot_acc_full, {col} FROM disorder_public "
                f"WHERE predictor=? AND disorder_version=? AND uniprot_acc_full IN ({marks})",
                [predictor, version, *chunk],
            )
            for r in rows:
                if r.get(col):
                    out.setdefault(r["uniprot_acc_full"], {})[predictor] = _decode(
                        r[col], predictor
                    )
    return out


def consensus(tracks: dict[str, list[float]], length: int) -> dict[int, float]:
    """Weighted mean of each predictor's within-protein percentile, by residue (1-indexed).

    A predictor shorter than the protein still counts over the residues it covers, which
    is what keeps NetSurfP-3.0 usable: it stops at 400 residues by design, and dropping it
    for any longer protein would discard the most informative track exactly where the
    signal-peptide-proximal sites are.
    """
    pct = {p: within_protein_percentile(t) for p, t in tracks.items() if t}
    if not pct:
        return {}
    out: dict[int, float] = {}
    for res in range(1, length + 1):
        num = den = 0.0
        for p, values in pct.items():
            if res <= len(values):
                w = WEIGHTS.get(p, 1.0)
                num += w * values[res - 1]
                den += w
        if den:
            out[res] = num / den
    return out
