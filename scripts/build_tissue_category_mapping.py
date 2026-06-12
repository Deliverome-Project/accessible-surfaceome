#!/usr/bin/env python3
"""Walk UBERON ontology → derive UBERON → organ-system category map.

Replaces the hand-curated UBERON_TO_CATEGORY mapping in
viewer/lib/tissue-categories.ts with one derived programmatically
from UBERON's `is_a` + `part_of` relations.

For each of the 14 organ-system categories, the script:
  1. Defines one or more "root" UBERON terms (e.g. "respiratory
     system" UBERON:0001004).
  2. Walks DOWN the ontology to enumerate every descendant.
  3. For every UBERON ID in CZI's tissue cell-count cache, finds
     which category root (if any) it descends from. Multi-root
     ties broken by category priority (specific > generic).

It also picks each category's "anchor" tissue — the UBERON with the
highest n_total cells in CZI — for the build's always-show list
(every gene's Tissues chart always shows these anchors even with
zero signal, so the reader can answer "is this gene in liver?"
without inferring from absence).

Outputs (overwritten on every run):
  - viewer/lib/tissue-categories-uberon-map.generated.ts
    Generated UBERON_TO_CATEGORY object replacing the hand list.
  - scripts/_tissue_category_anchors.py
    Python module the build script imports for the WHITELIST.

OBO source: http://purl.obolibrary.org/obo/uberon.obo (canonical).
Cached at /tmp/uberon.obo (~50 MB); re-download if older than 30d.

Run: uv run python scripts/build_tissue_category_mapping.py
"""
from __future__ import annotations

import os
import re
import sys
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

OBO_URL = "http://purl.obolibrary.org/obo/uberon.obo"
OBO_CACHE = Path("/tmp/uberon.obo")
OBO_MAX_AGE_DAYS = 30
TISSUE_COUNTS = Path("/tmp/czi_cell_tissue_counts.tsv")
UBERON_LABELS = Path("/tmp/uberon_to_label.tsv")

REPO_ROOT = Path(__file__).resolve().parent.parent
TS_OUT = REPO_ROOT / "viewer/lib/tissue-categories-uberon-map.generated.ts"
PY_OUT = REPO_ROOT / "scripts/_tissue_category_anchors.py"


# Preferred anchor per category — pick this UBERON over the highest-
# n_total descendant when available. Optimizes for reader recognition:
# "brain" reads more clearly than "dorsolateral prefrontal cortex"
# (which CZI happens to oversample), and the always-show panel needs
# the anatomically-default term, not the most-sampled subregion.
PREFERRED_ANCHOR_OVERRIDE: dict[str, str] = {
    "cns": "UBERON:0000955",                   # brain
    "head_sensory": "UBERON:0000970",          # eye
    "respiratory": "UBERON:0002048",           # lung
    "cardiovascular": "UBERON:0000948",        # heart
    "lymphoid": "UBERON:0000178",              # blood
    "hepatobiliary_pancreas": "UBERON:0002107",  # liver
    "digestive": "UBERON:0000160",             # intestine
    "urinary": "UBERON:0002113",               # kidney
    "endocrine": "UBERON:0002369",             # adrenal gland
    "reproductive": "UBERON:0000473",          # testis (paired anchor; could be ovary too)
    "skin_adipose": "UBERON:0002097",          # skin of body
    "musculoskeletal": "UBERON:0001134",       # skeletal muscle tissue
    "developmental": "UBERON:0000922",         # embryo
    "fluids_other": "UBERON:0000178",          # blood again — keep something recognizable
}


