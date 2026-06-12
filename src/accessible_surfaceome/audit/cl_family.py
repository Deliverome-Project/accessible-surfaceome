"""Middle-granularity CL family rollup.

Sits between the leaf Cell Ontology axis (~600 terms — too noisy for
HPA's 4× test) and the broad compartment axis (10 — too coarse to be
useful). Walks the CL graph from each CZI leaf CL upward and assigns
each leaf to the NEAREST ancestor whose number of CZI cohort
descendants falls in [MIN_DESC, MAX_DESC]. That ancestor is the
"family."

Why this granularity: HPA's actual cell-type rollup uses ~80-150
"named families" (B cell, T cell, macrophage, hepatocyte, astrocyte,
basal epithelial cell, ...). Hand-curating this list would rot every
Census refresh; deriving it programmatically from the CL graph
matches HPA's spirit while auto-updating with new cohort terms.

For the current CZI Census 2025-11-08 / cl-basic.obo cuts, the
default range [MIN_DESC=6, MAX_DESC=40] yields ~156 families. Leaves
without a family ancestor in that range (~130 of 896) fall back to
their broad compartment via cl_graph.cl_compartment.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Final

REPO = Path(__file__).resolve().parents[3]
DEFAULT_OBO_PATH = REPO / "data" / "external" / "ontologies" / "cl-basic.obo"
DEFAULT_CL_LABELS = Path("/tmp/cl_id_to_label.tsv")

# Range tuned so we land in HPA's ~80-150 family-count zone.
MIN_DESC: Final[int] = 6
MAX_DESC: Final[int] = 40


@lru_cache(maxsize=1)
def _load_dag(obo_path_str: str):
    from goatools.obo_parser import GODag
    return GODag(obo_path_str, prt=None)


def _load_czi_leaves(cl_labels_path: Path = DEFAULT_CL_LABELS) -> tuple[str, ...]:
    out: list[str] = []
    if not cl_labels_path.exists():
        return tuple()
    with cl_labels_path.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0].startswith("CL:"):
                out.append(parts[0])
    return tuple(out)


def _ancestors(dag, cl_id: str) -> set[str]:
    if cl_id not in dag:
        return set()
    seen = {cl_id}
    queue = [dag[cl_id]]
    while queue:
        t = queue.pop()
        for p in t.parents:
            if p.id not in seen:
                seen.add(p.id)
                queue.append(p)
    return seen


def _bfs_nearest_in_range(
    dag, leaf: str, desc_count: dict[str, int], min_d: int, max_d: int
) -> str | None:
    """BFS upward from `leaf`; return the first ancestor (including the
    leaf itself) whose descendant count is in [min_d, max_d]. None if
    no ancestor fits."""
    if leaf not in dag:
        return None
    visited: set[str] = set()
    queue = [dag[leaf]]
    while queue:
        t = queue.pop(0)
        if t.id in visited:
            continue
        visited.add(t.id)
        n = desc_count.get(t.id, 0)
        if min_d <= n <= max_d:
            return t.id
        for p in t.parents:
            queue.append(p)
    return None


@lru_cache(maxsize=8)
def _build_family_map(
    obo_path_str: str, labels_path_str: str, min_d: int, max_d: int
) -> dict[str, str]:
    dag = _load_dag(obo_path_str)
    leaves = _load_czi_leaves(Path(labels_path_str))
    # Count descendants per ancestor across all CZI leaves.
    desc_count: Counter[str] = Counter()
    for leaf in leaves:
        for a in _ancestors(dag, leaf):
            desc_count[a] += 1
    out: dict[str, str] = {}
    for leaf in leaves:
        fam = _bfs_nearest_in_range(dag, leaf, desc_count, min_d, max_d)
        if fam is not None:
            out[leaf] = fam
    return out


def cl_family(cl_id: str, cl_label: str | None = None) -> str:
    """Return the family CL term for a leaf CL — typically a name like
    "B cell", "T cell", "macrophage", "hepatocyte", etc.

    **Fallback (v2.1.7+).** When no graph ancestor with [MIN_DESC,
    MAX_DESC] cohort descendants exists for this leaf CL, the leaf
    IS its own family — return the leaf CL ID. Previously fell back
    to the broad compartment (Epithelial / Immune / etc.), which lost
    information for rare lineages (KLK2's prostate-luminal CL has no
    natural family ancestor; "Epithelial" is too coarse). Returning
    the leaf preserves "enriched · luminal cell of prostate
    epithelium" instead of dropping to "enriched · Epithelial."
    """
    if not cl_id:
        return ""
    fam_map = _build_family_map(str(DEFAULT_OBO_PATH), str(DEFAULT_CL_LABELS), MIN_DESC, MAX_DESC)
    fam = fam_map.get(cl_id)
    if fam is not None:
        return fam
    # Leaf is its own family — preserves the specific label.
    return cl_id


def cl_family_label(family_id: str) -> str:
    """Resolve a family CL ID to its human label. Pass-through for any
    non-CL strings (legacy compartment labels from older builds)."""
    if not family_id.startswith("CL:"):
        return family_id
    dag = _load_dag(str(DEFAULT_OBO_PATH))
    if family_id in dag:
        return dag[family_id].name or family_id
    return family_id
