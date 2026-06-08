"""Drift-detection harness for the deep-dive prompt corpus — 5 canonical
validation genes covering structurally distinct surface-accessibility
archetypes.

Each (gene, json_path, expected, owner) row in :data:`EXPECTATIONS`
asserts one record property that traces to a specific prompt rule.
When a re-annotation produces a different call, the failure message
names the responsible prompt section so triage is fast.

The harness AUTO-SKIPS when CLOUDFLARE_API_TOKEN is absent — CI smoke
runs without API access aren't blocked. When the Worker is reachable,
all 5 records are fetched once per session and cached in a
module-scoped fixture.

**Discipline:** prompt edits don't auto-re-annotate. After bumping
``PROMPT_CORPUS_VERSION`` (or editing any prompt that could affect
these 5 archetypes), re-run them via
``scripts/surfaceome_v2_annotate.py <SYMBOL>`` (~$2-3/gene) before
running these tests. Otherwise the tests run against the pre-edit
records and can't see new drift.

See :doc:`docs/validation/2026-06-rerun-expectations.md` for the
full prose context behind each expectation.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest


_PUBLIC_API = "https://api.deliverome.org/surfaceome/v1/genes"
_VALIDATION_GENES = ("TACSTD2", "HMGB1", "SRC", "GPR75", "TGOLN2")


@pytest.fixture(scope="module")
def records() -> dict[str, dict[str, Any]]:
    """Fetch all 5 validation records once per test session.

    Skipped when ``CLOUDFLARE_API_TOKEN`` is absent (offline CI smoke) —
    the Worker doesn't require auth but the env-var probe is a clean
    "is this a network-enabled run" gate that matches the other Cloud-
    dependent tests in this suite.
    """
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        pytest.skip(
            "CLOUDFLARE_API_TOKEN not set — validation tests skipped in "
            "offline CI smoke. Run with .env loaded to enable."
        )

    out: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=30.0) as c:
        for sym in _VALIDATION_GENES:
            try:
                r = c.get(f"{_PUBLIC_API}/{sym}")
                r.raise_for_status()
                out[sym] = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                pytest.skip(
                    f"Worker unreachable / returned non-JSON for {sym}: "
                    f"{exc!r} — validation tests can't run without a live "
                    f"public API."
                )
    return out


# (gene, dotted_json_path, expected, owning_prompt_section_or_validator)
#
# Path uses simple dot notation; lists are supported via ``[]`` (any
# element) or ``len(...)`` for cardinality. Keep specific to fields
# the validation review converged on — under-specifying is fine, the
# CLAIM is what we're regression-guarding.
EXPECTATIONS: list[tuple[str, str, Any, str]] = [
    # ---- TACSTD2 / TROP2 — canonical surface receptor ----
    (
        "TACSTD2", "executive_summary.surface_accessibility", "high",
        "synth surface_accessibility — YES-bucket; TACSTD2 has direct "
        "multi-method support + FDA-approved ADCs",
    ),
    (
        "TACSTD2", "executive_summary.state_dependence", {"moderate", "high"},
        "_check_state_dependence_consistent_with_modulation validator + "
        "synth state_dependence rule — TACSTD2 has tumor-induced "
        "upregulation; 'low' is forbidden",
    ),
    (
        "TACSTD2", "surface_evidence.evidence_grade", "direct_multi_method",
        "evidence_grade_builder — ≥2 direct surface methods for TACSTD2 "
        "(live flow + biotinylation + IHC membranous)",
    ),
    (
        "TACSTD2", "filters.has_known_ligand", True,
        "synth has_known_ligand — TACSTD2 has documented ligands",
    ),
    (
        "TACSTD2", "filters.has_known_ligand_rationale.len>0", True,
        "Filters._require_has_known_ligand_rationale_when_true validator — "
        "non-empty rationale required when has_known_ligand=True",
    ),
    (
        "TACSTD2", "filters.tumor_associated", True,
        "_derive_filters tumor_associated — biology shows tumor expression",
    ),
    (
        "TACSTD2", "filters.induction_trigger", "oncogenic",
        "_derive_filters induction_trigger — accessibility_modulation "
        "rows show oncogenic-transformation triggers",
    ),
    (
        "TACSTD2", "surface_evidence.excluded_as_ligand_engagement.len==0", True,
        "methods_builder inclusion criterion — TACSTD2 is the TM membrane "
        "component, no soluble-ligand engagement to exclude",
    ),

    # ---- HMGB1 — soluble DAMP, ligand-engagement filter case ----
    (
        "HMGB1", "executive_summary.surface_accessibility",
        {"moderate", "high"},
        "synth surface_accessibility — HMGB1 IS surface-accessible "
        "biologically (state-conditional via acetylation / necrotic "
        "release); YES bucket per the 'best-case state' rule",
    ),
    (
        "HMGB1", "executive_summary.state_dependence", "high",
        "synth state_dependence — acetylation/necrotic-release gating is "
        "the entire HMGB1 mechanism; 'low' is forbidden by validator + "
        "biology forces 'high'",
    ),
    (
        "HMGB1", "surface_evidence.evidence_grade",
        {"weak", "supportive_but_indirect"},
        "evidence_grade_builder + methods_builder inclusion filter — "
        "once ligand-engagement claims (HMGB1 binding RAGE/TREM-1) are "
        "excluded, remaining direct surface evidence is genuinely thin. "
        "Either `weak` (when only expression_only methods survive) or "
        "`supportive_but_indirect` (when the trafficking-with-dwell rule "
        "lifts permeabilized-IF + PM-trafficking observations) is in-range; "
        "the call SHOULD NOT be direct_*. Confirmed acceptable in the "
        "2.15.0 / 2.16.0 validation review.",
    ),
    (
        "HMGB1", "surface_evidence.excluded_as_ligand_engagement.len>=2", True,
        "methods_builder inclusion criterion — HMGB1's BS3-crosslink-"
        "to-TREM-1 + RAGE-binding + similar receptor-engagement claims "
        "MUST land in excluded_as_ligand_engagement (the load-bearing "
        "test of the ligand-engagement filter)",
    ),

    # ---- SRC — cancer-state outer-leaflet inversion ----
    (
        "SRC", "executive_summary.surface_accessibility",
        {"moderate", "high"},
        "synth surface_accessibility — SRC has documented cancer-state "
        "outer-leaflet inversion; inner-leaflet rejection should NOT "
        "kill the cancer-state evidence",
    ),
    (
        "SRC", "executive_summary.state_dependence", "high",
        "synth state_dependence — SRC's surface form is cancer-state-"
        "gated (cancer cells only); inner-leaflet kinase at baseline",
    ),
    (
        "SRC", "surface_evidence.evidence_grade",
        {"direct_single_method", "direct_multi_method"},
        "evidence_grade_builder — SRC has direct surface methods on the "
        "cancer-state pool; should clear the direct bar",
    ),

    # ---- GPR75 — class A GPCR, supportive-but-indirect ----
    (
        "GPR75", "executive_summary.surface_accessibility", "high",
        "synth surface_accessibility — canonical class A GPCR with 7TM "
        "topology; YES bucket",
    ),
    (
        "GPR75", "surface_evidence.evidence_grade", "direct_single_method",
        "methods_builder anti-patterns + species-aware multi-species "
        "handling — under 2.17.0+, the SH-SY5Y (human) component of the "
        "rat-cortical-neurons / SH-SY5Y live-cell flow study is the "
        "load-bearing direct row. Single direct method + indirect "
        "supporting rows → direct_single_method (NOT multi, not "
        "supportive_but_indirect). The synth's tone-discipline rule "
        "then caps surface_accessibility at moderate (since "
        "direct_single + confidence<high).",
    ),

    # ---- TGOLN2 — endomembrane resident with PM trafficking ----
    (
        "TGOLN2", "executive_summary.surface_accessibility", "low",
        "methods_builder 'transient trafficking with documented PM dwell' "
        "section + synth dual_localization vs endomembrane_resident "
        "disambiguation — TGN46 has documented PM-trafficking evidence "
        "(CLEM transport carriers); should NOT land at 'no'",
    ),
    (
        "TGOLN2", "executive_summary.state_dependence",
        {"moderate", "high"},
        "synth state_dependence — brief PM dwell is a state-conditional "
        "pool, not constitutive",
    ),
    (
        "TGOLN2", "executive_summary.surface_call_reason", "dual_localization",
        "synth endomembrane_resident vs dual_localization disambiguation "
        "(load-bearing rule) — when any trafficking-to-PM observation "
        "exists in A1, default to dual_localization (CONTEXTUAL bucket)",
    ),
]


def _resolve(record: dict[str, Any], path: str) -> Any:
    """Walk a dotted path, with two extensions:

    * ``foo.bar.len==N`` — assert ``len(record.foo.bar) == N``, return bool
    * ``foo.bar.len>=N`` / ``len>N`` / ``len>0`` — same with comparison
    * ``foo.bar.len>0`` is a shortcut for "non-empty"

    Keeps the EXPECTATIONS table readable while supporting cardinality
    checks alongside scalar comparisons.
    """
    # Split off any trailing len-comparison
    cmp_ops = ["len>=", "len<=", "len==", "len>", "len<"]
    leaf_op: tuple[str, int] | None = None
    for op in cmp_ops:
        if path.endswith(f".{op}0") or any(
            path.endswith(f".{op}{n}") for n in range(100)
        ):
            # Extract the integer after the op
            idx = path.rfind(f".{op}")
            n = int(path[idx + len(op) + 1:])
            path = path[:idx]
            leaf_op = (op, n)
            break

    cur: Any = record
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None

    if leaf_op is None:
        return cur
    if cur is None:
        # If we're checking len of a missing field, treat as len 0
        cur = []
    if isinstance(cur, str):
        actual_len = len(cur)
    elif hasattr(cur, "__len__"):
        actual_len = len(cur)
    else:
        return False

    op, n = leaf_op
    if op == "len==":
        return actual_len == n
    if op == "len>=":
        return actual_len >= n
    if op == "len<=":
        return actual_len <= n
    if op == "len>":
        return actual_len > n
    if op == "len<":
        return actual_len < n
    return False


@pytest.mark.parametrize(
    "gene,path,expected,owner",
    EXPECTATIONS,
    ids=[f"{g}::{p}" for g, p, _, _ in EXPECTATIONS],
)
def test_validation_expectation(
    records: dict[str, dict[str, Any]],
    gene: str,
    path: str,
    expected: Any,
    owner: str,
) -> None:
    """Each row asserts one (gene, field, expectation) from the
    docs/validation/2026-06-rerun-expectations.md set.

    On failure, the message names the prompt section / validator that
    owns the call — so the failed test points straight at where to
    look in the prompt corpus.
    """
    record = records[gene]
    actual = _resolve(record, path)

    # Expected may be a set (any-of) or a single value.
    if isinstance(expected, set):
        ok = actual in expected
        expected_str = " | ".join(repr(e) for e in sorted(expected, key=str))
    else:
        ok = actual == expected
        expected_str = repr(expected)

    assert ok, (
        f"\n  Gene:     {gene}"
        f"\n  Field:    {path}"
        f"\n  Expected: {expected_str}"
        f"\n  Got:      {actual!r}"
        f"\n  Owner:    {owner}"
        f"\n  See docs/validation/2026-06-rerun-expectations.md for context."
    )


def test_all_validation_genes_published(
    records: dict[str, dict[str, Any]],
) -> None:
    """Sanity guard: every gene in the validation set must have a record
    served by the Worker. If a gene is missing entirely, the
    parameterized tests above pass vacuously (KeyError → records[gene]
    → fixture skip). This makes the "missing" case explicit."""
    missing = [g for g in _VALIDATION_GENES if g not in records]
    assert not missing, (
        f"validation genes missing from /v1/genes: {missing}. "
        f"Re-annotate via scripts/surfaceome_v2_annotate.py <SYMBOL>."
    )


def test_schema_versions_match_each_other(
    records: dict[str, dict[str, Any]],
) -> None:
    """All 5 records should be on the same schema_version — they're
    validating the SAME prompt corpus. A mismatch means someone re-ran
    only some of them after a prompt bump."""
    versions = {g: r.get("schema_version") for g, r in records.items()}
    distinct = set(versions.values())
    assert len(distinct) == 1, (
        f"validation genes are on mixed schema_versions: {versions}. "
        f"Re-annotate the lagging genes so the entire set runs against "
        f"the same prompt corpus."
    )
