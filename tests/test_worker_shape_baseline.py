"""The committed live-response-shape baseline, and what it must contain.

``scripts/cloud/worker_shape_guard.py`` compares production's response key paths
against this file, because the deploy checklist's source comparisons cannot see
a field that exists in no branch — which is exactly what gets deleted when two
sessions deploy the shared Worker from unmerged branches on the same day.

A baseline is only as good as what it was captured from. These tests pin the
fields whose loss motivated the guard, so regenerating it against a Worker that
has ALREADY dropped them fails here instead of blessing the regression as the
new contract.
"""

from __future__ import annotations

import json

import pytest

from accessible_surfaceome.paths import REPO_ROOT

BASELINE = (
    REPO_ROOT / "cloudflare/workers/surfaceome_api/tests/live_shape_baseline.json"
)


@pytest.fixture(scope="module")
def shape() -> dict[str, list[str]]:
    assert BASELINE.is_file(), (
        "no live-shape baseline; run "
        "`uv run python scripts/cloud/worker_shape_guard.py --capture`"
    )
    return json.loads(BASELINE.read_text())["shape"]


def test_the_probe_set_is_heterogeneous(shape: dict[str, list[str]]) -> None:
    """One gene proves nothing. Most of these fields are GATED, and the first
    investigation of the 2026-10-15 incident briefly reached the wrong
    conclusion by checking CD63 — a non-member — for member-gated keys."""
    assert {"gene_library_member", "gene_non_member"} <= set(shape)
    assert {"tag_sites_frame_mapped", "tag_sites_det_only"} <= set(shape)
    assert "gene_bindome_member" in shape


def test_the_member_gated_keys_are_present_on_a_member(
    shape: dict[str, list[str]],
) -> None:
    """`library_designed_structure` / `_topology` exist only on origin/dev and
    only for library members. They are the clearest marker of which branch the
    live Worker was built from."""
    member = set(shape["gene_library_member"])
    assert "deterministic_features.library_designed_structure" in member
    assert "deterministic_features.library_designed_topology" in member


def test_the_member_gated_keys_are_absent_on_a_non_member(
    shape: dict[str, list[str]],
) -> None:
    """Gated, not universal — so a guard that only probed a member could not
    tell "this field is gated" from "this field is gone"."""
    non_member = set(shape["gene_non_member"])
    assert "deterministic_features.library_designed_structure" not in non_member


def test_bindome_is_promised_on_a_bearing_gene(
    shape: dict[str, list[str]],
) -> None:
    """`deterministic_features.bindome` was deployed from an unmerged branch on
    2026-10-15 (33c513e6) and silently dropped by the next deploy. It is gated
    on the 1,391 proteins that have Bindome sites, and no other probe has any —
    so the first run of this guard passed with "0 added" while the field it was
    built to protect was invisible to it."""
    bearing = set(shape["gene_bindome_member"])
    assert "deterministic_features.bindome" in bearing
    assert "deterministic_features.bindome.n_sites" in bearing


def test_bindome_is_absent_on_a_non_bearing_gene(
    shape: dict[str, list[str]],
) -> None:
    """Gated, not universal — the same presence/absence pair the library keys
    need, for the same reason."""
    assert "deterministic_features.bindome" not in set(shape["gene_non_member"])


def test_position_frame_is_promised_on_a_frame_mapped_tag_site(
    shape: dict[str, list[str]],
) -> None:
    """The field this session added, and the one a reconciling deploy from
    main+dev would silently drop — it is in neither branch."""
    assert "sites[].position_frame" in set(shape["tag_sites_frame_mapped"])


def test_the_dev_only_internalization_contract_is_promised(
    shape: dict[str, list[str]],
) -> None:
    """The standing dev-only contract named in CLAUDE.md. A deploy from an
    older branch would drop it and break the dev viewer."""
    assert shape.get("internalization"), "internalization probe missing"
    catalog = set(shape["catalog_head"])
    assert {"rows[].intern", "rows[].intern_lit", "rows[].intern_lit_grade"} <= catalog


def test_the_per_gene_search_facts_are_promised(shape: dict[str, list[str]]) -> None:
    """`prompt_sha` on the tag-sites response is what lets a reader tell "no
    published tag site exists" from "nobody looked" — 1,415 genes are the
    latter."""
    for probe in ("tag_sites_frame_mapped", "tag_sites_det_only"):
        assert "prompt_sha" in set(shape[probe]), probe


def test_every_probe_is_represented_in_the_baseline() -> None:
    """A probe added to PROBES but never `--capture`d is SILENTLY INERT.

    `check()` iterates `baseline["shape"].items()`, so it only ever compares
    probes the baseline already holds. Adding a probe without recapturing
    therefore buys nothing, and the guard reports PASS while the surface the new
    probe was meant to protect is unwatched — the same shape of failure as the
    original incident, one level up.

    The by-name assertions above are a forcing function only for fields someone
    thought to name twice. This makes it structural: any probe, named or not,
    must appear in the baseline.
    """
    import json

    from accessible_surfaceome.paths import REPO_ROOT

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "worker_shape_guard",
        REPO_ROOT / "scripts/cloud/worker_shape_guard.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = json.loads(BASELINE.read_text())["shape"]
    missing = [name for name, _ in mod.PROBES if name not in captured]
    assert not missing, (
        f"probes present in PROBES but absent from the baseline: {missing}. "
        "They contribute nothing until you run "
        "`uv run python scripts/cloud/worker_shape_guard.py --capture`."
    )


def test_the_baseline_has_no_orphan_probes() -> None:
    """And the reverse: a baseline entry whose probe was deleted is dead weight
    that would fail `check()` forever with '<entire probe unavailable>'."""
    import importlib.util
    import json

    from accessible_surfaceome.paths import REPO_ROOT

    spec = importlib.util.spec_from_file_location(
        "worker_shape_guard",
        REPO_ROOT / "scripts/cloud/worker_shape_guard.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = json.loads(BASELINE.read_text())["shape"]
    known = {name for name, _ in mod.PROBES}
    orphans = sorted(set(captured) - known)
    assert not orphans, f"baseline holds probes no longer in PROBES: {orphans}"
