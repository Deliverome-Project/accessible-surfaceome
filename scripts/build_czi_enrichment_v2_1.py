#!/usr/bin/env python3
"""Build per-gene CZI CellxGene enrichment JSONs — schema v2.1.

Differences from v2.0 (``build_czi_enrichment.py``):

* **classify-first.** v2.0 ran display thresholds before classification,
  which hid signal from the classifier (CD19 ended up `low_specificity`
  because its B-cell expression was pre-filtered to two pre-B subtypes).
  v2.1 classifies on every (cl, ub) pair that passes a lenient noise
  gate (n_expressing ≥ 10, pct ≥ 1%, n_total ≥ 50). The display lists
  keep the v2.0 thresholds — only the classifier sees the broader pool.

* **dual axis.** v2.0 only classifies on cell types. v2.1 emits
  ``cell_type_enrichment`` AND ``tissue_enrichment`` (the per-tissue
  axis schema was already in the viewer's `CellxGeneEnrichment` type;
  v2.0 just never populated it). Tissues get aggregated across all CL
  terms that express in them.

* **not_detected class.** v2.0 mislabeled 3,507 genes (incl. GPR75) as
  ``low_specificity`` whenever fewer than 2 cell types passed the
  classifier filter. v2.1 splits the empty case out as
  ``not_detected`` — "no cell type meets the CZI noise threshold,"
  which reads clearly distinct from "expressed in many cell types,
  none stands out."

* **top_tissues.** v2.0 only emitted top_cell_types; the viewer's
  v2.1-aware code already expects ``top_tissues`` (rank-DESC, capped at
  the same 30-item budget as cell types). v2.1 populates it.

* **legacy mirror.** ``enrichment_class``/``enrichment_cl_ids``/
  ``fold_change`` are kept as top-level mirrors of
  ``cell_type_enrichment.*`` so v2.0-aware readers continue to work
  through the transition.

* **gene filter.** Supports ``--genes-file <path>`` (newline-separated
  symbols) to restrict output to a subset — used for the deep-dive
  test cohort (14 genes) before committing to a full-cohort re-run.

Inputs (override via env vars): same as v2.0.

  CZI_WMG_GZ           — path to CZI's `expression-summary-condensed-DD-MM-YY.csv.gz`
  CZI_TISSUE_COUNTS    — (cl_id, uberon_id, n_cells) TSV
  CZI_UBERON_LABELS    — UBERON_ID → tissue label TSV
  CZI_CL_LABELS        — CL_ID → cell-type label TSV
  CZI_OUT_DIR          — output dir for {SYMBOL}.json (default /tmp/czi_enrichment_v2_1)
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from accessible_surfaceome.audit.cl_graph import (
    cl_compartment,
)
from accessible_surfaceome.audit.cl_family import (
    cl_family,
    cl_family_label,
)
from accessible_surfaceome.audit.uberon_categories import (
    TISSUE_CATEGORIES,
    all_categories_and_uberons,
    uberon_category,
)
from accessible_surfaceome.audit.uberon_organ import (
    uberon_organ,
    uberon_organ_label,
)

WMG = Path(os.environ.get(
    "CZI_WMG_GZ",
    "/Users/rebeccacarlson/Git/tess/scripts/tool-validation/.cache/expression-summary-condensed-11-09-25.csv.gz",
))
TISSUE_COUNTS = Path(os.environ.get("CZI_TISSUE_COUNTS", "/tmp/czi_cell_tissue_counts.tsv"))
UBERON_LABELS = Path(os.environ.get("CZI_UBERON_LABELS", "/tmp/uberon_to_label.tsv"))
CL_LABELS = Path(os.environ.get("CZI_CL_LABELS", "/tmp/cl_id_to_label.tsv"))
ENS_MAP = Path(
    Path(__file__).parent.parent
    / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
)
OUT_DIR = Path(os.environ.get("CZI_OUT_DIR", "/tmp/czi_enrichment_v2_1"))
MANIFEST = OUT_DIR.parent / (OUT_DIR.name + "_manifest.tsv")
CENSUS_VERSION = "2025-11-08"
SCHEMA_VERSION = "2.1.10"

# Classifier eligibility (lenient — captures whatever has signal).
MIN_N_TOTAL_FOR_CLASS = 50
MIN_NNZ_FOR_CLASS = 10
MIN_PCT_FOR_CLASS = 0.01

# v2.1.10+ magnitude gate: even when eligibles exist, refuse to call
# enriched/enhanced if the top entity's linear pop mean is below this
# floor. τ alone is a concentration shape metric and fires 0.85+ for
# genes whose top entity is at sub-noise magnitudes (GPR75 top = 0.09,
# PVRIG = 0.29) — "enriched · X" misleads when X is barely expressed.
#
# **Calibration note: this is CP10K-derived, NOT HPA's nTPM ≥ 1.**
# Our pop_mean = expm1(mean_log1p_cp10k) × pct_expressing. CP10K is
# single-cell per-10K normalization (CZI WMG convention); HPA's nTPM
# is bulk-tissue per-million. The two scales differ by roughly ×100
# (a pop_mean of 1.0 ≈ 100 nTPM in pseudo-bulk equivalent).
#
# 1.0 was chosen empirically from the 14-gene deep-dive cohort: the
# magnitude gap between the highest demoted false positive
# (ABCB9 cell_family = 0.87) and the lowest kept canonical
# (BAX M cell of gut = 2.3) sits cleanly across this threshold.
# Single-cell noise per cell is much higher than bulk, so a stricter
# floor than the bulk-equivalent ~0.01 is required to avoid noise
# concentrating into spurious τ peaks.
#
# Below this, the classifier returns `not_detected` regardless of τ.
# Treat the value as tunable: a stricter 2.0 would demote BAX too;
# a more permissive 0.5 would re-admit SRC's tissue_organ false
# positive.
MIN_TOP_POP_MEAN = 1.0

# Broad-class axis uses a STRICTER per-leaf qualifier than the
# leaf-CL axis. A 1% pct threshold lets dozens of weakly-expressing
# leaf CL terms scatter across every broad class, swamping real
# enrichment (IZUMO4 → spermatocyte at 85% loses to a low-pct
# salivary epithelium hit because both have eligible leaves in
# different broad classes). Raising to 5% pct picks out the
# representative leaves that carry real signal.
MIN_PCT_FOR_BROAD_CLASS = 0.05

# Display thresholds (strict — only show what's worth eyeballing).
COMMON_THRESHOLD = 1000
COMMON_TOP_N = 20
RARE_TOP_N = 10
RARE_MIN_MEAN = 2.0
COMMON_MIN_MEAN = 1.0
TOP_K_TISSUES = 3
MAX_CELL_TYPES = 30
MAX_TISSUES = 30

HPA_FOLD = 4.0


# ---------- IO helpers ----------


def load_cl_labels() -> dict[str, str]:
    out: dict[str, str] = {}
    with CL_LABELS.open() as f:
        header = f.readline().rstrip("\n").split("\t")
        if header[0].startswith("cell_type") and "ontology" in header[1]:
            label_idx, id_idx = 0, 1
        elif header[0] == "cl_id":
            id_idx, label_idx = 0, 1
        else:
            id_idx = 0 if header[0].lower().startswith("cl") or "ontology" in header[0] else 1
            label_idx = 1 - id_idx
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max(id_idx, label_idx):
                continue
            out[parts[id_idx]] = parts[label_idx]
    return out


def load_uberon_labels() -> dict[str, str]:
    """Load UBERON labels from the CZI cohort cache, with OBO fallback.

    The cohort cache (``/tmp/uberon_to_label.tsv``) only covers the
    409 leaf UBERONs CZI samples. WMG annotates some cells at parent
    UBERONs (mucosa, alveolus, musculature, endocrine gland, nervous
    system, pleural fluid) which aren't in the leaf cache. Falling
    back to raw IDs like ``UBERON:0001015`` in the chart x-axis was
    the v2.1.8 bug; v2.1.9+ extends the cache with OBO names so every
    UBERON the build sees has a human label.
    """
    out: dict[str, str] = {}
    with UBERON_LABELS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
    # OBO extension — pull names for parent UBERONs not in the cohort
    # cache. We don't union ALL of UBERON (~10k terms); we lazy-extend
    # by reading the OBO and adding every term not already in the cache.
    try:
        from accessible_surfaceome.audit.uberon_organ import (
            DEFAULT_OBO_PATH,
            _parse_obo,
        )
        terms = _parse_obo(str(DEFAULT_OBO_PATH))
        for ub_id, rec in terms.items():
            if ub_id not in out and rec.get("name"):
                out[ub_id] = rec["name"]
    except Exception as e:  # pragma: no cover
        print(f"  WARN: UBERON OBO label fallback failed ({e})", file=sys.stderr)
    return out


def _cohort_leaf_cls() -> frozenset[str]:
    """Return the set of CL terms in CZI's cell-count cache that have
    no DESCENDANTS that are also in the cohort. Each cell in CZI is
    annotated at its leaf CL plus every ancestor in the WMG output;
    counting/aggregating only over cohort-leaves recovers each cell
    exactly once (no parent+child double-count)."""
    cohort: set[str] = set()
    with TISSUE_COUNTS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 1 and parts[0].startswith("CL:"):
                cohort.add(parts[0])
    try:
        from accessible_surfaceome.audit.cl_graph import _load_dag, DEFAULT_OBO_PATH
        dag = _load_dag(str(DEFAULT_OBO_PATH))
        has_cohort_descendant: set[str] = set()
        for cl in cohort:
            if cl not in dag:
                continue
            for child in dag[cl].children:
                if child.id in cohort:
                    has_cohort_descendant.add(cl)
                    break
        return frozenset(cohort - has_cohort_descendant)
    except Exception as e:  # pragma: no cover
        print(f"  WARN: cohort-leaf detection failed ({e})", file=sys.stderr)
        return frozenset(cohort)


def load_tissue_counts() -> tuple[dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
    """Return (cl,uberon)->n, cl->n_total_across_tissues, uberon->n_total_across_celltypes.

    **Per-UBERON cell-union count via leaf-CL filter (v2.1.6).**

    The previous v2.1.x ``ub_total = sum(pair_counts[(cl, ub)] for cl)``
    double-counted cells when CZI's WMG annotates the same cells
    under multiple CL terms (parent + child). CD63-pancreas was the
    canonical case: raw pct landed at 154% and the chart had to clamp
    to 100%.

    Fix: identify the **leaf CL terms** in the CZI cohort (CL terms
    with no descendants that are also in the cohort) and sum
    ``pair_counts[(cl, ub)]`` only over those. The CZI Census tags
    every cell at its leaf CL annotation plus every CL ancestor in
    the WMG output; counting only the leaf level recovers each cell
    exactly once.

    Note: ``cl_total`` (sum across tissues per CL) stays as-is —
    that's the right denominator for the per-CL axis (the leaf-CL
    axis classifier uses it for the same gene's pct on a CL term).

    Falls back gracefully if the CL ontology can't be loaded — uses
    the old sum-across-all-CL behavior and logs a warning. Older
    builds without the cohort-leaf filter clamp pct at 100%, which
    the chart still does as a defensive measure.
    """
    pair: dict[tuple[str, str], int] = {}
    cl_total: dict[str, int] = defaultdict(int)
    ub_per_cl: dict[str, dict[str, int]] = defaultdict(dict)
    with TISSUE_COUNTS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            cl, ub, n = parts[0], parts[1], int(parts[2])
            pair[(cl, ub)] = n
            cl_total[cl] += n
            ub_per_cl[ub][cl] = n
    # Sum only over cohort-leaf CL pairs to count each cell once.
    cohort_leaves = _cohort_leaf_cls()
    if cohort_leaves:
        ub_total: dict[str, int] = {}
        for ub, cls_dict in ub_per_cl.items():
            ub_total[ub] = sum(
                n for cl, n in cls_dict.items() if cl in cohort_leaves
            )
        # Empty cohort-leaf sum (no leaves in this UBERON) → fall back
        # to max-CL count (lower bound).
        for ub, total in list(ub_total.items()):
            if total == 0 and ub in ub_per_cl:
                ub_total[ub] = max(ub_per_cl[ub].values())
    else:
        ub_total = {ub: sum(d.values()) for ub, d in ub_per_cl.items()}
    return pair, dict(cl_total), ub_total


def load_ens_map() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    with ENS_MAP.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sym = row.get("gene_symbol") or ""
            hgnc = row.get("hgnc_id") or ""
            ens_field = row.get("ensembl_gene") or ""
            if not ens_field:
                continue
            for ens in ens_field.replace(";", "|").split("|"):
                ens = ens.strip()
                if ens and ens.startswith("ENSG") and ens not in out:
                    out[ens] = (sym, hgnc)
    return out


# ---------- HPA classification ----------


def classify_hpa(
    entities: dict[str, float],          # entity_id -> LINEAR population mean (mean × pct, ≈ nTPM)
    n_totals: dict[str, int],            # entity_id -> n_total (full universe)
) -> tuple[str, list[str], float | None, list[tuple[str, float, float]]]:
    """Classify by τ cutoffs on linear population mean.

    Returns ``(class, entity_ids, fold_change, top_entity_contribs)``.
    ``class`` is one of ``not_detected | enriched | enhanced |
    low_specificity``. ``entity_ids`` carries the top-ranked entities
    by linear pop mean (1-3 entries — the chip's "in {entities}"
    list). ``fold_change`` is top-vs-next-ranked ratio
    (informational). ``top_entity_contribs`` is a list of
    ``(entity_id, pop_mean, per_entity_tau_contribution)`` tuples
    for the top 3 — used to render the multi-entity tooltip with
    per-entity numbers.

    **τ cutoffs (NOT HPA).** HPA's discrete tissue-specificity
    classification uses a 4× fold-change rule on nTPM
    (https://www.proteinatlas.org/humanproteome/tissue/tissue+specific).
    We do NOT follow HPA's discrete scheme — we use Yanai 2005 τ
    cutoffs derived from the Kryuchkova-Mostacci & Robinson-Rechavi
    2017 benchmark (which crowned τ best-in-class with τ ≥ 0.8) and
    the τ ≥ 0.85 idiom (Lüleci & Yılmaz 2022):

        τ ≥ 0.85   → enriched
        0.5 ≤ τ < 0.85 → enhanced
        τ < 0.5    → low_specificity

    Single-eligible edge case is enriched by definition. Zero
    eligibles → not_detected.

    **v2.1.10+ magnitude gate.** ``MIN_TOP_POP_MEAN`` is a CP10K-
    derived floor calibrated to the 14-gene deep-dive cohort (NOT
    a direct port of HPA's bulk nTPM ≥ 1; the scales differ by
    ~100×). A gene whose top eligible has pop_mean below this floor
    falls to ``not_detected`` regardless of τ — "enriched at
    concentration zero" is misleading. Fixes ABCB9 / GPR75 / PVRIG
    false-positive `enriched` calls where the top entity sits at
    sub-noise magnitudes.

    **τ universe = full measured set + noise floor.** Yanai 2005 and
    Kryuchkova-Mostacci 2017 always floor low intensities rather
    than dropping entities; HPA likewise uses a fixed 37-tissue
    universe with nTPM ≥ 1 floor; Tabula Sapiens 2.0 fixes N = 175
    cell types. See compute_tau docstring.
    """
    # Eligible entities (above noise) ranked by linear pop mean.
    eligible = sorted(
        (
            (k, v)
            for k, v in entities.items()
            if n_totals.get(k, 0) >= MIN_N_TOTAL_FOR_CLASS
        ),
        key=lambda kv: kv[1],
        reverse=True,
    )

    def _top_contribs(
        top_ids: list[str], x_max: float
    ) -> list[tuple[str, float, float]]:
        """Per-entity (id, pop_mean, tau_contribution) for the chip
        tooltip. tau_contribution = (1 − x/x_max) — the entity's own
        contribution to the τ sum, intuitive as "how much this entity
        adds to the specificity score." For the top entity it's 0
        (x = x_max), for entities at the floor it's near 1."""
        out: list[tuple[str, float, float]] = []
        emap = dict(eligible)
        for k in top_ids:
            v = emap.get(k, TAU_NOISE_FLOOR)
            contrib = 1.0 - (v / x_max) if x_max > 0 else 0.0
            out.append((k, v, contrib))
        return out

    if len(eligible) == 0:
        return "not_detected", [], None, []

    # Magnitude gate: top eligible must clear MIN_TOP_POP_MEAN
    # (≈ HPA's nTPM ≥ 1 detection floor) for any concentrated/elevated
    # call. Otherwise the gene is essentially not detected at an
    # interesting level anywhere — τ-based concentration is misleading.
    x_max_check = eligible[0][1]
    if x_max_check < MIN_TOP_POP_MEAN:
        return "not_detected", [], None, []

    if len(eligible) == 1:
        return "enriched", [eligible[0][0]], float("inf"), _top_contribs(
            [eligible[0][0]], eligible[0][1]
        )

    linear = [v for _, v in eligible]
    ids = [k for k, _ in eligible]
    x_max = linear[0]

    # τ over the full universe with noise floor — see compute_tau.
    tau = compute_tau(entities, n_totals)
    if tau is None:
        return "not_detected", [], None, []

    # Fold = top vs next-ranked (companion to τ, not class-determining).
    fold: float | None
    if linear[1] > 0:
        fold = linear[0] / linear[1]
    else:
        fold = float("inf")

    # τ cutoffs: Yanai 2005 + Kryuchkova-Mostacci 2017; 0.85 idiom
    # from Lüleci & Yılmaz 2022.
    if tau >= 0.85:
        # Up to 3 top entities by pop mean for the chip's "in {ents}"
        # line + the per-entity tooltip — restrict to entities within
        # 50% of the top so we don't list weakly-contributing ones.
        top_ids = [k for k, v in eligible if v >= 0.5 * x_max][:3]
        if not top_ids:
            top_ids = [ids[0]]
        return "enriched", top_ids, fold, _top_contribs(top_ids, x_max)
    if tau >= 0.5:
        top_ids = [ids[0]]
        return "enhanced", top_ids, fold, _top_contribs(top_ids, x_max)
    return "low_specificity", [], fold, []


TAU_NOISE_FLOOR = 0.001
"""Linear pop-mean floor for ineligible entities in τ.

Yanai 2005 explicitly noise-floored low intensities (`set log10(30) for
all intensities below log10(30)`); Kryuchkova-Mostacci 2017 likewise
floored expression at 1 RPKM. The floor — not removal of ineligibles
— is the canonical universe choice for τ in tissue-specificity work.

Our floor: 0.001 linear pop mean ≈ a gene expressed at mean log1p(CP10K)
≈ 0.1 in 1% of cells. Below the noise gate, but not zero — keeps τ
in a meaningful range when many entities sit at sub-noise levels."""


def compute_tau(
    entities: dict[str, float],
    n_totals: dict[str, int],
) -> float | None:
    """Yanai 2005 τ over the FULL measured universe with a noise floor.

    τ = Σ (1 − x_i / x_max) / (N − 1), where x_i is the linear
    population-mean expression of entity i ∈ universe.

    ``entities`` carries the linear population mean per ELIGIBLE
    entity (above the noise gate). ``n_totals`` carries n_total for
    every entity in the universe — including ineligibles. Ineligibles
    contribute ``TAU_NOISE_FLOOR`` to the τ sum (Yanai 2005 floor,
    Kryuchkova-Mostacci 2017 confirmation — they always floor low
    intensities rather than dropping entities, so a fixed N keeps τ
    cross-gene comparable).

    Why over the full universe (not eligibles-only): Yanai 2005,
    Kryuchkova-Mostacci 2017, HPA's tissue-specificity proteome, and
    Tabula Sapiens 2.0 all keep N fixed by flooring low values rather
    than removing entities below detection. Eligibles-only τ collapses
    to "concentration among entities that express the gene" which is a
    different question and isn't cross-gene comparable.

    Returns:
        τ ∈ [0, 1], or ``None`` when fewer than 2 universe entities
        or x_max <= floor (gene effectively unmeasured everywhere).

    Field references:
        * Yanai et al. 2005, *Bioinformatics* (PMID 15388519) —
          original τ; uses fixed N with noise floor.
        * Kryuchkova-Mostacci & Robinson-Rechavi 2017, *Brief.
          Bioinformatics* (PMID 26891983) — τ best-in-class
          benchmark; <1 RPKM floor.
        * Lüleci & Yılmaz 2022, *BioData Mining* — τ ≥ 0.85 cutoff
          for "specific" expression.
        * HPA tissue-specific page (37-tissue universe + nTPM ≥ 1
          floor).
        * Tabula Sapiens 2.0 (bioRxiv 2024.12.03.626516) — τ > 0.85
          over fixed 175-cell-type universe.
    """
    linear: list[float] = []
    for k, n_total in n_totals.items():
        if n_total < MIN_N_TOTAL_FOR_CLASS:
            continue
        v = entities.get(k)
        if v is None or v < TAU_NOISE_FLOOR:
            linear.append(TAU_NOISE_FLOOR)
        else:
            linear.append(v)
    n = len(linear)
    if n < 2:
        return None
    x_max = max(linear)
    if x_max <= TAU_NOISE_FLOOR:
        return None
    return sum(1.0 - x / x_max for x in linear) / (n - 1)


def fold_change_payload(fold: float | None) -> tuple[float | None, bool]:
    """Serialize fold_change to (value, infinite_flag) for JSON encoding.
    JSON doesn't support inf — we write null + a sibling boolean."""
    if fold is None:
        return None, False
    if math.isinf(fold):
        return None, True
    return round(fold, 3), False


def serialize_contribs(
    contribs: list[tuple[str, float, float]],
    label_fn,
    sub_label_fn=None,
) -> list[dict]:
    """Convert classify_hpa's top_entity_contribs to JSON-friendly dicts.

    Each tuple ``(entity_id, pop_mean, tau_contribution)`` becomes
    ``{"id", "label", "pop_mean", "tau_contrib"}``. ``label_fn`` is a
    per-axis resolver (e.g. ``cl_labels.get`` for leaf CL, ``cl_family_label``
    for the family axis). The viewer reads these to render the
    multi-entity tooltip with per-entity τ contributions.

    ``sub_label_fn`` is optional and resolves the entity id to the
    label of the leaf that the rollup signal actually rests on. The
    cell-family axis sets it to ``cl_labels.get(family_top_cl[fid])``
    so the chip can read "extraembryonic cell (placental villous
    trophoblast)" instead of just "extraembryonic cell". The
    tissue-organ axis does the same for the underlying top UBERON.
    Skipped when None or when the sub-label matches the label
    (so single-leaf families don't render "X (X)").
    """
    out: list[dict] = []
    for entity_id, pop_mean, tau_contrib in contribs:
        label = label_fn(entity_id) if entity_id else ""
        row = {
            "id": entity_id,
            "label": label,
            "pop_mean": round(pop_mean, 4),
            "tau_contrib": round(tau_contrib, 4),
        }
        if sub_label_fn is not None and entity_id:
            sub = sub_label_fn(entity_id) or ""
            if sub and sub != label:
                row["sub_label"] = sub
        out.append(row)
    return out


def classify_and_score(
    pop_linear: dict[str, float],
    n_total_universe: dict[str, int],
    label_fn,
    sub_label_fn=None,
):
    """Run classify_hpa + compute_tau + fold_change_payload +
    serialize_contribs in one call.

    Returns ``(class, ids, fold_val, fold_inf, tau, contribs)``.
    Threads ``sub_label_fn`` through to ``serialize_contribs`` so a
    rollup axis (cell_family, tissue_organ) can render the underlying
    leaf the signal rests on in the chip tooltip.
    """
    klass, ids, fold, contribs = classify_hpa(pop_linear, n_total_universe)
    tau = compute_tau(pop_linear, n_total_universe)
    fold_val, fold_inf = fold_change_payload(fold)
    return klass, ids, fold_val, fold_inf, tau, serialize_contribs(
        contribs, label_fn, sub_label_fn
    )


# ---------- per-gene build ----------


def build_record(
    symbol: str,
    hgnc: str,
    ensembl_gene: str,
    cl_to_uberon: dict[str, dict[str, list[float]]],
    cl_labels: dict[str, str],
    uberon_labels: dict[str, str],
    pair_counts: dict[tuple[str, str], int],
    cl_total_counts: dict[str, int],
    ub_total_counts: dict[str, int],
) -> dict:
    # ---- Per-CL pooled across all tissues ----
    # Two parallel dicts: ``cl_means_log`` keeps the among-expressors
    # log1p mean (kept on the record's display rows so a reader can
    # cross-check against cellxgene viewer values). ``cl_pop_linear``
    # is the LINEAR population mean (≈ nTPM) — what the classifier and
    # τ consume.
    cl_means_log: dict[str, float] = {}
    cl_pop_linear: dict[str, float] = {}
    cl_n_total_for_class: dict[str, int] = {}
    cl_n_expressing: dict[str, int] = {}
    cl_n_total_display: dict[str, int] = {}

    for cl, ub_to_stats in cl_to_uberon.items():
        tot_nnz = sum(v[0] for v in ub_to_stats.values())
        tot_sum = sum(v[1] for v in ub_to_stats.values())
        if tot_nnz <= 0:
            continue
        n_total = cl_total_counts.get(cl, 0)
        if n_total <= 0:
            continue
        mean_log = tot_sum / tot_nnz
        cl_n_expressing[cl] = int(tot_nnz)
        cl_n_total_display[cl] = n_total
        pct = tot_nnz / n_total
        # Classifier-eligible: passes noise gate.
        if tot_nnz >= MIN_NNZ_FOR_CLASS and pct >= MIN_PCT_FOR_CLASS:
            cl_means_log[cl] = mean_log
            cl_pop_linear[cl] = math.expm1(mean_log) * pct
            cl_n_total_for_class[cl] = n_total

    # Full leaf-CL universe: ineligibles floor at 1e-3 inside τ via
    # the universe-stable noise floor (Yanai 2005 convention).
    cl_class, cl_ids, cl_fold_val, cl_fold_inf, cl_tau, cl_contribs = (
        classify_and_score(
            cl_pop_linear,
            cl_total_counts,
            lambda i: cl_labels.get(i, i),
        )
    )

    # ---- Broad cell class rollup ----
    # HPA's 4× test was designed for ~40 broad tissues. cellxgene has
    # 600+ leaf CL terms; well-known markers (CD19 across B-cell
    # subtypes, KLK2 in 2 prostate luminal subtypes) end up
    # low_specificity because no single CL term dominates the
    # next-ranked sibling 4×. Roll each leaf CL up to one of ~10
    # compartments (Epithelial / Immune / Neural / Endothelial /
    # Stromal / Muscle / Reproductive / Stem / Tumor / Other) via the
    # keyword rules in accessible_surfaceome.audit.cl_broad_classes.
    #
    # **Signal = max-qualified-leaf, not aggregate.** Two failure
    # modes ruled-out earlier:
    #   - **Aggregate by sum** dilutes tissue-restricted signal — KLK2
    #     expressing in 17k prostate luminal cells gets numerator 17k,
    #     denominator millions of Epithelial cells across the genome,
    #     pct → ~1%. KLK2 falsely reads not_detected.
    #   - **Any-leaf passes, mean by nnz-weighted average** brings KLK2
    #     back but adds noise — every broad class with any weak leaf
    #     qualifier becomes eligible, IZUMO4 (testis-Reproductive)
    #     gets shadowed by Immune-because-some-thymocyte-passes.
    #
    # The fix: broad-class signal = mean of its STRONGEST qualified
    # leaf. Each class competes via its best representative. KLK2's
    # Epithelial is luminal prostate (mean=3.7); IZUMO4's
    # Reproductive is spermatocyte (mean=2.6); each gene's enrichment
    # signal stays grounded in its real CL biology.
    class_max_leaf_mean: dict[str, float] = {}  # LINEAR pop mean per broad class
    for cl, ub_to_stats in cl_to_uberon.items():
        bc = cl_compartment(cl)
        tot_nnz = sum(v[0] for v in ub_to_stats.values())
        tot_sum = sum(v[1] for v in ub_to_stats.values())
        n_total_cl = cl_total_counts.get(cl, 0)
        if tot_nnz <= 0 or n_total_cl <= 0:
            continue
        pct_leaf = tot_nnz / n_total_cl
        if tot_nnz < MIN_NNZ_FOR_CLASS or pct_leaf < MIN_PCT_FOR_BROAD_CLASS:
            continue
        mean_log = tot_sum / tot_nnz
        # Linear population mean for this leaf (≈ nTPM).
        leaf_pop_linear = math.expm1(mean_log) * pct_leaf
        prev = class_max_leaf_mean.get(bc, -math.inf)
        if leaf_pop_linear > prev:
            class_max_leaf_mean[bc] = leaf_pop_linear

    # n_total per broad class = sum of leaf n_totals (for the
    # zero-baseline universe count). Walks every CL so the universe
    # is the FULL broad-class set, even classes this gene has no
    # signal in.
    class_n_total_summed: dict[str, int] = defaultdict(int)
    for cl, n_total in cl_total_counts.items():
        bc = cl_compartment(cl)
        class_n_total_summed[bc] += n_total

    class_class, class_ids, class_fold_val, class_fold_inf, class_tau, class_contribs = (
        classify_and_score(
            class_max_leaf_mean,
            class_n_total_summed,
            lambda i: i,  # broad classes are already labels
        )
    )

    # ---- Cell-FAMILY axis (middle granularity, ~150 terms) ----
    # Between leaf CL (~600, where the 4× rule rarely fires) and the
    # 10 broad compartments. The family is the leaf CL's nearest
    # ancestor with 6-40 CZI cohort descendants — programmatic walk
    # via cl_family.py. Signal aggregation matches the broad-class
    # axis: max-pop-mean leaf within each family. Family of one cell
    # type IS that cell type — so the family axis converges to the
    # leaf for fine-grained CL terms with few siblings.
    family_max_leaf_mean: dict[str, float] = {}
    family_top_cl: dict[str, str] = {}
    family_n_total_universe: dict[str, int] = {}
    # Family universe: every cl in cl_total_counts contributes its
    # n_total to its family's denominator (for the zero baseline).
    for cl, n_total in cl_total_counts.items():
        fam = cl_family(cl, cl_labels.get(cl, ""))
        family_n_total_universe[fam] = family_n_total_universe.get(fam, 0) + n_total
    for cl, pop in cl_pop_linear.items():
        fam = cl_family(cl, cl_labels.get(cl, ""))
        if pop > family_max_leaf_mean.get(fam, -math.inf):
            family_max_leaf_mean[fam] = pop
            family_top_cl[fam] = cl

    family_class, family_ids, family_fold_val, family_fold_inf, family_tau, family_contribs = (
        classify_and_score(
            family_max_leaf_mean,
            family_n_total_universe,
            cl_family_label,
            # Underlying leaf CL the family signal rests on — the chip
            # tooltip surfaces this so a reader sees "extraembryonic
            # cell (placental villous trophoblast)" not just the
            # family label.
            lambda fid: cl_labels.get(family_top_cl.get(fid, ""), ""),
        )
    )
    family_labels = [cl_family_label(fid) for fid in family_ids]
    family_top_cl_labels = [
        cl_labels.get(family_top_cl.get(fid, ""), "") for fid in family_ids
    ]

    # ---- Per-UBERON pooled across all cell types ----
    # Aggregate ONLY across cohort-leaf CL terms so each cell is counted
    # exactly once. CZI's WMG annotates every cell at its leaf CL plus
    # each CL ancestor; summing without the leaf filter double-counts
    # cells under their parent + grandparent annotations and inflates
    # both numerator (nnz) and denominator (n_total). CD63-pancreas raw
    # pct was 154% under the old all-CL sum; the leaf-CL filter brings
    # numerator and denominator to a consistent count.
    # **pct via weighted-mean-of-per-(cl, ub) pcts (v2.1.7+).** Each
    # per-(cl, ub) pct is sane by construction: nnz / n_total_pair with
    # the WMG-nnz fallback ensuring pct ≤ 1.0 at the pair level. Take
    # the weighted mean across leaf CLs in each UBERON (weights =
    # n_total_pair) to get a per-UBERON pct that never needs clipping.
    # Equivalent to SUM(nnz_leaf) / SUM(n_total_leaf_with_fallback) —
    # avoids the previous all-CL sum that overcounted via parent CL
    # hierarchy and required clamping to 100%.
    # **v2.1.9+ clean-only per-UBERON aggregation.**
    # The cell-count cache (``/tmp/czi_cell_tissue_counts.tsv``) is
    # dramatically stale for some (cl, ub) pairs vs the 2025-11-08
    # WMG (cardiac fibroblast in heart: cache=466, WMG nnz=127,804).
    # Previous versions clipped stale-pair pct to 100% via WMG-nnz
    # fallback, which over-inflated per-UBERON pct (EGFR-heart hit
    # 97.5% via the ceiling artifact). v2.1.9 drops stale pairs from
    # the per-UBERON aggregation entirely — keep only (cl, ub) where
    # the cache n_total ≥ WMG nnz. Per-UBERON pop_mean is computed
    # purely from clean pairs.
    #
    # Consequences:
    #   * Tissues whose top-coverage cells (cardiac fibroblast in
    #     heart, alveolar T2 in lung, hepatocyte in liver) are all
    #     stale lose their dominant signal in the aggregate. The
    #     remaining clean pairs (smaller cell types) drive the
    #     per-UBERON pop_mean.
    #   * Tissues where the gene's true signal is in cells that the
    #     cache covers cleanly (placenta-trophoblast, gonad-germ
    #     cell, prostate-basal) keep their full signal.
    #   * Some canonical tissues will drop from the chip ranking
    #     (LRP2-kidney if proximal tubule is the only clean pair
    #     and pct-fail the noise gate). Documented as a known
    #     limitation pending cache regeneration.
    cohort_leaves = _cohort_leaf_cls()
    ub_means_log: dict[str, float] = {}
    ub_pop_linear: dict[str, float] = {}
    ub_pooled: dict[str, dict[str, float]] = {}
    # Track stale-fraction for the is_stale_denominator display flag.
    ub_stale_observed_nnz: dict[str, float] = {}
    ub_total_observed_nnz: dict[str, float] = {}
    for cl, ub_to_stats in cl_to_uberon.items():
        if cohort_leaves and cl not in cohort_leaves:
            continue
        for ub, vals in ub_to_stats.items():
            nnz, ssum = vals
            if nnz <= 0:
                continue
            cache_n = pair_counts.get((cl, ub), 0)
            is_stale_pair = cache_n < int(nnz)
            # Track stale fraction across ALL observed pairs (clean
            # + stale) so the display flag reflects what the cache
            # is missing for this tissue.
            ub_total_observed_nnz[ub] = ub_total_observed_nnz.get(ub, 0.0) + nnz
            if is_stale_pair:
                ub_stale_observed_nnz[ub] = ub_stale_observed_nnz.get(ub, 0.0) + nnz
                continue  # drop from aggregation
            if cache_n <= 0:
                continue
            slot = ub_pooled.setdefault(ub, {
                "nnz": 0.0, "sum": 0.0, "n_total_leaf": 0.0,
            })
            slot["nnz"] += nnz
            slot["sum"] += ssum
            slot["n_total_leaf"] += cache_n
    ub_n_total_for_class: dict[str, int] = {}
    ub_n_expressing: dict[str, int] = {}
    ub_n_total_display: dict[str, int] = {}
    ub_stale_fraction: dict[str, float] = {}
    STALE_FLAG_THRESHOLD = 0.5
    for ub, st in ub_pooled.items():
        nnz = st["nnz"]
        n_total_leaf = st["n_total_leaf"]
        if nnz <= 0 or n_total_leaf <= 0:
            continue
        n_total = int(n_total_leaf)
        mean_log = st["sum"] / nnz
        ub_n_expressing[ub] = int(nnz)
        ub_n_total_display[ub] = n_total
        pct = nnz / n_total
        # stale-fraction is computed across all observed pairs (clean
        # + stale) so the display flag reflects how much of the
        # tissue's WMG signal the clean-only aggregate is missing.
        total_obs = ub_total_observed_nnz.get(ub, 0.0)
        ub_stale_fraction[ub] = (
            ub_stale_observed_nnz.get(ub, 0.0) / total_obs if total_obs > 0 else 0.0
        )
        if nnz < MIN_NNZ_FOR_CLASS or pct < MIN_PCT_FOR_CLASS:
            continue
        ub_means_log[ub] = mean_log
        ub_pop_linear[ub] = math.expm1(mean_log) * pct
        ub_n_total_for_class[ub] = n_total

    # Pass the full UBERON universe (every tissue with n_total >=
    # MIN_N_TOTAL_FOR_CLASS) so the zero-baseline kicks in for
    # tissues without this gene's signal. Classifier + τ both
    # operate on LINEAR population mean (≈ nTPM).
    ub_class, ub_ids, ub_fold_val, ub_fold_inf, ub_tau, ub_contribs = (
        classify_and_score(
            ub_pop_linear,
            ub_total_counts,
            lambda u: uberon_labels.get(u, u),
        )
    )

    # ---- Tissue-CATEGORY axis (14 organ-system rollup) ----
    # HPA's 4× rule was designed for ~40 broad tissues. CZI emits 410
    # fine-grained UBERONs (96 brain subregions alone — Brodmann areas,
    # cortical layers, etc.). Aggregating to 14 organ-system categories
    # collapses GPR75's brain signal scattered across many subregions
    # back into a single CNS bucket, matches HPA's original ~40-tissue
    # design, and lets τ run on a sensibly-sized axis. UBERON →
    # category map is the programmatic ontology-walk output at
    # viewer/lib/tissue-categories-uberon-map.generated.ts
    # (build script: scripts/build_tissue_category_mapping.py).
    #
    # **Signal = max UBERON pop mean within category, NOT sum.** Two
    # failure modes ruled out:
    #   - Sum-across-category dilutes: aggregate nnz across the
    #     category's UBERONs vs aggregate n_total (which grows much
    #     faster — CNS sums to 25M cells across 96 subregions).
    #     GPR75's 20k brain cells over 25M denominator → 0.08% pct,
    #     fails the noise gate. False-negative.
    #   - Sum-of-pop-means double-counts: each UBERON's pop_mean is
    #     already a per-cell-of-tissue average; summing isn't a
    #     meaningful aggregate.
    # Max-UBERON-per-category matches the broad-CL approach: each
    # category competes via its strongest tissue. GPR75's CNS =
    # brain's pop mean (0.13). Cleanly above the noise gate.
    cat_to_ubs = all_categories_and_uberons()
    cat_pop_linear: dict[str, float] = {}    # category -> max linear pop mean
    cat_n_total_universe: dict[str, int] = {}  # category -> sum of UBERON n_totals
    cat_top_ub: dict[str, str] = {}          # category -> UBERON ID of the winning leaf
    for cat in TISSUE_CATEGORIES:
        cat_n_total_universe[cat] = sum(
            ub_total_counts.get(u, 0) for u in cat_to_ubs.get(cat, [])
        )
    for ub, pop in ub_pop_linear.items():
        cat = uberon_category(ub)
        if pop > cat_pop_linear.get(cat, -math.inf):
            cat_pop_linear[cat] = pop
            cat_top_ub[cat] = ub

    cat_class, cat_ids, cat_fold_val, cat_fold_inf, cat_tau, cat_contribs = (
        classify_and_score(
            cat_pop_linear,
            cat_n_total_universe,
            lambda c: c,  # categories are already labels
            # Underlying winning UBERON within the category — GPR75
            # CNS → "brain", KLK2 reproductive → "prostate gland".
            lambda c: uberon_labels.get(cat_top_ub.get(c, ""), ""),
        )
    )
    # Resolve category IDs to the underlying winning tissue label —
    # e.g. CNS → brain — so the chip shows the tissue the category
    # signal rests on.
    cat_top_tissues = [
        uberon_labels.get(cat_top_ub.get(c, ""), "") for c in cat_ids
    ]

    # ---- Tissue-ORGAN axis (middle granularity, ~150 terms) ----
    # Between leaf UBERON (~410, brain fragments across 96 subregions)
    # and the 13 organ-system categories. The organ is the leaf
    # UBERON's nearest ancestor with 4-30 CZI cohort descendants —
    # programmatic walk via uberon_organ.py. Signal aggregation
    # matches the tissue-category axis: max-pop-mean UBERON within
    # each organ.
    organ_max_leaf_mean: dict[str, float] = {}
    organ_top_ub: dict[str, str] = {}
    organ_n_total_universe: dict[str, int] = {}
    for ub, n_total in ub_total_counts.items():
        organ = uberon_organ(ub)
        organ_n_total_universe[organ] = organ_n_total_universe.get(organ, 0) + n_total
    for ub, pop in ub_pop_linear.items():
        organ = uberon_organ(ub)
        if pop > organ_max_leaf_mean.get(organ, -math.inf):
            organ_max_leaf_mean[organ] = pop
            organ_top_ub[organ] = ub

    organ_class, organ_ids, organ_fold_val, organ_fold_inf, organ_tau, organ_contribs = (
        classify_and_score(
            organ_max_leaf_mean,
            organ_n_total_universe,
            uberon_organ_label,
            # Underlying leaf UBERON the organ signal rests on.
            lambda oid: uberon_labels.get(organ_top_ub.get(oid, ""), ""),
        )
    )
    organ_labels = [uberon_organ_label(oid) for oid in organ_ids]
    organ_top_ub_labels = [
        uberon_labels.get(organ_top_ub.get(oid, ""), "") for oid in organ_ids
    ]

    # ---- Reverse cells_by_tissue map ----
    # The viewer's tissue cross-filter clicks a tissue bar and shows
    # "cell types in {tissue}". Without this reverse map, the viewer
    # falls back to walking each cell type's truncated top-3 tissues
    # array, which misses cell types whose pooled mean is too low to
    # make the top_cell_types cap (e.g. embryo signal sits in many
    # cell types each at moderate pop mean — none lands in top 30
    # globally but many show up if you ask "what's in embryo?").
    #
    # **WMG nnz fallback** (per 4f4a51a05): when the cell-count cache
    # says fewer cells than WMG saw, the cache is stale; use WMG nnz
    # as the denominator and flag is_uncertain so the viewer can
    # render distinctly. This is what fixes "No cell types in embryo"
    # — embryo has 28k EGFR-expressing cells in WMG that the cache
    # didn't see, so they were getting dropped at the n_total_pair < 50
    # gate.
    CELLS_BY_TISSUE_PER_TISSUE_CAP = 20
    cells_by_tissue: dict[str, list[dict]] = {}
    for cl, ub_to_stats in cl_to_uberon.items():
        for ub, (nnz, ssum) in ub_to_stats.items():
            if nnz <= 0:
                continue
            cache_n = pair_counts.get((cl, ub), 0)
            # v2.1.9: drop stale pairs from display entirely (same as
            # per-UBERON aggregation). Showing a 100% pct ceiling for
            # a stale pair misleads — the cache simply doesn't know
            # the real n_total.
            if cache_n < int(nnz) or cache_n <= 0:
                continue
            cell_pct = nnz / cache_n
            cells_by_tissue.setdefault(ub, []).append({
                "cl_id": cl,
                "cell_type": cl_labels.get(cl, cl),
                "mean_log1p_cp10k": round(ssum / nnz, 4),
                "n_expressing": int(nnz),
                "n_total": int(cache_n),
                "pct_expressing": round(cell_pct, 4),
                "is_trace": bool(
                    nnz < MIN_NNZ_FOR_CLASS or cell_pct < MIN_PCT_FOR_CLASS
                ),
            })
    for ub in cells_by_tissue:
        cells_by_tissue[ub].sort(key=lambda c: -c["n_expressing"])
        cells_by_tissue[ub] = cells_by_tissue[ub][:CELLS_BY_TISSUE_PER_TISSUE_CAP]

    # ---- Build display lists ----
    # v2.0 displayed entries solely by mean rank, which let
    # pct=0.01% noise rows (n=1 of 17,571) dominate low-expression
    # genes like GPR75. v2.1 layers the same pct/nnz noise gate the
    # classifier uses onto the COMMON bucket — large cell-type pools
    # (n_total ≥ 1000) need real coverage to display, not a single
    # bright outlier. The rare bucket keeps its mean-only rule
    # because small-n cell types can't meet a pct gate without
    # losing meaningful signal.
    # v2.1.8+: sort COMMON by score (≈ nTPM = mean × pct), not by mean.
    # Pre-v2.1.8 sorted by mean, which let a high-mean cell with low
    # pct (e.g. trophoblast giant cell at mean=2.90, pct=10.7%, score
    # 1.8) rank ABOVE the gene's canonical high-prevalence cells (e.g.
    # placental villous trophoblast at mean=2.56, pct=68.8%, score 8.2)
    # and crowd them out of the display. Score matches the chart's
    # default Y-axis ("Score") AND the classifier's ranking — the chip
    # and chart are now showing the same data. RARE bucket keeps the
    # mean-based rank because pct is unreliable at small-n (n_total <
    # 1000); a rare high-mean cell is the right signal there.
    common: list[dict] = []
    rare: list[dict] = []
    for cl in cl_n_expressing:
        n_total = cl_n_total_display[cl]
        n_exp = cl_n_expressing[cl]
        # Recover mean even when the cell type didn't pass the
        # classifier eligibility gate (so rare/small-n cells still
        # show with their actual mean for the table).
        mean_log = cl_means_log.get(cl) or sum(
            v[1] for v in cl_to_uberon[cl].values()
        ) / max(1, sum(v[0] for v in cl_to_uberon[cl].values()))
        pct_cl = n_exp / n_total if n_total > 0 else 0.0
        score_cl = math.expm1(mean_log) * pct_cl  # ≈ nTPM
        entry = {
            "cl_id": cl,
            "mean_log": mean_log,
            "score": score_cl,
            "n_expressing": n_exp,
            "n_total": n_total,
        }
        if n_total < MIN_N_TOTAL_FOR_CLASS:
            continue
        if n_total >= COMMON_THRESHOLD:
            if pct_cl < MIN_PCT_FOR_CLASS or n_exp < MIN_NNZ_FOR_CLASS:
                continue
            common.append(entry)
        elif mean_log >= RARE_MIN_MEAN:
            rare.append(entry)
    common.sort(key=lambda e: e["score"], reverse=True)
    rare.sort(key=lambda e: e["mean_log"], reverse=True)
    common_qual = [e for e in common if e["mean_log"] >= COMMON_MIN_MEAN]
    chosen_common = common_qual[:COMMON_TOP_N]
    chosen_rare = rare[:RARE_TOP_N]
    if len(chosen_common) < COMMON_TOP_N:
        need = COMMON_TOP_N - len(chosen_common)
        chosen_rare = rare[: RARE_TOP_N + need]
    merged: list[dict] = [{**e, "is_rare": False} for e in chosen_common] + [
        {**e, "is_rare": True} for e in chosen_rare
    ]
    # Final merged sort by score so the chart shows the high-coverage
    # canonical cells first; chart's "Sort by mean" UI option still
    # works at render time.
    merged.sort(key=lambda e: e["score"], reverse=True)
    merged = merged[:MAX_CELL_TYPES]

    top_cell_types: list[dict] = []
    for e in merged:
        cl = e["cl_id"]
        ub_stats = cl_to_uberon.get(cl, {})
        tissues: list[dict] = []
        for ub, vals in ub_stats.items():
            nnz, ssum = vals
            if nnz <= 0:
                continue
            cache_n = pair_counts.get((cl, ub), 0)
            # v2.1.9: drop stale pairs entirely from per-cell-type
            # nested tissue rows. Showing a 100% pct ceiling row
            # misleads — clean-only display.
            if cache_n < int(nnz) or cache_n <= 0:
                continue
            mean_t = ssum / nnz
            tissues.append(
                {
                    "tissue": uberon_labels.get(ub, ub),
                    "uberon_id": ub,
                    "mean_log1p_cp10k": round(mean_t, 4),
                    "n_expressing": int(nnz),
                    "n_total": int(cache_n),
                    "pct_expressing": round(nnz / cache_n, 4),
                }
            )
        tissues.sort(key=lambda t: t["n_expressing"], reverse=True)
        tissues = tissues[:TOP_K_TISSUES]
        n_exp = int(e["n_expressing"])
        n_tot = int(e["n_total"])
        top_cell_types.append(
            {
                "cell_type": cl_labels.get(cl, cl),
                "cl_id": cl,
                "mean_log1p_cp10k": round(e["mean_log"], 4),
                "n_expressing": n_exp,
                "n_total": n_tot,
                "pct_expressing": round(n_exp / n_tot, 4) if n_tot > 0 else None,
                "is_rare": bool(e["is_rare"]),
                "is_trace": bool(n_exp < MIN_NNZ_FOR_CLASS or (n_tot > 0 and n_exp / n_tot < MIN_PCT_FOR_CLASS)),
                "tissues": tissues,
            }
        )

    # ---- Build top_tissues display list ----
    # v2.1.8+ sort by SCORE (≈ nTPM = mean × pct), not mean — same
    # rationale as the top_cell_types display fix. Mean-sorting
    # surfaced high-mean-low-pct noise tissues (saliva at pct=0.0%
    # ranked above heart at pct=97%); score-sorting puts the
    # high-coverage tissues where the gene actually has signal first.
    # v2.1.9+ adds ``is_stale_denominator`` flag: when >50% of the
    # tissue's nnz is from (cl, ub) pairs where the cell-count cache
    # is stale, the displayed pct hits 100% by ceiling artifact, not
    # by biology. The viewer reads this flag to caveat the row.
    tissue_rows: list[dict] = []
    for ub, n_exp in ub_n_expressing.items():
        n_total = ub_n_total_display[ub]
        if n_total < COMMON_THRESHOLD:
            continue
        mean_log = ub_pooled[ub]["sum"] / ub_pooled[ub]["nnz"]
        pct = n_exp / n_total
        score = math.expm1(mean_log) * pct
        tissue_rows.append(
            {
                "tissue": uberon_labels.get(ub, ub),
                "uberon_id": ub,
                "mean_log1p_cp10k": round(mean_log, 4),
                "n_expressing": n_exp,
                "n_total": n_total,
                "pct_expressing": round(pct, 4),
                "score": round(score, 4),
                "is_trace": bool(n_exp < MIN_NNZ_FOR_CLASS or pct < MIN_PCT_FOR_CLASS),
                "is_stale_denominator": bool(
                    ub_stale_fraction.get(ub, 0.0) > STALE_FLAG_THRESHOLD
                ),
            }
        )
    tissue_rows.sort(key=lambda r: r["score"], reverse=True)
    tissue_rows = tissue_rows[:MAX_TISSUES]

    # ---- Assemble record ----
    record = {
        "schema_version": SCHEMA_VERSION,
        "census_version": CENSUS_VERSION,
        "gene_symbol": symbol,
        "hgnc_id": hgnc or None,
        "ensembl_gene": ensembl_gene,
        # v2.1.2 broad-class rollup — the chip-facing classification.
        # Cell ontology compartments via cl-basic.obo graph walk (not
        # keyword rules). CL leaf terms still emitted under
        # cell_type_enrichment. Each axis carries τ (Yanai 2005
        # specificity) alongside the HPA discrete class.
        "cell_class_enrichment": {
            "class": class_class,
            "class_ids": class_ids,
            "class_labels": list(class_ids),  # broad classes are already labels
            "fold_change": class_fold_val,
            "fold_change_infinite": class_fold_inf,
            "tau": class_tau,
            "top_entity_contribs": class_contribs,
        },
        # v2.1.4+ cell-FAMILY axis — middle granularity (~150 terms).
        # Walks each leaf CL to its nearest ancestor with 6-40 CZI
        # cohort descendants (see cl_family.py). The names that
        # surface are biologically meaningful: B cell, T cell,
        # macrophage, hepatocyte, astrocyte, kidney loop of Henle
        # cell, etc.
        "cell_family_enrichment": {
            "class": family_class,
            "family_ids": family_ids,
            "family_labels": family_labels,
            "top_cl_labels": family_top_cl_labels,
            "fold_change": family_fold_val,
            "fold_change_infinite": family_fold_inf,
            "tau": family_tau,
            "top_entity_contribs": family_contribs,
        },
        # Leaf-CL classification — debugging / power users. Noisy at
        # the leaf-CL granularity (600+ entities) but τ is still
        # informative.
        "cell_type_enrichment": {
            "class": cl_class,
            "cl_ids": cl_ids,
            "fold_change": cl_fold_val,
            "fold_change_infinite": cl_fold_inf,
            "tau": cl_tau,
            "top_entity_contribs": cl_contribs,
        },
        "tissue_enrichment": {
            "class": ub_class,
            "uberon_ids": ub_ids,
            "tissue_labels": [uberon_labels.get(u, u) for u in ub_ids],
            "fold_change": ub_fold_val,
            "fold_change_infinite": ub_fold_inf,
            "tau": ub_tau,
            "top_entity_contribs": ub_contribs,
        },
        # v2.1.3+ organ-system category axis. Aggregates the 410
        # fine-grained UBERONs into 14 organ systems via the
        # ontology-derived map (viewer/lib/tissue-categories-uberon-
        # map.generated.ts). Solves the brain-fragmentation problem —
        # GPR75 signal across 96 brain subregions collapses into a
        # single CNS bucket, where it can compete with eye/embryo on
        # the 4× test.
        "tissue_category_enrichment": {
            "class": cat_class,
            "category_ids": cat_ids,
            "category_labels": list(cat_ids),
            # The UBERON tissue each category's signal rests on (the
            # max-pop-mean UBERON within the category). GPR75 CNS →
            # "brain", KLK2 reproductive → "prostate gland", LRP2
            # urinary → "kidney".
            "top_tissues": cat_top_tissues,
            "fold_change": cat_fold_val,
            "fold_change_infinite": cat_fold_inf,
            "tau": cat_tau,
            "top_entity_contribs": cat_contribs,
        },
        # v2.1.4+ tissue-ORGAN axis — middle granularity (~150
        # terms). Between leaf UBERON (~410) and the 13 organ-system
        # categories. Walks each UBERON to its nearest ancestor with
        # 4-30 cohort descendants (see uberon_organ.py). Brain
        # subregions roll to "brain" or "Brodmann area"; gut
        # subregions roll to "intestine"/"colon"/etc.
        "tissue_organ_enrichment": {
            "class": organ_class,
            "organ_ids": organ_ids,
            "organ_labels": organ_labels,
            "top_uberon_labels": organ_top_ub_labels,
            "fold_change": organ_fold_val,
            "fold_change_infinite": organ_fold_inf,
            "tau": organ_tau,
            "top_entity_contribs": organ_contribs,
        },
        # v2.0 legacy mirror so older readers don't break during the
        # transition. Points at the broad-class rollup (v2.1.1's
        # primary surface).
        "enrichment_class": class_class,
        "enrichment_cl_ids": class_ids,
        "fold_change": class_fold_val,
        "fold_change_infinite": class_fold_inf,
        # Display lists
        "top_cell_types": top_cell_types,
        "top_tissues": tissue_rows,
        # Reverse map: tissue UBERON → cells expressing in it (capped
        # at 20 per tissue). Powers the viewer's tissue cross-filter
        # ("show cell types in {tissue}"). Without this, clicking a
        # tissue with no top-30 cell-type bars shows "No cell types
        # in {tissue}" even when WMG has signal there.
        "cells_by_tissue": cells_by_tissue,
    }
    return record


# ---------- Main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--genes-file",
        type=Path,
        help="Newline-separated gene symbols to restrict output to (default: all).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help=f"Output dir for {{SYMBOL}}.json (default: {OUT_DIR})",
    )
    args = ap.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    gene_filter: set[str] | None = None
    if args.genes_file:
        gene_filter = {
            line.strip().upper()
            for line in args.genes_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        print(f"Gene filter: {len(gene_filter)} symbols", file=sys.stderr)

    print("Loading lookups…", file=sys.stderr)
    cl_labels = load_cl_labels()
    uberon_labels = load_uberon_labels()
    pair_counts, cl_total_counts, ub_total_counts = load_tissue_counts()
    ens_map = load_ens_map()
    print(
        f"  cl_labels={len(cl_labels)} uberon={len(uberon_labels)} "
        f"pair_counts={len(pair_counts)} cl_totals={len(cl_total_counts)} "
        f"ub_totals={len(ub_total_counts)} ens_map={len(ens_map)}",
        file=sys.stderr,
    )

    # When a gene filter is in play, restrict to that subset's
    # Ensembl IDs — saves streaming time + avoids holding the full
    # cohort's aggregate dict in memory.
    keep_ens: set[str] | None = None
    if gene_filter:
        keep_ens = {ens for ens, (sym, _) in ens_map.items() if sym.upper() in gene_filter}
        print(f"  ens filter: {len(keep_ens)} Ensembl IDs match the symbol list", file=sys.stderr)

    t0 = time.time()
    agg: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    )
    print(f"Streaming WMG ({WMG.name})…", file=sys.stderr)
    n_rows = 0
    n_kept = 0
    with gzip.open(WMG, "rt") as f:
        reader = csv.reader(f)
        _header = next(reader)
        for row in reader:
            n_rows += 1
            if n_rows % 5_000_000 == 0:
                print(f"  {n_rows:,} rows ({time.time()-t0:.0f}s, kept {n_kept:,})", file=sys.stderr)
            gene, tissue, _org, cl, nnz_s, sum_s, _sqsum = row
            if keep_ens is not None and gene not in keep_ens:
                continue
            try:
                nnz = float(nnz_s)
                ssum = float(sum_s)
            except ValueError:
                continue
            slot = agg[gene][cl][tissue]
            slot[0] += nnz
            slot[1] += ssum
            n_kept += 1
    print(
        f"Stream done: {n_rows:,} rows in {time.time()-t0:.1f}s "
        f"(kept {n_kept:,} for {len(agg)} genes)",
        file=sys.stderr,
    )

    # ---- Build per-gene records ----
    t1 = time.time()
    cl_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    tissue_class_counts: Counter[str] = Counter()
    written = 0
    manifest_rows: list[list[str]] = []
    for ensembl_gene, cl_to_uberon in agg.items():
        sym_hgnc = ens_map.get(ensembl_gene)
        if not sym_hgnc:
            continue
        symbol, hgnc = sym_hgnc
        if not symbol:
            continue
        if gene_filter is not None and symbol.upper() not in gene_filter:
            continue
        record = build_record(
            symbol,
            hgnc,
            ensembl_gene,
            cl_to_uberon,
            cl_labels,
            uberon_labels,
            pair_counts,
            cl_total_counts,
            ub_total_counts,
        )
        cl_counts[record["cell_type_enrichment"]["class"]] += 1
        class_counts[record["cell_class_enrichment"]["class"]] += 1
        tissue_class_counts[record["tissue_enrichment"]["class"]] += 1
        (out_dir / f"{symbol}.json").write_text(json.dumps(record, separators=(",", ":")))
        written += 1
        manifest_rows.append([
            symbol,
            hgnc,
            ensembl_gene,
            record["cell_class_enrichment"]["class"],
            ";".join(record["cell_class_enrichment"]["class_ids"]),
            record["tissue_enrichment"]["class"],
            ";".join(record["tissue_enrichment"]["uberon_ids"]),
            str(len(record["top_cell_types"])),
            str(len(record["top_tissues"])),
        ])
    print(f"Write done: {written} genes in {time.time()-t1:.1f}s", file=sys.stderr)

    # ---- Manifest ----
    manifest = out_dir.parent / (out_dir.name + "_manifest.tsv")
    with manifest.open("w") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "gene_symbol", "hgnc_id", "ensembl_gene",
            "cell_class", "cell_class_ids",
            "tissue_class", "tissue_ids",
            "n_top_cell_types", "n_top_tissues",
        ])
        w.writerows(manifest_rows)

    # ---- Report ----
    print("\n=== STATS ===", file=sys.stderr)
    print("Cell-class axis (broad rollup):", file=sys.stderr)
    for c in ("enriched", "group_enriched", "enhanced", "low_specificity", "not_detected"):
        print(f"  {c}: {class_counts.get(c, 0)}", file=sys.stderr)
    print("Leaf-CL axis (fine-grained, for debugging):", file=sys.stderr)
    for c in ("enriched", "group_enriched", "enhanced", "low_specificity", "not_detected"):
        print(f"  {c}: {cl_counts.get(c, 0)}", file=sys.stderr)
    print("Tissue axis classes:", file=sys.stderr)
    for c in ("enriched", "group_enriched", "enhanced", "low_specificity", "not_detected"):
        print(f"  {c}: {tissue_class_counts.get(c, 0)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
