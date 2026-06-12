"""UBERON → organ-system category map for tissue-level enrichment.

Parallel to ``cl_graph.py`` (which rolls leaf CL terms up to ~10 cell
compartments). Here we roll the 409 fine-grained CZI UBERON terms up
to 14 organ-system categories so HPA-style τ + classification can run
on a tractable axis instead of on raw UBERONs where brain gets split
across 96 subregions (Brodmann areas, cortical layers, etc.).

The map is the **generated** mapping at
``viewer/lib/tissue-categories-uberon-map.generated.ts`` — produced by
``scripts/build_tissue_category_mapping.py`` via a programmatic walk
of UBERON's is_a + part_of graph from defined organ-system roots
(UBERON:0001017 CNS, UBERON:0001004 respiratory, etc.). We parse that
TS file at import time so Python and TypeScript stay in lock-step:
when the build script regenerates the TS map, this module picks it up
automatically on the next import.

The 14 categories match the deliverome design-token palette
(viewer/lib/tissue-categories.ts):

    cns                       (CNS — 96 UBERONs incl. all brain subregions)
    head_sensory              (Head & sensory — 62)
    digestive                 (Digestive GI — 56)
    cardiovascular            (Cardiovascular — 36)
    skin_adipose              (Skin & adipose — 31)
    respiratory               (Respiratory — 27)
    fluids_other              (Fluids / other — 34, including reassigned
                               musculoskeletal terms after the category
                               was dropped — see commit 58a66a4c2)
    reproductive              (Reproductive — 21)
    lymphoid                  (Lymphoid & blood — 13)
    hepatobiliary_pancreas    (Hepatobiliary & pancreas — 12)
    developmental             (Developmental — 11)
    urinary                   (Urinary — 7)
    endocrine                 (Endocrine — 3)
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final

REPO = Path(__file__).resolve().parents[3]
DEFAULT_TS_MAP_PATH = (
    REPO / "viewer" / "lib" / "tissue-categories-uberon-map.generated.ts"
)

TISSUE_CATEGORIES: Final[tuple[str, ...]] = (
    "cns",
    "head_sensory",
    "respiratory",
    "cardiovascular",
    "lymphoid",
    "digestive",
    "hepatobiliary_pancreas",
    "urinary",
    "endocrine",
    "reproductive",
    "skin_adipose",
    "developmental",
    "fluids_other",
)

_PATTERN = re.compile(r'"(UBERON:\d+)":\s*"([a-z_]+)"')


@lru_cache(maxsize=1)
def _load_map(path_str: str) -> dict[str, str]:
    """Parse the generated TS map into a Python dict. Cached."""
    path = Path(path_str)
    if not path.exists():
        return {}
    text = path.read_text()
    return dict(_PATTERN.findall(text))


def uberon_category(uberon_id: str, ts_map_path: Path | None = None) -> str:
    """Return the 14-category organ-system label for a UBERON term.

    Falls back to ``fluids_other`` when the UBERON isn't in the
    generated map (the build script's ontology walk handles 409/409
    CZI UBERONs as of the current cl-basic + uberon-2024-10 cuts, so
    fall-through is rare and reserved for truly orphan terms).
    """
    if not uberon_id:
        return "fluids_other"
    path = ts_map_path or DEFAULT_TS_MAP_PATH
    return _load_map(str(path)).get(uberon_id, "fluids_other")


def all_categories_and_uberons(ts_map_path: Path | None = None) -> dict[str, list[str]]:
    """Inverse: category → list of UBERON IDs in it. Useful for the
    full-universe denominator in τ + classifier when we want every
    category's total cell count (not just the categories the current
    gene has signal in)."""
    path = ts_map_path or DEFAULT_TS_MAP_PATH
    out: dict[str, list[str]] = {c: [] for c in TISSUE_CATEGORIES}
    for ub, cat in _load_map(str(path)).items():
        if cat not in out:
            out[cat] = []
        out[cat].append(ub)
    return out
