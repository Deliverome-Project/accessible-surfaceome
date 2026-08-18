"""Per-isoform shared/unique classification (tag_sites/isoform.py)."""
from accessible_surfaceome.tag_sites.isoform import (
    classify_isoform_sites,
    isoform_to_canonical_map,
)


def _det(site_id, res, kind="internal", det_path="surface_loop"):
    return {
        "site_id": site_id, "provenance": "deterministic_computed",
        "det_path": det_path, "site_kind": kind, "insert_after_residue": res,
        "tag_type": "ALFA",
    }


def test_identity_map_is_1to1():
    seq = "ACDEFGHIKL"
    assert isoform_to_canonical_map(seq, seq) == {i: i for i in range(1, 11)}


def test_deletion_shifts_downstream_residues():
    # canonical ABCDEFGHIJ; isoform deletes G,H (canonical 7-8) -> ABCDEFIJ.
    canon = "ABCDEFGHIJ"
    iso = "ABCDEFIJ"
    m = isoform_to_canonical_map(canon, iso)
    assert m[1] == 1 and m[6] == 6          # prefix unchanged
    assert m[7] == 9 and m[8] == 10          # isoform I,J -> canonical 9,10 (shifted)


def test_insertion_residues_have_no_canonical_counterpart():
    # canonical ABCDEF; isoform inserts XYZ after C -> ABCXYZDEF.
    m = isoform_to_canonical_map("ABCDEF", "ABCXYZDEF")
    assert 4 not in m and 5 not in m and 6 not in m   # X,Y,Z are isoform-unique
    assert m[3] == 3 and m[7] == 4                    # C stays; D re-aligns to canonical 4


def test_shared_when_isoform_site_maps_to_canonical_site():
    canon = "A" * 200
    iso = "A" * 200
    canon_sites = [_det("X-surface_loop-100", 100)]
    iso_sites = [_det("X-surface_loop-100", 100)]
    pins = classify_isoform_sites(
        isoform_id="X-2", isoform_sites=iso_sites, isoform_sequence=iso,
        canonical_sites=canon_sites, canonical_sequence=canon,
    )
    assert len(pins) == 1
    assert pins[0]["classification"] == "shared"
    assert pins[0]["left_pct"] == 50.0


def test_unique_when_isoform_site_has_no_canonical_neighbor():
    # isoform has a 3-residue insertion carrying a site; canonical has no site there.
    canon = "ABCDEF" + "G" * 100
    iso = "ABC" + "MNPQR" + "DEF" + "G" * 100  # 5-residue insertion after C
    canon_sites = [_det("X-surface_loop-90", 90)]           # far away on canonical
    iso_sites = [_det("X-surface_loop-5", 5)]               # inside the insertion (M..R)
    pins = classify_isoform_sites(
        isoform_id="X-2", isoform_sites=iso_sites, isoform_sequence=iso,
        canonical_sites=canon_sites, canonical_sequence=canon,
    )
    assert pins[0]["classification"] == "unique"
    assert pins[0]["canonical_residue"] is None


def test_truncated_cterm_is_unique_terminal():
    # A truncation isoform: its NEW C-terminus is far from the canonical C-term,
    # so the isoform terminal_c is unique. (Varied sequence — a homopolymer would
    # align degenerately and defeat the test.)
    canon = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKR"
    iso = canon[:40]  # C-terminal truncation at residue 40
    canon_sites = [_det("X-terminal-c", len(canon), kind="terminal_c", det_path="terminal")]
    iso_sites = [_det("X-terminal-c", len(iso), kind="terminal_c", det_path="terminal")]
    pins = classify_isoform_sites(
        isoform_id="X-2", isoform_sites=iso_sites, isoform_sequence=iso,
        canonical_sites=canon_sites, canonical_sequence=canon,
    )
    # isoform C-term (residue 40) aligns to canonical 40, far from the canonical
    # terminal at len(canon)=77 -> unique.
    assert pins[0]["canonical_residue"] == 40
    assert pins[0]["classification"] == "unique"
    assert pins[0]["left_pct"] == 100.0


def test_run_isoform_pins_orchestration(monkeypatch):
    # Injected fetch_pdb + stubbed gate internals: verifies the loop runs the
    # gates per isoform, classifies vs canonical, and skips isoforms AFDB 404s.
    from accessible_surfaceome.tag_sites import run as R

    monkeypatch.setattr(R, "compute_signals", lambda *a, **k: {"sequence": k["sequence"]})
    # isoform "X-2" nominates a site at residue 100 (matches a canonical site -> shared)
    monkeypatch.setattr(
        R, "derive_deterministic_sites",
        lambda gene, acc, *, signals: [_det("X-surface_loop-100", 100)],
    )

    def fetch_pdb(acc):
        if acc == "X-3":
            raise RuntimeError("AFDB 404 — no isoform model")  # -> skipped
        return f"/fake/{acc}.pdb"

    canon = "A" * 200
    pins = R.run_isoform_pins(
        "X", "P0",
        canonical_sequence=canon,
        canonical_sites=[_det("X-surface_loop-100", 100)],
        isoforms=[("X-2", "A" * 200, "O" * 200), ("X-3", "A" * 150, "O" * 150)],
        fetch_pdb=fetch_pdb,
    )
    assert {p["isoform_id"] for p in pins} == {"X-2"}       # X-3 skipped (404)
    assert pins[0]["classification"] == "shared"
