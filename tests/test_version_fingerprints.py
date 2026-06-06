"""Guardrail: schema + prompt changes must come with a version bump.

These tests pin a fingerprint of each versioned artifact — the
``SurfaceomeRecord`` and ``TriageRecord`` Pydantic schemas, and the agent
prompt corpus — to its declared version in
``tests/version_fingerprints.json``. If an artifact's *content* changes but
its version + recorded fingerprint weren't updated together, the guardrail
fails. The fix is a deliberate version bump followed by
``uv run python scripts/update_version_fingerprints.py``, which refuses to
record a new fingerprint under an unchanged version — so the bump can't be
skipped.

Root cause this prevents: ``SurfaceomeRecord``'s schema was reworked
repeatedly while ``schema_version`` stayed pinned at ``1.1.0``, so every
record (and the viewer's freshness check) thought it was current when it
wasn't.
"""

from accessible_surfaceome import _version_guard as vg
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


def test_schema_fingerprint_is_deterministic_hex() -> None:
    a = vg.schema_fingerprint(SurfaceomeRecord)
    b = vg.schema_fingerprint(SurfaceomeRecord)
    assert a == b
    assert len(a) == 64 and all(c in "0123456789abcdef" for c in a)


def test_prompt_corpus_fingerprint_is_deterministic_and_nonempty() -> None:
    assert vg.prompt_files(), "expected agent prompt files to exist"
    a = vg.prompt_corpus_fingerprint()
    b = vg.prompt_corpus_fingerprint()
    assert a == b
    assert len(a) == 64


def test_reconcile_refuses_new_fingerprint_under_unchanged_version() -> None:
    golden = {"X": {"version": "1.0.0", "fingerprint": "aaa"}}
    current = {"X": {"version": "1.0.0", "fingerprint": "bbb"}}  # changed, same ver
    new_golden, errors = vg.reconcile(golden, current)
    assert errors, "content change without a version bump must error"
    assert new_golden == golden, "golden must be left unchanged when refused"


def test_reconcile_records_when_version_bumped() -> None:
    golden = {"X": {"version": "1.0.0", "fingerprint": "aaa"}}
    current = {"X": {"version": "1.1.0", "fingerprint": "bbb"}}
    new_golden, errors = vg.reconcile(golden, current)
    assert not errors
    assert new_golden["X"] == {"version": "1.1.0", "fingerprint": "bbb"}


def test_reconcile_adds_new_artifact_without_error() -> None:
    new_golden, errors = vg.reconcile(
        {}, {"X": {"version": "1.0.0", "fingerprint": "aaa"}}
    )
    assert not errors
    assert new_golden["X"]["fingerprint"] == "aaa"


def test_reconcile_is_noop_when_unchanged() -> None:
    golden = {"X": {"version": "1.0.0", "fingerprint": "aaa"}}
    new_golden, errors = vg.reconcile(golden, {k: dict(v) for k, v in golden.items()})
    assert not errors
    assert new_golden == golden


def test_committed_golden_matches_current_artifacts() -> None:
    """The actual guardrail. Fails when a schema/prompt drifted from its
    recorded version+fingerprint. Fix: bump the version, then run
    ``uv run python scripts/update_version_fingerprints.py``."""
    current = vg.current_fingerprints()
    golden = vg.load_golden()
    new_golden, errors = vg.reconcile(golden, current)
    assert not errors, "Version-bump guardrail tripped:\n" + "\n".join(errors)
    assert new_golden == golden, (
        "tests/version_fingerprints.json is out of date (a version moved or an "
        "artifact was added without regenerating the golden). Run "
        "scripts/update_version_fingerprints.py."
    )
