"""Closed-enum + backward-compat coercion tests for ``MembraneSubdomain``.

``MembraneSubdomain.subdomain`` was free text, which let models emit
"cilia" / "primary cilium" / "Primary Cilium" for the same biology and broke
grouping queries. It is now the closed ``MembraneSubdomainName`` Literal, with
a ``mode="before"`` validator that NORMALIZES any incoming string (so legacy
free-text records still load) and coerces anything unrecognized to ``"other"``.
"""

from __future__ import annotations

import typing

import pytest

from accessible_surfaceome.tools._shared.models import (
    MembraneSubdomain,
    MembraneSubdomainName,
)

_CANONICAL = (
    "lipid_raft",
    "tight_junction",
    "primary_cilium",
    "apical_membrane",
    "basolateral_membrane",
    "immune_synapse",
    "focal_adhesion",
    "caveolae",
    "other",
)


def _subdomain(raw: str) -> str:
    """Build a ``MembraneSubdomain`` from a (possibly free-text) value.

    Goes through ``model_validate`` with a dict — the path legacy JSON
    records actually take — so the closed-enum field type doesn't reject the
    free-text test inputs at static-check time.
    """
    return MembraneSubdomain.model_validate({"subdomain": raw}).subdomain


# --------------------------------------------------------------------------
# The field is a closed Literal of exactly the canonical tokens.
# --------------------------------------------------------------------------


def test_subdomain_is_closed_literal():
    assert typing.get_origin(MembraneSubdomainName) is typing.Literal
    assert set(typing.get_args(MembraneSubdomainName)) == set(_CANONICAL)


@pytest.mark.parametrize("value", _CANONICAL)
def test_canonical_values_pass_through(value: str):
    assert _subdomain(value) == value


# --------------------------------------------------------------------------
# Legacy free-text coerces to the right canonical value.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # cilium family
        ("cilia", "primary_cilium"),
        ("cilium", "primary_cilium"),
        ("Primary Cilium", "primary_cilium"),
        ("primary cilium", "primary_cilium"),
        ("ciliary", "primary_cilium"),
        ("ciliary membrane", "primary_cilium"),
        # lipid raft family
        ("lipid raft", "lipid_raft"),
        ("lipid rafts", "lipid_raft"),
        ("Lipid Rafts", "lipid_raft"),
        ("raft", "lipid_raft"),
        ("rafts", "lipid_raft"),
        ("membrane raft", "lipid_raft"),
        # apical
        ("apical", "apical_membrane"),
        ("apical membrane", "apical_membrane"),
        ("apical surface", "apical_membrane"),
        # basolateral
        ("basolateral", "basolateral_membrane"),
        ("basolateral membrane", "basolateral_membrane"),
        # tight junction
        ("tight junction", "tight_junction"),
        ("tight junctions", "tight_junction"),
        ("zonula occludens", "tight_junction"),
        # immune synapse
        ("immune synapse", "immune_synapse"),
        ("immunological synapse", "immune_synapse"),
        ("immunologic synapse", "immune_synapse"),
        # focal adhesion
        ("focal adhesion", "focal_adhesion"),
        ("focal adhesions", "focal_adhesion"),
        # caveolae
        ("caveolae", "caveolae"),
        ("caveola", "caveolae"),
        ("caveolar", "caveolae"),
    ],
)
def test_legacy_free_text_coerces_to_canonical(raw: str, expected: str):
    assert _subdomain(raw) == expected


def test_normalization_handles_mixed_separators_and_whitespace():
    # lowercase + strip + collapse runs of space/hyphen/underscore to one "_".
    assert _subdomain("  Lipid--Rafts ") == "lipid_raft"
    assert _subdomain("tight-junctions") == "tight_junction"
    assert _subdomain("primary_cilium") == "primary_cilium"


# --------------------------------------------------------------------------
# Genuinely-unknown values coerce to "other" — never rejected (backward-compat).
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "nucleus",
        "weird thing",
        "",
        "inner leaflet",
        "inner leaflet / cytoplasmic face of plasma membrane",
    ],
)
def test_unknown_values_coerce_to_other(raw: str):
    assert _subdomain(raw) == "other"
