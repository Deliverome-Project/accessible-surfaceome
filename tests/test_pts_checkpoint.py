"""Tests for the mid-gene PTS checkpoint in the v2 orchestrator.

The checkpoint persists a serialized ``DualPlanTrimSelectResult`` after a
successful PTS dual run, so a restart on the next attempt of the same
gene can short-circuit past the ~$1.35 PTS spend. The pieces under test:

* :func:`_checkpoint_path` produces filesystem-safe paths keyed on gene id.
* :func:`_save_pts_checkpoint` round-trips through
  :func:`_load_pts_checkpoint` (write → read → reconstruct without loss
  of the fields the orchestrator's builder/synth pipeline reads:
  bundle, A1 claims, A2 claims).
* :func:`_delete_pts_checkpoint` removes the file and is a no-op when
  the file doesn't exist.
* Best-effort semantics: a missing checkpoint returns None rather than
  raising; a corrupt JSON returns None.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from accessible_surfaceome.agents.plan_trim_select.runner import (
    DualPlanTrimSelectResult,
    PlanTrimSelectResult,
)
from accessible_surfaceome.agents.surfaceome_v2 import orchestrator
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    IdentifierBundle,
)


def _make_bundle() -> IdentifierBundle:
    """Minimal valid IdentifierBundle for a fake gene."""
    return IdentifierBundle(
        hgnc_symbol="FOO",
        hgnc_id="HGNC:1",
        uniprot_acc="P12345",
        ncbi_gene_id=12345,
        ensembl_gene="ENSG00000000000",
    )


def _make_dual(n_a1_claims: int = 2, n_a2_claims: int = 3) -> DualPlanTrimSelectResult:
    """Construct a small DualPlanTrimSelectResult for round-trip testing.

    Claims are populated with the minimal fields the EvidenceClaim model
    requires; the checkpoint code only round-trips claims for the
    builder/synth phases, so only their model_validate / model_dump
    must work.
    """
    bundle = _make_bundle()

    def _claim(idx: int, focus: str) -> EvidenceClaim:
        from accessible_surfaceome.tools._shared.models import AssayContext

        return EvidenceClaim(
            evidence_id=f"{focus}_evi_{idx:02d}",
            claim=f"Stub claim {idx} for {focus}.",
            claim_type="surface_expression",
            direction="supports",
            evidence_type="flow_cytometry",
            evidence_tier="primary",
            confidence="moderate",
            assay_context=AssayContext(species="human"),
            source_id=f"PMID:{idx + 100}",
            quote=f"Stub quote {idx} for {focus}.",
            section="results",
        )

    a1 = PlanTrimSelectResult(
        gene="FOO",
        bundle=bundle,
        plan=None,
        selection_response=None,
        agent_focus="a1",
        claims=[_claim(i, "a1") for i in range(n_a1_claims)],
        n_claims=n_a1_claims,
        n_anchored=n_a1_claims,
    )
    a2 = PlanTrimSelectResult(
        gene="FOO",
        bundle=bundle,
        plan=None,
        selection_response=None,
        agent_focus="a2",
        claims=[_claim(i, "a2") for i in range(n_a2_claims)],
        n_claims=n_a2_claims,
        n_anchored=n_a2_claims,
    )
    return DualPlanTrimSelectResult(
        gene="FOO",
        bundle=bundle,
        a1=a1,
        a2=a2,
        elapsed_s=42.0,
    )


def test_checkpoint_path_filesystem_safe(tmp_path: Path) -> None:
    """HGNC ids carry colons; the path must rewrite them so the filename
    is filesystem-safe (no directory traversal, no colon problems on
    Windows). Plain symbols pass through unchanged.
    """
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        p1 = orchestrator._checkpoint_path("HGNC:1234")
        p2 = orchestrator._checkpoint_path("FOO")
    assert ":" not in p1.name
    assert p1.name == "HGNC_1234.pts.json"
    assert p2.name == "FOO.pts.json"


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """The serialized dual round-trips: load reconstructs the bundle +
    both side ledgers with the same claim ids the original carried.
    The orchestrator's downstream pipeline reads dual.bundle, dual.a1,
    dual.a2 — all three are present and consistent.
    """
    dual = _make_dual(n_a1_claims=2, n_a2_claims=3)
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        orchestrator._save_pts_checkpoint("FOO", dual)
        loaded = orchestrator._load_pts_checkpoint("FOO")

    assert loaded is not None
    assert loaded.bundle is not None
    assert loaded.bundle.hgnc_symbol == "FOO"
    assert loaded.bundle.uniprot_acc == "P12345"
    assert len(loaded.a1.claims) == 2
    assert len(loaded.a2.claims) == 3
    assert loaded.a1.agent_focus == "a1"
    assert loaded.a2.agent_focus == "a2"
    assert {c.evidence_id for c in loaded.a1.claims} == {"a1_evi_00", "a1_evi_01"}
    assert {c.evidence_id for c in loaded.a2.claims} == {
        "a2_evi_00",
        "a2_evi_01",
        "a2_evi_02",
    }
    # Replay cost is always zero — that's the whole point.
    assert loaded.total_cost_usd == 0.0


def test_load_missing_returns_none(tmp_path: Path) -> None:
    """No checkpoint file → None (callers fall through to fresh PTS)."""
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        assert orchestrator._load_pts_checkpoint("NOFILE") is None


def test_load_corrupt_returns_none(tmp_path: Path) -> None:
    """A corrupt JSON checkpoint must not crash the orchestrator —
    callers fall through to fresh PTS instead.
    """
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        path = orchestrator._checkpoint_path("CORRUPT")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ this is not valid json")
        assert orchestrator._load_pts_checkpoint("CORRUPT") is None


def test_load_missing_bundle_returns_none(tmp_path: Path) -> None:
    """A checkpoint with no bundle field is too-old shape for the
    current builder/synth path; load returns None so the orchestrator
    re-runs PTS fresh.
    """
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        path = orchestrator._checkpoint_path("OLD")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "gene": "OLD",
                    "a1": {"agent_focus": "a1", "claims": []},
                    "a2": {"agent_focus": "a2", "claims": []},
                    # no "bundle" key — pre-v2.34 shape
                }
            )
        )
        assert orchestrator._load_pts_checkpoint("OLD") is None


def test_delete_removes_file(tmp_path: Path) -> None:
    """After a successful gene, the checkpoint is cleared so the next
    run starts fresh.
    """
    dual = _make_dual()
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        orchestrator._save_pts_checkpoint("FOO", dual)
        assert orchestrator._checkpoint_path("FOO").exists()
        orchestrator._delete_pts_checkpoint("FOO")
        assert not orchestrator._checkpoint_path("FOO").exists()


def test_delete_missing_is_noop(tmp_path: Path) -> None:
    """Deleting a non-existent checkpoint must not raise — the
    orchestrator calls delete on every success regardless of whether a
    checkpoint was written this run.
    """
    with patch.object(orchestrator, "_CHECKPOINT_DIR", tmp_path):
        # Must not raise.
        orchestrator._delete_pts_checkpoint("NEVER_SAVED")


def test_save_creates_directory(tmp_path: Path) -> None:
    """First-ever save on a fresh worktree must create the
    .runs/_phase_checkpoint/ directory rather than failing on missing
    parent dirs.
    """
    nested = tmp_path / "deeply" / "nested" / "ckpt"
    with patch.object(orchestrator, "_CHECKPOINT_DIR", nested):
        orchestrator._save_pts_checkpoint("FOO", _make_dual())
        assert nested.exists()
        assert (nested / "FOO.pts.json").exists()


def test_pts_cost_cap_constant_is_5_usd() -> None:
    """Sanity-check the PTS-level cap is set to $5 — separate from the
    $7 total ceiling PR54 has post-builders. The constant was promoted to
    module scope (so the resume path can reference it); this test would fail
    if a later edit dropped the cap or changed its value.
    """
    import inspect

    assert orchestrator.MAX_PTS_COST_USD == 5.0
    source = inspect.getsource(orchestrator._annotate)
    assert "PTS-level cost ceiling exceeded" in source


def test_pts_cap_checked_before_any_checkpoint_write() -> None:
    """Invariant (regression guard): the PTS cost-cap abort must run BEFORE
    either checkpoint write, so an over-cap dual never leaves a *resumable*
    checkpoint (on-disk or durable D1) that could auto-resume past the cap on
    re-dispatch. Pinned by source order — cheap and catches a reorder.
    """
    import inspect

    source = inspect.getsource(orchestrator._annotate)
    cap_idx = source.index("PTS-level cost ceiling exceeded")
    # Match the call sites (trailing "(") so a prose comment mentioning the
    # function names can't satisfy the search.
    assert cap_idx < source.index("_save_pts_checkpoint("), (
        "PTS cap check must precede the on-disk checkpoint write"
    )
    assert cap_idx < source.index("_publish_pts_checkpoint("), (
        "PTS cap check must precede the durable D1 checkpoint publish"
    )