# Category roots — one or more UBERON IDs each category descends from.
# Priority is the LIST ORDER below: earlier categories win ties. Put
# the more specific categories first (hepatobiliary before its parent
# digestive; head_sensory before the catch-all "head & neck").
CATEGORY_ROOTS: list[tuple[str, str, list[str]]] = [
    ("cns", "CNS", [
        "UBERON:0001017",   # central nervous system
    ]),
    ("head_sensory", "Head & sensory", [
        "UBERON:0000970",   # eye
        "UBERON:0001690",   # ear
        "UBERON:0000004",   # nose
        "UBERON:0001723",   # tongue
        "UBERON:0001728",   # mouth
        "UBERON:0000974",   # neck
        "UBERON:0000033",   # head — broader, catches scalp/face
    ]),
    ("respiratory", "Respiratory", [
        "UBERON:0001004",   # respiratory system
    ]),
    ("cardiovascular", "Cardiovascular", [
        "UBERON:0004535",   # cardiovascular system
        "UBERON:0001009",   # circulatory system (parent of cardiovascular)
    ]),
    ("lymphoid", "Lymphoid & blood", [
        "UBERON:0002405",   # immune system
        "UBERON:0006558",   # lymphoid system
        "UBERON:0000178",   # blood (sometimes annotated as a tissue, not under immune)
        "UBERON:0002371",   # bone marrow (hematopoietic root)
    ]),
    # Hepatobiliary BEFORE digestive — it's a subset of digestive in
    # the ontology, so without priority it would lose to digestive.
    ("hepatobiliary_pancreas", "Hepatobiliary & pancreas", [
        "UBERON:0002423",   # hepatobiliary system
        "UBERON:0002107",   # liver (in case hepatobiliary system isn't a parent)
        "UBERON:0001264",   # pancreas
        "UBERON:0002110",   # gallbladder
    ]),
    ("digestive", "Digestive (GI)", [
        "UBERON:0001007",   # digestive system
    ]),
    ("urinary", "Urinary", [
        "UBERON:0001008",   # renal/excretory system
    ]),
    ("endocrine", "Endocrine", [
        "UBERON:0000949",   # endocrine system
    ]),
    ("reproductive", "Reproductive", [
        "UBERON:0000990",   # reproductive system
    ]),
    ("skin_adipose", "Skin & adipose", [
        "UBERON:0002416",   # integumental system (skin)
        "UBERON:0001013",   # adipose tissue
        "UBERON:0000310",   # breast (mammary gland tissue, often colocated)
    ]),
    ("musculoskeletal", "Musculoskeletal", [
        "UBERON:0002204",   # musculoskeletal system
        "UBERON:0001630",   # muscle organ — catch muscle subtypes
        "UBERON:0002385",   # muscle tissue
        "UBERON:0001134",   # skeletal muscle tissue
        # NOTE: limb / chest / abdomen are NOT included as roots even
        # though it'd catch a few more terms — they're body regions
        # and they'd sweep in unrelated structures (e.g. abdomen
        # would pull in omentum, peritoneum, and most viscera). Let
        # those regional terms fall to fluids_other.
    ]),
    ("developmental", "Developmental", [
        "UBERON:0000922",   # embryo
        "UBERON:0001987",   # placenta
        "UBERON:0007234",   # fetal organ
        "UBERON:0001040",   # yolk sac
    ]),
    # fluids_other = explicit roots for fluid terms + catch-all for the rest.
    ("fluids_other", "Fluids / other", [
        "UBERON:0006314",   # bodily fluid
        "UBERON:0001359",   # cerebrospinal fluid
        "UBERON:0001836",   # saliva
        "UBERON:0001913",   # milk
        "UBERON:0000175",   # pleural effusion
        "UBERON:0002358",   # peritoneum (serous membrane)
        "UBERON:0001366",   # parietal peritoneum
        "UBERON:0000344",   # mucosa
        "UBERON:0000030",   # lamina propria
    ]),
]


