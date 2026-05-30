"""Regression: the resolver's ``uniprot_family`` must be the parsed UniProt
SIMILARITY family string — NOT the accession.

All four ``IdentifierBundle(...)`` constructors in ``gene_lookup.py`` used
to pass ``uniprot_family=uniprot_acc`` (a copy-paste of the accession kwarg),
so the correctly-computed ``_uniprot_family(entry)`` local was discarded and
every record's deterministic ``uniprot_family`` came back as the accession
(e.g. EGFR -> "P00533"). The viewer's "Family & gene group" deterministic
bucket then rendered nothing useful. Lock the field to the SIMILARITY string.

Network-backed (live HGNC + UniProt), skipped when
``ACCESSIBLE_SURFACEOME_NO_NETWORK=1`` — mirrors test_gene_lookup_resolver.py.
"""

from __future__ import annotations

import os

import pytest

from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

pytestmark = pytest.mark.skipif(
    os.environ.get("ACCESSIBLE_SURFACEOME_NO_NETWORK") == "1",
    reason="net",
)


@pytest.fixture(scope="module")
def http():
    import httpx

    with httpx.Client(timeout=30) as client:
        yield client


def test_egfr_uniprot_family_is_similarity_not_accession(http):
    bundle = resolve_by_hgnc_id("HGNC:3236", http=http)  # EGFR
    assert bundle.uniprot_acc == "P00533"
    # The bug: this used to equal the accession.
    assert bundle.uniprot_family != bundle.uniprot_acc
    assert bundle.uniprot_family is not None
    # EGFR's well-known SIMILARITY family path.
    assert "Protein kinase superfamily" in bundle.uniprot_family
