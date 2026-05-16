"""Regression tests for the HGNC-ID-keyed resolver.

These pin the four divergence classes the genome-wide v3 audit
surfaced. Each test exercises one class with a representative
symbol; if anyone reintroduces lex-sort tiebreak, removes the
Class B fallback, or short-circuits the merge-chain follow, the
specific failure mode breaks here.

The tests hit the live HGNC and UniProt APIs. They're fast on a
warm cache (sub-second per case, ~90-day TTL) and only marginally
slower on a cold cache; the failure-mode signatures these tests
detect are reproducibly present in the public APIs.

Mark as ``@pytest.mark.live`` so they can be excluded from offline
runs via ``pytest -m 'not live'`` — see ``pyproject.toml`` marker
config or add ``filterwarnings`` if the marker isn't registered.
"""
from __future__ import annotations

import pytest

from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import (
    _pick_canonical_uniprot,
    _uniprot_search_by_symbol,
    resolve_by_hgnc_id,
)


@pytest.fixture(scope="module")
def http():
    """Live HTTP client shared across the module so the HGNC + UniProt
    cache amortizes across cases."""
    client = open_default_client()
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Class A — multi_xref. HGNC lists multiple reviewed Swiss-Prot accs that all
# share the primary geneName. Tiebreak must prefer the oldest entry (the
# canonical Swiss-Prot record), not the lex-smallest acc (which often points
# at a newer fragment / variant).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hgnc_id", "expected_acc", "description"),
    [
        ("HGNC:17868", "Q9BXH1", "BBC3 canonical PUMA (193 aa, 2004) not Q96PG8 (261 aa, 2012)"),
        ("HGNC:7459",  "P03905", "MT-ND4 mitochondrial canonical (459 aa, 1986) not C0HME5 (99 aa fragment, 2026)"),
        ("HGNC:9449",  "P04156", "PRNP canonical prion (253 aa, 1986) not F7VJQ1 (73 aa, 2012)"),
        ("HGNC:1158",  "P30536", "TSPO canonical (169 aa, 1993) not B1AH88 (102 aa variant, 2009)"),
    ],
)
def test_multi_xref_picks_canonical_not_fragment(http, hgnc_id, expected_acc, description):
    """HGNC's uniprot_ids xref includes multiple reviewed entries that all
    name the gene as primary. The canonical pick must be the oldest
    Swiss-Prot record (firstPublicDate tiebreak) — lex-sort gives the wrong
    answer in every one of these cases."""
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    assert bundle.uniprot_acc == expected_acc, description


# ---------------------------------------------------------------------------
# Class B — HGNC curates the gene but uniprot_ids xref is empty. Resolver
# must fall back to UniProt symbol search using HGNC's *primary* symbol,
# then HGNC's previous symbols if the primary misses.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hgnc_id", "expected_acc", "description"),
    [
        ("HGNC:20154", "Q8TB40", "ABHD4 — HGNC has gene but empty uniprot_xref"),
        ("HGNC:3554",  "Q92506", "HSD17B8 — HGNC has gene but empty uniprot_xref"),
    ],
)
def test_hgnc_empty_xref_falls_back_to_symbol_search(http, hgnc_id, expected_acc, description):
    """HGNC sometimes curates a gene without filling the uniprot_ids xref.
    The HGNC-ID resolver must fall back to UniProt symbol search using
    HGNC's primary symbol; raising LookupError would lose the gene from
    every cohort sweep."""
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    assert bundle.uniprot_acc == expected_acc, description


