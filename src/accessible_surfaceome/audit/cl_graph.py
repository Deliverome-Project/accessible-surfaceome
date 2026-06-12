"""Cell Ontology graph walk for broad-compartment rollup.

Replaces the keyword-rule rollup in ``cl_broad_classes.py``. Each leaf CL
term is mapped to one of ~10 compartments by walking ``is_a`` ancestors
in the CL graph (loaded from ``data/external/ontologies/cl-basic.obo``)
and matching against a priority-ordered list of compartment-root CL
terms. First match wins.

Why graph not keywords:

* **Stable across Census releases.** CZI adds new CL terms each Census
  cut. The keyword rules need a code update; the graph walk finds the
  compartment for any descendant of an existing root automatically.

* **Matches the field convention.** Tabula Sapiens, CellTypist, CellRef
  all derive their compartments by walking CL ``is_a`` to defined
  root terms. Reviewer-traceable to the OBO Foundry release.

* **Correct on edge cases.** "alveolar macrophage" → leukocyte (Immune)
  by ancestry, not by an "alveolar" keyword that would mis-route to
  Epithelial. "Trophoblast giant cell" → extraembryonic (Reproductive),
  not "T cell" substring match.

Compartment roots (priority-ordered — first ancestor match wins):

  Tumor          ← malignant cell / neoplastic cell
  Reproductive   ← germ line cell / extraembryonic cell
  Immune         ← leukocyte / hematopoietic cell (catches erythrocytes)
  Neural         ← neural cell / glial cell
  Endothelial    ← endothelial cell
  Muscle         ← muscle cell
  Stem           ← stem cell
  Epithelial     ← epithelial cell
  Stromal        ← stromal cell / fibroblast / connective tissue cell
  Other          ← no ancestor match
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

REPO = Path(__file__).resolve().parents[3]
DEFAULT_OBO_PATH = REPO / "data" / "external" / "ontologies" / "cl-basic.obo"

BROAD_CLASSES: Final[tuple[str, ...]] = (
    "Epithelial",
    "Immune",
    "Endothelial",
    "Stromal",
    "Neural",
    "Muscle",
    "Reproductive",
    "Stem",
    "Tumor",
    "Other",
)

# Priority-ordered list of (compartment_root_cl_id, compartment_label).
# First ancestor match wins. Order matters when a CL term is descendant
# of multiple roots — e.g. a malignant epithelial cell is both Tumor and
# Epithelial; Tumor is listed first so it wins (a treatment-relevant
# distinction). Same for Reproductive over Epithelial (trophoblast is
# epithelium by lineage, but we want it bucketed Reproductive).
_COMPARTMENT_ROOTS: Final[tuple[tuple[str, str], ...]] = (
    ("CL:0001064", "Tumor"),         # malignant cell
    ("CL:0001063", "Tumor"),         # neoplastic cell
    ("CL:0000039", "Reproductive"),  # germ line cell
    ("CL:0000349", "Reproductive"),  # extraembryonic cell (trophoblast)
    ("CL:0000738", "Immune"),        # leukocyte
    ("CL:0000988", "Immune"),        # hematopoietic cell (erythrocyte, etc.)
    ("CL:0002319", "Neural"),        # neural cell
    ("CL:0000125", "Neural"),        # glial cell (alt root)
    ("CL:0000115", "Endothelial"),   # endothelial cell
    ("CL:0000187", "Muscle"),        # muscle cell
    ("CL:0000034", "Stem"),          # stem cell
    ("CL:0000066", "Epithelial"),    # epithelial cell
    ("CL:0000499", "Stromal"),       # stromal cell
    ("CL:0000057", "Stromal"),       # fibroblast (alt)
    ("CL:0002320", "Stromal"),       # connective tissue cell
)


@lru_cache(maxsize=1)
def _load_dag(obo_path_str: str):
    """Load the CL OBO with goatools and cache. goatools is already in the
    project's dependency list (used elsewhere for GO terms); reusing it
    avoids adding obonet."""
    from goatools.obo_parser import GODag
    return GODag(obo_path_str, prt=None)


@lru_cache(maxsize=4096)
def _ancestors(cl_id: str, obo_path_str: str) -> frozenset[str]:
    """All is_a ancestors of `cl_id` (recursive), including the term itself.
    Frozenset so the result is hashable for cache."""
    dag = _load_dag(obo_path_str)
    if cl_id not in dag:
        return frozenset()
    seen = {cl_id}
    queue = [dag[cl_id]]
    while queue:
        t = queue.pop()
        for p in t.parents:
            if p.id not in seen:
                seen.add(p.id)
                queue.append(p)
    return frozenset(seen)


def cl_compartment(cl_id: str, obo_path: Path | None = None) -> str:
    """Return the broad compartment for a leaf CL term via graph walk.

    Returns one of the ~10 strings in ``BROAD_CLASSES``. Falls back to
    ``"Other"`` when the CL term isn't in the OBO (rare — cl-basic.obo
    covers ~99% of CZI's WMG CL terms) or has no compartment-root
    ancestor.
    """
    if not cl_id:
        return "Other"
    obo = obo_path or DEFAULT_OBO_PATH
    a = _ancestors(cl_id, str(obo))
    if not a:
        return "Other"
    for root, label in _COMPARTMENT_ROOTS:
        if root in a:
            return label
    return "Other"
