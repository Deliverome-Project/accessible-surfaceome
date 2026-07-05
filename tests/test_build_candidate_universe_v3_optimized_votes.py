"""Guard: candidate_universe_v3 optimized DB vote must treat the
optimized-cutoffs table as a POSITIVE LIST — an accession absent from it
contributes (0, 0), it must NOT fall back to the initial UniProt/CSPA flag.

Per the Methods ("Treatment of source absence" + the CSPA recalibration), the
optimized CSPA rule is high-confidence-only and absence-from-source counts as a
"not surface" vote; the high-confidence tightening is documented to drop ~80
putative-CSPA-only proteins that no other source flags. The optimized-cutoffs
file (``db_optimized_cutoffs.tsv``) is built as a positive list of accessions
passing >=1 tightened cutoff (it carries no rows with both optimized flags 0),
so an accession's *absence* is itself the signal that it passed neither cutoff.

The earlier fallback ``_opt.get(acc, (initial_uniprot, initial_cspa))``
resurrected the un-tightened initial flag for absent accessions, re-admitting
exactly those putative-CSPA-only proteins the tightening exists to drop (e.g.
filamin / ryanodine-receptor / ER-resident proteins riding a low-confidence
CSPA hit). This pins the corrected behavior.

Pure-function test: imports the script via sys.path the way the repo's other
script tests do, so it must not trigger the module's D1 query at import time.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_candidate_universe_v3 as m  # noqa: E402  # ty: ignore[unresolved-import]


def _row(acc, uniprot, cspa, go=0, surfy=0, hpa=0):
    return {
        "uniprot_acc": acc,
        "uniprot_flag": str(uniprot),
        "cspa_flag": str(cspa),
        "go_flag": str(go),
        "surfy_flag": str(surfy),
        "hpa_flag": str(hpa),
    }


def test_absent_accession_contributes_zero_not_initial_flag():
    # Accession absent from the optimized table; initial UniProt AND CSPA both 1.
    # Optimized cutoffs are a positive list -> absent means it passed neither ->
    # both must contribute 0 (the initial flags must NOT be resurrected).
    m._opt.clear()
    r = _row("Q99999", uniprot=1, cspa=1, go=0, surfy=0, hpa=0)
    assert m._opt_votes(r) == 0


def test_absent_accession_still_counts_unchanged_go_surfy_hpa():
    # GO / SURFY / HPA are not recalibrated — their initial flag always stands.
    # Only UniProt and CSPA are zeroed for an absent accession.
    m._opt.clear()
    r = _row("Q99999", uniprot=1, cspa=1, go=1, surfy=1, hpa=0)
    assert m._opt_votes(r) == 2  # go + surfy; uniprot & cspa tightened to 0


def test_present_accession_uses_optimized_flags():
    m._opt.clear()
    m._opt["P12345"] = (1, 0)  # uniprot_optimized=1, cspa_optimized=0
    # initial cspa=1 but optimized cspa=0 -> cspa contributes 0; uniprot_opt=1.
    r = _row("P12345", uniprot=1, cspa=1, go=0, surfy=0, hpa=1)
    assert m._opt_votes(r) == 2  # uniprot_opt(1) + hpa(1); cspa optimized-out


def test_opt_membership_absent_is_zero_zero():
    m._opt.clear()
    assert m._opt_membership("NOPE") == (0, 0)


def test_opt_membership_present_returns_table_value():
    m._opt.clear()
    m._opt["P12345"] = (1, 1)
    assert m._opt_membership("P12345") == (1, 1)