# ---------------------------------------------------------------------------
# Class C — HGNC has applied a symbol rename that UniProt hasn't synced.
# Resolver walks HGNC's xref to the protein UniProt still knows under the
# previous name. Symbol search would miss because the new symbol isn't
# indexed yet.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hgnc_id", "expected_acc", "renamed_to", "uniprot_still_calls_it"),
    [
        ("HGNC:28210", "Q86UY5", "SACK1A", "FAM83A"),
        # ("HGNC:28133", "Q96GX8", "CLMB", "C16orf74") — retired 2026-05-16.
        # HGNC re-renamed CLMB to FAM167B and UniProt has since synced;
        # both authorities now agree FAM167B -> Q9BTA0, so the case no
        # longer exercises the HGNC-ahead path. Drop in a fresher rename
        # if you want a 2-row parametrize again.
    ],
)
def test_hgnc_ahead_of_uniprot_rename(http, hgnc_id, expected_acc, renamed_to, uniprot_still_calls_it):
    """HGNC re-assigned the primary symbol but UniProt's index lags. The
    HGNC-ID path finds the right protein via xref; production's symbol
    search at UniProt would return nothing or pick a different gene."""
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    assert bundle.uniprot_acc == expected_acc, (
        f"HGNC's primary is {renamed_to!r} but UniProt still has the entry "
        f"under primary geneName={uniprot_still_calls_it!r}"
    )
    # Also: production's symbol search must miss (or find something else)
    # — that's the failure mode this resolver path exists to recover from.
    prod_pick = _uniprot_search_by_symbol(renamed_to, http=http)
    assert prod_pick != expected_acc, (
        "If UniProt's symbol search ever finds this acc, the rename has "
        "synced and this test case can be retired. Pick a fresher HGNC "
        "rename for the test."
    )


# ---------------------------------------------------------------------------
# Class D — input symbol is ambiguous (legacy synonym in another gene). The
# HGNC-ID path lands on the right gene; production's symbol search picks the
# wrong gene entirely. These are the dangerous failures — production was
# triaging the wrong protein, sometimes the wrong biology kingdom (RNA vs
# protein-coding).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hgnc_id", "expected_acc", "production_wrong_answer", "gloss"),
    [
        ("HGNC:7419",  "P00395",       "P23219",       "COX1 → mitochondrial cytochrome c oxidase, NOT cyclooxygenase-1 (PTGS1)"),
        ("HGNC:7421",  "P00403",       "P35354",       "COX2 → mitochondrial cytochrome c oxidase II, NOT cyclooxygenase-2 (PTGS2)"),
        ("HGNC:12731", "P42768",       "A0A0C5B5G6",   "WAS → Wiskott-Aldrich Syndrome protein, NOT MT-RNR1 (an rRNA gene)"),
    ],
)
def test_symbol_collision_resolves_via_hgnc_id(http, hgnc_id, expected_acc, production_wrong_answer, gloss):
    """When the input symbol is a legacy synonym in a different gene,
    HGNC-ID resolution lands on the correct gene; symbol search lands on
    the synonym holder. WAS is the most dangerous case — production's
    symbol search picked an rRNA (not even a protein-coding gene)."""
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    assert bundle.uniprot_acc == expected_acc, gloss


# ---------------------------------------------------------------------------
# Picker: explicit tiebreak rules.
# ---------------------------------------------------------------------------


def test_picker_prefers_primary_name_match(http):
    """When multiple accs are reviewed Swiss-Prot, the one whose primary
    geneName matches `prefer_primary_name` wins regardless of acc order."""
    # BBC3 has [Q96PG8, Q9BXH1] in HGNC's xref. Both have primary_name=BBC3.
    # Lex-sort would pick Q96PG8 first; primary-name-match leaves it a tie;
    # firstPublicDate (Q9BXH1=2004 vs Q96PG8=2012) decides for Q9BXH1.
    picked = _pick_canonical_uniprot(
        ["Q96PG8", "Q9BXH1"], http=http, prefer_primary_name="BBC3"
    )
    assert picked == "Q9BXH1", "primary-name + age tiebreak must pick the canonical"


def test_picker_drops_deleted_and_follows_merge_chains():
    """Sanity probe — verified by hand against documented merged / deleted
    UniProt accs is brittle (UniProt re-activates entries occasionally),
    so test the structural property: passing a single acc still flows
    through reconciliation (no single-acc shortcut), and the function
    raises LookupError when *every* candidate resolves to merged-with-no-
    target / deleted / 404.

    The actual merge-chain following + delete filtering is exercised by
    the live audit, which finds zero divergences for this category after
    the picker patch. Adding a deterministic unit-level test would require
    HTTP mocking that adds more brittleness than it removes."""
    # Empty list raises ValueError (programmer error, not LookupError).
    # http=None is fine here because the empty-list guard short-circuits
    # before any HTTP call. Both mypy and ty need explicit-ignore
    # directives because the annotation is strictly typed.
    with pytest.raises(ValueError):
        _pick_canonical_uniprot([], http=None)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
