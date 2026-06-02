"""Tests for publish-time family self-heal (Chunk 2 of the PR #47 redesign).

``_heal_family_in_place`` re-asserts the deterministic, hgnc_id-keyed family
tags on every publish surface. It is cheap (no network) for healthy records,
guards against overwriting populated fields with empty resolved values, and
never breaks publish on a resolver miss.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from accessible_surfaceome.cloud.surface_annotation import _heal_family_in_place


class _FakeBundle:
    def __init__(self, groups: list[str], family: str | None) -> None:
        self.hgnc_gene_groups = groups
        self.uniprot_family = family


def _rec(groups, family, hgnc_id="HGNC:3236"):
    return {
        "gene": {"hgnc_symbol": "EGFR", "hgnc_id": hgnc_id},
        "executive_summary": {
            "hgnc_gene_groups": groups,
            "uniprot_family": family,
        },
    }


def _patch_resolver(bundle):
    """Patch the resolver + the http factory at their source modules (the
    self-heal imports them locally at call time)."""
    return (
        patch(
            "accessible_surfaceome.tools.gene_lookup.resolve_by_hgnc_id",
            return_value=bundle,
        ),
        patch(
            "accessible_surfaceome.tools._shared.http.open_default_client",
            return_value=object(),
        ),
    )


def test_heals_empty_family_fields_from_resolver():
    rec = _rec([], None)
    bundle = _FakeBundle(["CD molecules", "RTKs"], "Protein kinase superfamily")
    p_resolve, p_http = _patch_resolver(bundle)
    with p_resolve as m_resolve, p_http:
        healed = _heal_family_in_place(rec)
    assert healed is True
    assert rec["executive_summary"]["hgnc_gene_groups"] == ["CD molecules", "RTKs"]
    assert rec["executive_summary"]["uniprot_family"] == "Protein kinase superfamily"
    m_resolve.assert_called_once()


def test_healthy_record_skips_network():
    # Both fields populated → return early, never touch the resolver.
    rec = _rec(["CD molecules"], "Protein kinase superfamily")
    resolver = MagicMock()
    with patch(
        "accessible_surfaceome.tools.gene_lookup.resolve_by_hgnc_id", resolver
    ):
        healed = _heal_family_in_place(rec)
    assert healed is False
    resolver.assert_not_called()


def test_populated_to_empty_guard():
    # Existing groups populated, family empty. Resolver returns empty groups
    # + a real family → the populated groups must NOT be wiped; family fills.
    rec = _rec(["CD molecules"], None)
    bundle = _FakeBundle([], "Protein kinase superfamily")
    p_resolve, p_http = _patch_resolver(bundle)
    with p_resolve, p_http:
        healed = _heal_family_in_place(rec)
    assert healed is True
    assert rec["executive_summary"]["hgnc_gene_groups"] == ["CD molecules"]  # kept
    assert rec["executive_summary"]["uniprot_family"] == "Protein kinase superfamily"


def test_no_hgnc_id_is_noop():
    rec = _rec([], None, hgnc_id=None)
    resolver = MagicMock()
    with patch(
        "accessible_surfaceome.tools.gene_lookup.resolve_by_hgnc_id", resolver
    ):
        healed = _heal_family_in_place(rec)
    assert healed is False
    resolver.assert_not_called()


def test_resolver_failure_is_swallowed():
    rec = _rec([], None)
    with patch(
        "accessible_surfaceome.tools.gene_lookup.resolve_by_hgnc_id",
        side_effect=RuntimeError("network down"),
    ), patch(
        "accessible_surfaceome.tools._shared.http.open_default_client",
        return_value=object(),
    ):
        healed = _heal_family_in_place(rec)
    assert healed is False
    # Record left untouched — publish proceeds.
    assert rec["executive_summary"]["hgnc_gene_groups"] == []
    assert rec["executive_summary"]["uniprot_family"] is None