def maybe_download_obo() -> None:
    """Cache uberon.obo at /tmp/uberon.obo; refresh if older than 30 d."""
    if OBO_CACHE.exists():
        age_days = (time.time() - OBO_CACHE.stat().st_mtime) / 86400
        if age_days < OBO_MAX_AGE_DAYS:
            print(f"  using cached {OBO_CACHE} ({age_days:.0f} d old)", file=sys.stderr)
            return
        print(f"  cache stale ({age_days:.0f} d); refreshing", file=sys.stderr)
    print(f"  downloading {OBO_URL}...", file=sys.stderr)
    with urllib.request.urlopen(OBO_URL, timeout=60) as resp:
        OBO_CACHE.write_bytes(resp.read())
    size_mb = OBO_CACHE.stat().st_size / 1024 / 1024
    print(f"  cached {size_mb:.1f} MB at {OBO_CACHE}", file=sys.stderr)


def parse_obo(path: Path) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Return (id → name, id → set of parent IDs via is_a + part_of)."""
    names: dict[str, str] = {}
    parents: dict[str, set[str]] = defaultdict(set)
    re_relationship = re.compile(r"^relationship: part_of (UBERON:\d+)")
    re_is_a = re.compile(r"^is_a: (UBERON:\d+)")
    re_id = re.compile(r"^id: (UBERON:\d+)")
    re_name = re.compile(r"^name: (.+)$")
    cur_id: str | None = None
    in_term = False
    is_obsolete = False
    with path.open() as f:
        for line in f:
            line = line.rstrip("\n")
            if line == "[Term]":
                cur_id = None
                in_term = True
                is_obsolete = False
                continue
            if line.startswith("[") and line != "[Term]":
                in_term = False
                continue
            if not in_term:
                continue
            if line == "is_obsolete: true":
                is_obsolete = True
                if cur_id and cur_id in parents:
                    parents.pop(cur_id, None)
                    names.pop(cur_id, None)
                continue
            if is_obsolete:
                continue
            m = re_id.match(line)
            if m:
                cur_id = m.group(1)
                continue
            if cur_id is None:
                continue
            m = re_name.match(line)
            if m:
                names[cur_id] = m.group(1)
                continue
            m = re_is_a.match(line)
            if m:
                parents[cur_id].add(m.group(1))
                continue
            m = re_relationship.match(line)
            if m:
                parents[cur_id].add(m.group(1))
                continue
    return names, dict(parents)


def descendants_of(
    roots: list[str],
    parents: dict[str, set[str]],
) -> set[str]:
    """Walk DOWN from each root: every UBERON whose ancestor chain
    contains a root via is_a / part_of."""
    # Build child → parent map first; invert to get parent → children.
    children: dict[str, set[str]] = defaultdict(set)
    for child, ps in parents.items():
        for p in ps:
            children[p].add(child)
    seen: set[str] = set(roots)
    q = deque(roots)
    while q:
        node = q.popleft()
        for c in children.get(node, ()):
            if c in seen:
                continue
            seen.add(c)
            q.append(c)
    return seen


def load_czi_tissues() -> tuple[set[str], dict[str, int]]:
    """Return (set of UBERON IDs in CZI cache, UBERON → total cell count)."""
    uberons: set[str] = set()
    totals: dict[str, int] = defaultdict(int)
    with TISSUE_COUNTS.open() as f:
        next(f, None)  # header
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            _cl, ub, n = parts[0], parts[1], int(parts[2])
            uberons.add(ub)
            totals[ub] += n
    return uberons, dict(totals)


def load_uberon_labels_local() -> dict[str, str]:
    out: dict[str, str] = {}
    if not UBERON_LABELS.exists():
        return out
    with UBERON_LABELS.open() as f:
        next(f, None)
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
    return out


def main() -> int:
    print("Loading UBERON ontology...", file=sys.stderr)
    maybe_download_obo()
    obo_names, obo_parents = parse_obo(OBO_CACHE)
    print(f"  parsed {len(obo_names)} terms, {sum(len(v) for v in obo_parents.values())} edges", file=sys.stderr)

    print("Loading CZI tissue cache...", file=sys.stderr)
    czi_uberons, czi_totals = load_czi_tissues()
    local_labels = load_uberon_labels_local()
    print(f"  {len(czi_uberons)} distinct CZI tissues", file=sys.stderr)

    # Walk descendants for each category
    print("Walking category descendants...", file=sys.stderr)
    cat_descendants: dict[str, set[str]] = {}
    for cat_id, _label, roots in CATEGORY_ROOTS:
        desc = descendants_of(roots, obo_parents)
        cat_descendants[cat_id] = desc
        print(f"  {cat_id:25s} {len(desc):>5d} descendants from {len(roots)} root(s)", file=sys.stderr)

    # Assign each CZI UBERON to a category (priority = list order).
    assignments: dict[str, str] = {}  # uberon → cat_id
    unmapped: list[str] = []
    for ub in sorted(czi_uberons):
        matched: str | None = None
        for cat_id, _label, _roots in CATEGORY_ROOTS:
            if ub in cat_descendants[cat_id]:
                matched = cat_id
                break
        if matched is None:
            unmapped.append(ub)
            assignments[ub] = "fluids_other"
        else:
            assignments[ub] = matched

    # Print summary
    print(file=sys.stderr)
    print("Coverage:", file=sys.stderr)
    by_cat: dict[str, list[str]] = defaultdict(list)
    for ub, cat in assignments.items():
        by_cat[cat].append(ub)
    for cat_id, _label, _roots in CATEGORY_ROOTS:
        ubs = by_cat.get(cat_id, [])
        print(f"  {cat_id:25s} {len(ubs):>3d} CZI tissues", file=sys.stderr)
    print(f"  {'fluids_other (catchall)':25s} {len(by_cat.get('fluids_other', [])):>3d} CZI tissues", file=sys.stderr)
    print(f"  TOTAL                     {len(assignments):>3d}", file=sys.stderr)
    print(f"  unmapped (→ fluids_other): {len(unmapped)}", file=sys.stderr)
    if unmapped:
        for ub in unmapped[:20]:
            name = obo_names.get(ub) or local_labels.get(ub) or "?"
            print(f"      {ub:18s} {name}", file=sys.stderr)
        if len(unmapped) > 20:
            print(f"      ... and {len(unmapped)-20} more", file=sys.stderr)

    # Pick anchors: prefer the PREFERRED_ANCHOR_OVERRIDE entry if
    # it appears in CZI; otherwise fall back to highest-n_total
    # UBERON per category. The override gives recognizable common
    # names like "brain" / "heart" / "liver" instead of the
    # subregions CZI happens to oversample.
    anchors: dict[str, str] = {}
    for cat_id, _label, _roots in CATEGORY_ROOTS:
        cat_ubs = set(by_cat.get(cat_id, []))
        pref = PREFERRED_ANCHOR_OVERRIDE.get(cat_id)
        if pref and pref in cat_ubs:
            anchors[cat_id] = pref
            continue
        # Note: an override that's NOT in the descendant set is a hint
        # the category roots missed it; we accept the next-best
        # candidate but log a warning.
        if pref and pref in czi_uberons:
            print(f"  WARN: preferred anchor {pref} for {cat_id} "
                  f"not in walked descendants; using highest-n fallback",
                  file=sys.stderr)
        candidates = sorted(
            cat_ubs,
            key=lambda ub: -czi_totals.get(ub, 0),
        )
        if candidates:
            anchors[cat_id] = candidates[0]

    # Write the TypeScript generated file
    print(f"\nWriting {TS_OUT}", file=sys.stderr)
    TS_OUT.parent.mkdir(parents=True, exist_ok=True)
    ts_lines = [
        "/* AUTO-GENERATED by scripts/build_tissue_category_mapping.py. DO NOT EDIT.",
        " * Run the script to regenerate after UBERON or CATEGORY_ROOTS changes.",
        " *",
        f" * Source: {OBO_URL}",
        f" * CZI tissue universe: {len(czi_uberons)} UBERON IDs",
        f" * Category roots walked: {len(CATEGORY_ROOTS)} categories",
        " */",
        "",
        "import type { TissueCategoryId } from \"./tissue-categories\";",
        "",
        "export const GENERATED_UBERON_TO_CATEGORY: Readonly<",
        "  Record<string, TissueCategoryId>",
        "> = {",
    ]
    # Group by category for readability
    for cat_id, label, _roots in CATEGORY_ROOTS:
        ubs = sorted(by_cat.get(cat_id, []), key=lambda u: -czi_totals.get(u, 0))
        if not ubs:
            continue
        ts_lines.append(f"  // {label} — {len(ubs)} tissues")
        for ub in ubs:
            name = obo_names.get(ub) or local_labels.get(ub) or ""
            n = czi_totals.get(ub, 0)
            comment = f"  // {name} (n={n:,})" if name else f"  // n={n:,}"
            ts_lines.append(f'  "{ub}": "{cat_id}",{comment}')
    # Catch-all
    catchall = sorted(by_cat.get("fluids_other", []), key=lambda u: -czi_totals.get(u, 0))
    if catchall:
        ts_lines.append("  // Fluids / other — catch-all for unmapped")
        for ub in catchall:
            name = obo_names.get(ub) or local_labels.get(ub) or ""
            n = czi_totals.get(ub, 0)
            comment = f"  // {name} (n={n:,})" if name else f"  // n={n:,}"
            ts_lines.append(f'  "{ub}": "fluids_other",{comment}')
    ts_lines.append("} as const;")
    ts_lines.append("")
    ts_lines.append("/** One representative UBERON per category — highest-n_total in CZI. */")
    ts_lines.append("export const GENERATED_CATEGORY_ANCHORS: Readonly<")
    ts_lines.append("  Record<TissueCategoryId, string>")
    ts_lines.append("> = {")
    for cat_id, label, _roots in CATEGORY_ROOTS:
        ub = anchors.get(cat_id)
        if not ub:
            ts_lines.append(f'  // {label}: no descendants in CZI cache')
            continue
        name = obo_names.get(ub) or local_labels.get(ub) or ""
        n = czi_totals.get(ub, 0)
        ts_lines.append(f'  "{cat_id}": "{ub}",  // {name} (n={n:,})')
    # fluids_other anchor (might be empty)
    fcat = sorted(by_cat.get("fluids_other", []), key=lambda u: -czi_totals.get(u, 0))
    if fcat:
        ub = fcat[0]
        name = obo_names.get(ub) or local_labels.get(ub) or ""
        n = czi_totals.get(ub, 0)
        ts_lines.append(f'  "fluids_other": "{ub}",  // {name} (n={n:,})')
    ts_lines.append("} as const;")
    ts_lines.append("")
    TS_OUT.write_text("\n".join(ts_lines))

    # Write the Python anchors module (build script imports it)
    print(f"Writing {PY_OUT}", file=sys.stderr)
    py_lines = [
        '"""AUTO-GENERATED by scripts/build_tissue_category_mapping.py. DO NOT EDIT."""',
        "",
        "# Anchor UBERON ID per organ-system category — highest-n_total in CZI.",
        "# Build script injects these as zero-signal entries into every gene's",
        "# top_tissues, so the reader always sees the 14 organ systems even when",
        "# the gene has no expression in them.",
        "",
        "CATEGORY_ANCHORS = {",
    ]
    for cat_id, label, _roots in CATEGORY_ROOTS:
        ub = anchors.get(cat_id)
        if not ub:
            continue
        name = obo_names.get(ub) or local_labels.get(ub) or ""
        n = czi_totals.get(ub, 0)
        py_lines.append(f'    "{ub}": "{cat_id}",  # {label} → {name} (n={n:,})')
    py_lines.append("}")
    py_lines.append("")
    py_lines.append("# Flat list for the build script's whitelist injection.")
    py_lines.append("WHITELIST_TISSUES = list(CATEGORY_ANCHORS.keys())")
    py_lines.append("")
    PY_OUT.write_text("\n".join(py_lines))

    print(f"\nDONE. {len(assignments)} UBERON IDs mapped, {len(anchors)} anchors picked.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
