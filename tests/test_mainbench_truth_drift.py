"""Guard against denormalized-column drift across the figure-input TSVs.

Each figure-input TSV under ``data/processed/**`` and ``data/eval/**``
denormalizes columns from a different upstream source so figure scripts
can answer common questions with one filter instead of a 3-way join.
The trade-off (per CLAUDE.md "Figure-input TSV conventions"): the same
fact lives in multiple places. If one place is updated without the
other, the figures silently render stale numbers.

The historical incident that motivated these guards: D1's
``benchmark_version`` (canonical labels) was updated to flip FN1 /
HMGB1 from ``no`` → ``contextual`` and BAX / IZUMO4 / LYN from
``contextual`` → ``no``. The eval TSV tracked. The v2 mainbench
tracked. But the old ``mainbench_canonical_v1.tsv`` silently kept the
pre-update labels — every "Sonnet+ncbi missed N genes" analysis read
off it was off by ~5 genes. v1 has since been deleted; these tests
exist so a future re-incarnation doesn't reproduce the failure mode.

Each test below pins one cross-file invariant. If any fail, the fix is
the same: re-run ``scripts/augment_figure_tsvs_with_stable_ids.py``
and commit the regenerated TSVs in the same change.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from accessible_surfaceome.paths import REPO_ROOT

EVAL_TSV = REPO_ROOT / "data/eval/triage_benchmark_v1.tsv"
MAINBENCH_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
MAINBENCH_REPLICATES_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
CANDIDATE_UNIVERSE_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
DB_CUTOFFS_TSV = REPO_ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"

# Bench prediction TSVs share the same denormalized columns (truth,
# 5 surface flags, n_db_votes, stable IDs) — the only difference is
# canonical_v2 carries one row per (gene, model, variant) cell with
# majority-aggregated verdicts, while replicates_v2 carries every
# individual replicate. Both must clear the same drift guards.
BENCH_PREDICTION_TSVS = (MAINBENCH_TSV, MAINBENCH_REPLICATES_TSV)

# Stable-ID columns checked for cross-TSV consistency. Per CLAUDE.md
# "Gene identifier resolution", ``hgnc_id`` is the canonical key; the
# rest are derived and should track. ``uniprot_acc`` is also checked
# where both files carry it, but its column names differ across TSVs
# (eval/mainbench: ``uniprot_acc``; candidate_universe: ``uniprot_accession``).
STABLE_ID_COLS = ("hgnc_id", "ensembl_gene", "ncbi_gene_id")

SURFACE_FLAG_COLS = (
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "hpa_surface_flag",
)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


@pytest.mark.parametrize(
    "tsv_path",
    BENCH_PREDICTION_TSVS,
    ids=lambda p: p.name,
)
def test_bench_truth_matches_curated_eval(tsv_path: Path) -> None:
    """For every gene in a bench prediction TSV, the denormalized
    ``ground_truth_verdict`` / ``ground_truth_class`` must equal the
    curated eval TSV's ``ground_truth_verdict`` / ``class``.

    Covers both the canonical (per-cell majority) and replicates
    (per-replicate) bench files. Failure means the curated truth was
    edited without re-running ``augment_figure_tsvs_with_stable_ids.py``
    (or the export wasn't refreshed via ``export_mainbench_to_tsv.py``
    after a D1 truth update). Fix: re-run augment and commit the
    regenerated TSV in the same change.
    """
    if not (EVAL_TSV.exists() and tsv_path.exists()):
        pytest.skip(f"{tsv_path.name} or eval TSV not present (partial checkout)")
    curated = {
        r["gene_symbol"]: (r["ground_truth_verdict"], r["class"])
        for r in _read_tsv(EVAL_TSV)
    }
    bench_rows = _read_tsv(tsv_path)

    mismatches: list[str] = []
    seen: set[str] = set()
    for r in bench_rows:
        gene = r["gene_symbol"]
        if gene in seen:
            continue
        seen.add(gene)
        # Every prediction row for the gene carries the same denormalized
        # truth; first row per gene is enough to detect drift.
        expected = curated.get(gene)
        if expected is None:
            mismatches.append(
                f"{gene}: in {tsv_path.name} but NOT in eval TSV — "
                "curated source is missing this gene"
            )
            continue
        actual = (r["ground_truth_verdict"], r["ground_truth_class"])
        if actual != expected:
            mismatches.append(
                f"{gene}: {tsv_path.name}={actual!r} vs curated={expected!r}"
            )

    assert not mismatches, (
        "Denormalized truth drift detected in "
        f"{tsv_path.relative_to(REPO_ROOT)}. "
        "Re-run scripts/augment_figure_tsvs_with_stable_ids.py and commit "
        f"the regenerated TSV.\nMismatches ({len(mismatches)}):\n"
        + "\n".join(f"  • {m}" for m in mismatches[:20])
        + (f"\n  … and {len(mismatches) - 20} more" if len(mismatches) > 20 else "")
    )


@pytest.mark.parametrize(
    "tsv_path",
    BENCH_PREDICTION_TSVS,
    ids=lambda p: p.name,
)
def test_bench_truth_is_internally_consistent(tsv_path: Path) -> None:
    """All prediction rows for the same gene must carry the same
    denormalized truth. A within-gene mismatch would mean the augment
    step ran inconsistently (different rows joined against different
    snapshots of the curated source).
    """
    if not tsv_path.exists():
        pytest.skip(f"{tsv_path.name} not present (partial checkout)")
    per_gene_truths: dict[str, set[tuple[str, str]]] = {}
    for r in _read_tsv(tsv_path):
        per_gene_truths.setdefault(r["gene_symbol"], set()).add(
            (r["ground_truth_verdict"], r["ground_truth_class"])
        )
    inconsistent = {g: ts for g, ts in per_gene_truths.items() if len(ts) > 1}
    assert not inconsistent, (
        "Within-gene truth inconsistency in "
        f"{tsv_path.relative_to(REPO_ROOT)}: "
        f"{len(inconsistent)} genes carry conflicting denormalized truths. "
        f"Sample: {dict(list(inconsistent.items())[:3])!r}"
    )


def _index_candidate_universe_by_acc() -> dict[str, dict[str, str]]:
    """``candidate_universe.tsv`` is keyed on ``(uniprot_accession,
    gene_symbol)`` — a gene with multiple reviewed UniProt entries
    appears in multiple rows. Per the augment script
    (``n_db_votes_by_acc`` in
    ``scripts/augment_figure_tsvs_with_stable_ids.py``), denormalized
    DB columns are joined by ``uniprot_accession``. The bench TSV
    pins a specific accession per gene, so the per-accession join is
    the authoritative one — gene-symbol indexing would miss the
    correct row for multi-accession genes (SIRPB1 carries 2 rows;
    NRXN1 has 2; etc.).
    """
    return {
        r["uniprot_accession"]: r
        for r in _read_tsv(CANDIDATE_UNIVERSE_TSV)
        if r.get("uniprot_accession")
    }


@pytest.mark.skipif(
    not (EVAL_TSV.exists() and CANDIDATE_UNIVERSE_TSV.exists()),
    reason="figure-input TSVs not present (partial checkout)",
)
def test_eval_n_db_votes_matches_candidate_universe() -> None:
    """The eval TSV's ``n_db_votes`` column is a denormalized copy of
    the candidate-universe's ``n_sources_surface``, joined per
    ``uniprot_acc`` (see ``n_db_votes_by_acc`` in the augment script).
    Drift here means the bench DB-membership counts in the headline
    figures (zero-DB rescues, soft-credit accounting) disagree with
    the underlying catalog.

    NB: ``candidate_universe.tsv`` only contains genes with at least
    one DB vote — so a bench gene with ``n_db_votes == 0`` is
    legitimately absent. The check is one-way: if the gene is in
    candidate_universe, the counts must match.
    """
    cu_by_acc = _index_candidate_universe_by_acc()
    mismatches: list[str] = []
    for r in _read_tsv(EVAL_TSV):
        acc = (r.get("uniprot_acc") or "").strip()
        if not acc:
            continue
        cu_row = cu_by_acc.get(acc)
        if cu_row is None:
            # Zero-DB gene → expected to be absent from candidate_universe.
            # Sanity check: eval should report n_db_votes=0 for it.
            n_votes = (r.get("n_db_votes") or "").strip()
            if n_votes and n_votes != "0":
                mismatches.append(
                    f"{r['gene_symbol']} ({acc}): eval n_db_votes={n_votes!r} "
                    f"but candidate_universe has no row for this accession "
                    f"(only DB-positive genes are in candidate_universe — "
                    f"counts must be 0 if absent)"
                )
            continue
        expected = cu_row.get("n_sources_surface", "")
        actual = (r.get("n_db_votes") or "").strip()
        if actual != expected:
            mismatches.append(
                f"{r['gene_symbol']} ({acc}): eval n_db_votes={actual!r} vs "
                f"candidate_universe n_sources_surface={expected!r}"
            )
    assert not mismatches, (
        f"Eval TSV n_db_votes drifted from candidate_universe.tsv "
        f"({len(mismatches)} rows). Re-run augment_figure_tsvs_with_stable_ids.py.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:20])
    )


@pytest.mark.skipif(
    not (EVAL_TSV.exists() and CANDIDATE_UNIVERSE_TSV.exists()),
    reason="figure-input TSVs not present (partial checkout)",
)
def test_eval_sonnet_verdict_matches_candidate_universe() -> None:
    """Eval TSV's ``sonnet_verdict``/``sonnet_reason`` columns are
    denormalized from the canonical Sonnet+ncbi sweep — same source
    candidate_universe.tsv reads. Both are joined by ``uniprot_acc``
    in the augment script. Drift means one figure attributes the
    wrong call to Sonnet relative to another, which is an integrity
    bug for the cost-vs-accuracy and DB-overlap figures.
    """
    cu_by_acc = _index_candidate_universe_by_acc()
    mismatches: list[str] = []
    for r in _read_tsv(EVAL_TSV):
        acc = (r.get("uniprot_acc") or "").strip()
        if not acc:
            continue
        cu_row = cu_by_acc.get(acc)
        if cu_row is None:
            continue  # zero-DB gene, absent from candidate_universe by design
        expected = (cu_row.get("sonnet_verdict", ""), cu_row.get("sonnet_reason", ""))
        actual = (r.get("sonnet_verdict", ""), r.get("sonnet_reason", ""))
        if actual != expected:
            mismatches.append(
                f"{r['gene_symbol']} ({acc}): eval={actual!r} vs "
                f"candidate_universe={expected!r}"
            )
    assert not mismatches, (
        f"Eval TSV sonnet_verdict/sonnet_reason drifted from "
        f"candidate_universe.tsv ({len(mismatches)} rows). "
        f"Re-run augment_figure_tsvs_with_stable_ids.py.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:20])
    )


@pytest.mark.parametrize(
    "tsv_path",
    BENCH_PREDICTION_TSVS,
    ids=lambda p: p.name,
)
def test_bench_db_flags_match_candidate_universe(tsv_path: Path) -> None:
    """The bench TSV's 5 ``*_surface_flag`` columns + ``n_db_votes``
    are denormalized from candidate_universe.tsv per ``uniprot_acc``.
    A bench gene without a candidate_universe row is legitimately
    zero-DB (see ``test_eval_n_db_votes_matches_candidate_universe``).
    """
    if not (tsv_path.exists() and CANDIDATE_UNIVERSE_TSV.exists()):
        pytest.skip(f"{tsv_path.name} or candidate_universe not present")
    cu_by_acc = _index_candidate_universe_by_acc()
    mismatches: list[str] = []
    seen: set[str] = set()
    for r in _read_tsv(tsv_path):
        gene = r["gene_symbol"]
        if gene in seen:
            continue
        seen.add(gene)
        acc = (r.get("uniprot_acc") or "").strip()
        if not acc:
            continue
        ref = cu_by_acc.get(acc)
        if ref is None:
            # Zero-DB gene → flags should all be 0 and n_db_votes 0.
            for col in SURFACE_FLAG_COLS:
                if r.get(col, "0") not in ("0", ""):
                    mismatches.append(
                        f"{gene} ({acc})/{col}: {tsv_path.name}={r.get(col)!r} "
                        f"but gene is absent from candidate_universe "
                        f"(would imply 0)"
                    )
            n_votes = (r.get("n_db_votes") or "").strip()
            if n_votes and n_votes != "0":
                mismatches.append(
                    f"{gene} ({acc})/n_db_votes: {tsv_path.name}={n_votes!r} "
                    f"but absent from candidate_universe"
                )
            continue
        for col in SURFACE_FLAG_COLS:
            mb_val = r.get(col, "")
            cu_val = ref.get(col, "")
            if mb_val != cu_val:
                mismatches.append(
                    f"{gene} ({acc})/{col}: {tsv_path.name}={mb_val!r} vs "
                    f"candidate_universe={cu_val!r}"
                )
        mb_count = r.get("n_db_votes", "")
        cu_count = ref.get("n_sources_surface", "")
        if mb_count != cu_count:
            mismatches.append(
                f"{gene} ({acc})/n_db_votes: {tsv_path.name}={mb_count!r} vs "
                f"candidate_universe n_sources_surface={cu_count!r}"
            )
    assert not mismatches, (
        f"Bench DB columns drifted from candidate_universe.tsv in "
        f"{tsv_path.relative_to(REPO_ROOT)} ({len(mismatches)} mismatches). "
        f"Re-run augment_figure_tsvs_with_stable_ids.py.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:20])
    )


@pytest.mark.skipif(
    not DB_CUTOFFS_TSV.exists(),
    reason="db_optimized_cutoffs.tsv not present (partial checkout)",
)
def test_db_cutoffs_n_sources_matches_flag_sum() -> None:
    """Internal consistency: ``n_sources_surface`` in db_optimized_cutoffs
    must equal the sum of its 5 ``*_surface_flag`` columns. A drift here
    means the figure that splits "n DBs voted surface" by cutoff choice
    is reading a denormalized count that the underlying flags don't
    support.
    """
    mismatches: list[str] = []
    for r in _read_tsv(DB_CUTOFFS_TSV):
        acc = r.get("accession", "<no-acc>")
        flag_sum = sum(int(r.get(col, "0") or "0") for col in SURFACE_FLAG_COLS)
        n_sources = int(r.get("n_sources_surface", "0") or "0")
        if flag_sum != n_sources:
            mismatches.append(
                f"{acc}: n_sources_surface={n_sources} but sum of 5 flag cols={flag_sum}"
            )
    assert not mismatches, (
        f"db_optimized_cutoffs n_sources_surface drift "
        f"({len(mismatches)} rows). The 5-flag sum is the source of truth; "
        f"re-run the canonical_universe builder to refresh.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:10])
    )


@pytest.mark.skipif(
    not (EVAL_TSV.exists() and MAINBENCH_TSV.exists()
         and MAINBENCH_REPLICATES_TSV.exists()
         and CANDIDATE_UNIVERSE_TSV.exists() and DB_CUTOFFS_TSV.exists()),
    reason="figure-input TSVs not present (partial checkout)",
)
def test_stable_ids_consistent_across_figure_tsvs() -> None:
    """Same ``gene_symbol`` must map to the same stable IDs
    (``hgnc_id``, ``ensembl_gene``, ``ncbi_gene_id``) wherever the
    symbol appears across the figure-input TSVs. A divergence here
    means a symbol-keyed join would silently misroute a small subset
    of human genes (the COX1 / WAS class documented in CLAUDE.md
    "Gene identifier resolution").

    Build the canonical map gradually: every TSV is treated as a
    contributing source. The first non-blank ID tuple seen for a
    symbol becomes the canonical pin; subsequent non-blank tuples for
    the same symbol must match it. Blank-ID rows (alternate-accession
    rows in candidate_universe; rows where the column simply doesn't
    exist) are skipped — they neither pin nor contradict.
    """
    canonical: dict[str, tuple[str, ...]] = {}
    mismatches: list[str] = []

    for tsv_path in (CANDIDATE_UNIVERSE_TSV, EVAL_TSV, MAINBENCH_TSV,
                     MAINBENCH_REPLICATES_TSV, DB_CUTOFFS_TSV):
        seen_in_tsv: set[str] = set()
        for r in _read_tsv(tsv_path):
            gene = r.get("gene_symbol")
            if not gene or gene in seen_in_tsv:
                continue
            local = tuple(r.get(c, "") for c in STABLE_ID_COLS)
            if not any(local):
                # All-blank row (e.g. alternate-accession candidate_universe
                # row, or a TSV that doesn't carry stable IDs at all).
                # Doesn't pin anything; doesn't contradict.
                continue
            seen_in_tsv.add(gene)
            ref = canonical.get(gene)
            if ref is None:
                canonical[gene] = local
                continue
            if local != ref:
                rel = tsv_path.relative_to(REPO_ROOT)
                mismatches.append(
                    f"{rel} :: {gene}: {local!r} vs already-pinned {ref!r}"
                )

    assert not mismatches, (
        f"Stable-ID drift across figure TSVs ({len(mismatches)} rows). "
        "Re-run augment_figure_tsvs_with_stable_ids.py to re-pin every "
        f"figure TSV against gene_identifier_public.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:15])
    )


@pytest.mark.skipif(
    not (MAINBENCH_TSV.exists() and MAINBENCH_REPLICATES_TSV.exists()),
    reason="bench TSVs not present (partial checkout)",
)
def test_canonical_verdict_matches_replicate_majority() -> None:
    """``mainbench_canonical_v2.tsv`` carries the per-cell majority
    verdict across replicates (see ``_collapse_to_majority`` in
    ``scripts/export_mainbench_to_tsv.py``); ``mainbench_replicates_v2.tsv``
    carries the raw replicates. Recompute the surface-side majority
    from the replicates and assert it matches canonical_v2's recorded
    verdict — otherwise one TSV was regenerated and the other wasn't.

    The export script collapses verdicts to {surface, not_surface} via
    ``_surface_vote`` (yes/contextual → surface; no → not_surface), then
    picks the within-winning-side verdict by simple majority. The
    *reason* canonical_v2 records is a "representative" from the first
    matching rep — we don't pin reason here (its tiebreak depends on
    rep-iteration order and isn't a clean invariant), only the verdict.
    """
    from collections import Counter

    def _surface_side(v: str) -> str | None:
        if v in ("yes", "contextual"):
            return "surface"
        if v == "no":
            return "not_surface"
        return None

    cells: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for r in _read_tsv(MAINBENCH_REPLICATES_TSV):
        key = (r["gene_symbol"], r["model"], r["prompt_variant"])
        cells.setdefault(key, []).append(r)

    majority_verdict_by_cell: dict[tuple[str, str, str], str] = {}
    win_verdicts_by_cell: dict[tuple[str, str, str], set[str]] = {}
    for key, reps in cells.items():
        valid = [r for r in reps if _surface_side(r.get("predicted_verdict", "")) is not None]
        if not valid:
            continue
        side_counts = Counter(_surface_side(r["predicted_verdict"]) for r in valid)
        winning_side = side_counts.most_common(1)[0][0]
        win_reps = [r for r in valid if _surface_side(r["predicted_verdict"]) == winning_side]
        verdict_counts = Counter(r["predicted_verdict"] for r in win_reps)
        majority_verdict_by_cell[key] = verdict_counts.most_common(1)[0][0]
        # The recorded reason must come from a rep with this verdict
        # (the export script picks one such rep as "representative").
        win_verdicts_by_cell[key] = {r["predicted_verdict"] for r in win_reps}

    mismatches: list[str] = []
    for r in _read_tsv(MAINBENCH_TSV):
        key = (r["gene_symbol"], r["model"], r["prompt_variant"])
        expected_verdict = majority_verdict_by_cell.get(key)
        if expected_verdict is None:
            mismatches.append(f"{key}: in canonical_v2 but absent from replicates_v2")
            continue
        actual = r.get("predicted_verdict", "")
        if actual != expected_verdict:
            mismatches.append(
                f"{key}: canonical_v2 verdict={actual!r} vs "
                f"majority-from-replicates={expected_verdict!r}"
            )

    assert not mismatches, (
        f"Canonical-v2 verdict drifted from replicates-v2 raw replicates "
        f"({len(mismatches)} cells). One TSV was regenerated and the "
        f"other wasn't. Re-run scripts/export_mainbench_to_tsv.py.\n"
        + "\n".join(f"  • {m}" for m in mismatches[:15])
    )
