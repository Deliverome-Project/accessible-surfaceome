"""UniProt-feature veto for the deterministic tag-site gates.

Fetches the reviewed UniProt entry (reusing the repo's rate-limited
``CachedHTTP``), extracts hazard residues (disulfides, glycosylation,
binding/active/processing sites), and computes each residue's 3D distance to the
nearest hazard atom on the AlphaFold model — the ``feature_dist`` signal the
gates use for their spatial clearance veto.
"""
from __future__ import annotations

from typing import Any

# UniProt feature types whose residues a tag insertion must stay clear of.
HAZARD_FEATURE_TYPES = {
    "Disulfide bond",
    "Glycosylation",
    "Binding site",
    "Active site",
    "Site",
    "Modified residue",
    "Cross-link",
    "Lipidation",
}


def hazard_residues(features: list[dict[str, Any]]) -> set[int]:
    """Residue positions (1-indexed) covered by hazard features. A disulfide's
    two partners are its ``start`` and ``end`` endpoints; spans (binding sites)
    contribute every residue start..end. Non-hazard types are ignored."""
    out: set[int] = set()
    for feat in features:
        if feat.get("type") not in HAZARD_FEATURE_TYPES:
            continue
        loc = feat.get("location", {})
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        if start is None and end is None:
            continue
        if feat.get("type") == "Disulfide bond":
            # start & end are the two bonded cysteines, not a contiguous span.
            for v in (start, end):
                if isinstance(v, int):
                    out.add(v)
            continue
        s = start if isinstance(start, int) else end
        e = end if isinstance(end, int) else start
        if isinstance(s, int) and isinstance(e, int):
            out.update(range(min(s, e), max(s, e) + 1))
    return out


def feature_distances(pdb_path: str, hazard_res: set[int]) -> dict[int, float]:
    """Per-residue minimum CA-CA distance (Å) to any hazard residue on the
    model. Residues with no hazard in the structure get ``inf`` (fully clear)."""
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    ca: dict[int, Any] = {}
    for res in struct.get_residues():
        if "CA" in res:
            ca[res.id[1]] = res["CA"].coord
    hazard_coords = [ca[h] for h in hazard_res if h in ca]
    out: dict[int, float] = {}
    for r, coord in ca.items():
        if not hazard_coords:
            out[r] = float("inf")
            continue
        out[r] = min(float(((coord - h) ** 2).sum() ** 0.5) for h in hazard_coords)
    return out


def fetch_uniprot_features(acc: str, http: Any | None = None) -> list[dict[str, Any]]:
    """Fetch the reviewed UniProt entry and return its ``features`` list. Uses
    the repo's default rate-limited cached client when ``http`` is None."""
    from accessible_surfaceome.tools._shared.http import open_default_client

    close = False
    if http is None:
        http = open_default_client()
        close = True
    try:
        data = http.get_json(
            f"https://rest.uniprot.org/uniprotkb/{acc}.json",
            source="uniprot",
            ttl_days=30,
        )
    finally:
        if close:
            http.__exit__(None, None, None)
    return data.get("features", []) if isinstance(data, dict) else []
