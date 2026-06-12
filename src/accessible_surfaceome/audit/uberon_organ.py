"""Middle-granularity UBERON organ rollup.

Parallel to ``cl_family`` for cell types. Walks the UBERON graph
(``is_a`` + ``part_of`` edges) from each CZI UBERON term upward and
assigns it to the NEAREST ancestor whose number of CZI cohort
descendants falls in ``[MIN_DESC, MAX_DESC]``. That ancestor is the
"organ."

Sits between the leaf UBERON axis (~410 — too fine, brain fragments
across 96 subregions) and the organ-system category axis (13 — too
coarse for "which organ specifically?"). With the default range
``[MIN_DESC=4, MAX_DESC=30]`` we land on ~152 organ-level terms:
brain, kidney, retina, lymph node, heart, lung, intestine, prostate
gland, etc. — plus more specific structures where CZI has dense
sampling (Brodmann areas roll to "Brodmann area" parent, cortical
subregions roll to "cortex of cerebral lobe", etc.).

The OBO source for this walk is `/tmp/uberon.obo` — fetched and
cached by the user's ``scripts/build_tissue_category_mapping.py``.
This module reuses that cache instead of re-downloading.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Final

from accessible_surfaceome.audit.uberon_categories import uberon_category

DEFAULT_OBO_PATH = Path("/tmp/uberon.obo")
DEFAULT_UBERON_LABELS = Path("/tmp/uberon_to_label.tsv")

MIN_DESC: Final[int] = 4
MAX_DESC: Final[int] = 30


@lru_cache(maxsize=1)
def _parse_obo(obo_path_str: str) -> dict[str, dict]:
    """Parse uberon.obo into {id: {'id', 'name', 'is_a', 'part_of'}}.

    Minimal: we only need ``is_a`` and ``part_of UBERON:xxx`` lines.
    The full uberon.obo has many other relationship types we ignore.
    """
    path = Path(obo_path_str)
    if not path.exists():
        return {}
    terms: dict[str, dict] = {}
    current: dict | None = None
    with path.open() as f:
        for raw in f:
            line = raw.rstrip()
            if line == "[Term]":
                if current and current.get("id"):
                    terms[current["id"]] = current
                current = {"id": None, "name": None, "is_a": [], "part_of": []}
            elif line.startswith("id: UBERON:"):
                if current is not None:
                    current["id"] = line[4:]
            elif line.startswith("name: ") and current is not None:
                current["name"] = line[6:]
            elif line.startswith("is_a: UBERON:") and current is not None:
                m = re.match(r"is_a:\s+(UBERON:\d+)", line)
                if m:
                    current["is_a"].append(m.group(1))
            elif line.startswith("relationship: part_of UBERON:") and current is not None:
                m = re.match(r"relationship: part_of\s+(UBERON:\d+)", line)
                if m:
                    current["part_of"].append(m.group(1))
            elif line == "":
                if current and current.get("id"):
                    terms[current["id"]] = current
                current = None
    if current and current.get("id"):
        terms[current["id"]] = current
    return terms


def _load_czi_leaves(labels_path: Path = DEFAULT_UBERON_LABELS) -> tuple[str, ...]:
    if not labels_path.exists():
        return tuple()
    out: list[str] = []
    with labels_path.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0].startswith("UBERON:"):
                out.append(parts[0])
    return tuple(out)


def _ancestors(terms: dict[str, dict], ub_id: str) -> set[str]:
    """``is_a`` ancestors only — NOT ``part_of``. ``is_a`` gives true
    "is a kind of" subtype relations (prostate gland is_a accessory
    male sex gland), which are what we want for organ rollup.
    ``part_of`` gives compositional containment ("prostate is part of
    male reproductive system"); walking those would push us up to
    organ SYSTEM terms (developmental, regional, structural concepts
    like "endoderm-derived structure") instead of named organs."""
    if ub_id not in terms:
        return set()
    seen = {ub_id}
    queue = [ub_id]
    while queue:
        t = queue.pop()
        rec = terms.get(t)
        if not rec:
            continue
        for p in rec["is_a"]:
            if p not in seen:
                seen.add(p)
                queue.append(p)
    return seen


def _bfs_nearest_in_range(
    terms: dict[str, dict], leaf: str, desc_count: dict[str, int], min_d: int, max_d: int
) -> str | None:
    if leaf not in terms:
        return None
    visited: set[str] = set()
    queue = [leaf]
    while queue:
        t = queue.pop(0)
        if t in visited:
            continue
        visited.add(t)
        n = desc_count.get(t, 0)
        if min_d <= n <= max_d:
            return t
        rec = terms.get(t)
        if rec:
            for p in rec["is_a"]:
                queue.append(p)
    return None


@lru_cache(maxsize=8)
def _build_organ_map(
    obo_path_str: str, labels_path_str: str, min_d: int, max_d: int
) -> dict[str, str]:
    """For each CZI leaf UBERON, find its "natural parent organ" —
    the ancestor (via is_a only) that is itself in the CZI cohort AND
    has the most cohort descendants. If no ancestor is in CZI, the
    leaf IS its own organ.

    Rationale: UBERON's is_a chain runs through conceptual ancestors
    (sense organ, gonad, ectoderm-derived structure) that aren't
    biologically useful organ labels. The right "organ" for Brodmann
    area 4 is "brain" — also in CZI cohort, parent of 96 brain
    subregions. The right organ for prostate gland is "prostate
    gland" — no CZI-cohort UBERON ancestor exists.

    The min_d/max_d parameters are unused in this design but kept in
    the signature for API stability."""
    terms = _parse_obo(obo_path_str)
    leaves = _load_czi_leaves(Path(labels_path_str))
    leaves_set = frozenset(leaves)
    # Count cohort descendants per term (used as the "size" tiebreaker
    # — pick the ancestor that gathers the most cohort coverage).
    desc_count: Counter[str] = Counter()
    for leaf in leaves:
        for a in _ancestors(terms, leaf):
            desc_count[a] += 1
    out: dict[str, str] = {}
    for leaf in leaves:
        czi_ancestors = [
            a for a in _ancestors(terms, leaf)
            if a in leaves_set and a != leaf
        ]
        if not czi_ancestors:
            # Leaf is its own organ (no CZI cohort UBERON sits above
            # it in the is_a hierarchy).
            out[leaf] = leaf
            continue
        # Pick the cohort ancestor with the most cohort descendants —
        # that's the "broadest CZI organ" this leaf sits under.
        best = max(czi_ancestors, key=lambda a: desc_count.get(a, 0))
        out[leaf] = best
    return out


def uberon_organ(uberon_id: str) -> str:
    """Return the organ-level UBERON term for a CZI tissue.

    Falls back to the organ-system category (from
    ``uberon_categories.uberon_category``) when no ancestor in
    ``[MIN_DESC, MAX_DESC]`` is found — fluid / extraembryonic /
    anatomical-region terms that don't have a "real organ" parent.
    """
    if not uberon_id:
        return uberon_category(uberon_id)
    organ_map = _build_organ_map(
        str(DEFAULT_OBO_PATH), str(DEFAULT_UBERON_LABELS), MIN_DESC, MAX_DESC
    )
    organ = organ_map.get(uberon_id)
    if organ is not None:
        return organ
    return uberon_category(uberon_id)


def uberon_organ_label(organ_id_or_category: str) -> str:
    """Resolve an organ UBERON ID to its human label. Pass-through for
    category names."""
    if not organ_id_or_category.startswith("UBERON:"):
        return organ_id_or_category
    terms = _parse_obo(str(DEFAULT_OBO_PATH))
    rec = terms.get(organ_id_or_category)
    if rec and rec.get("name"):
        return rec["name"]
    return organ_id_or_category
