"""Deterministic homonym-aware gene grounding (gene_gazetteer).

Regression guard for the TF/F3 collision: HGNC lists ``TF`` as an alias of
F3 (tissue factor), so an F3 sentence written "tissue factor (TF/CD142)"
carries the shared ``TF`` token and would otherwise pass the plain target
check. ``homonym_competitor_tokens`` surfaces the competitor's
*distinguishing* token (``CD142``) so ``sentence_subject`` can reclassify
such a sentence as ``competing`` without dropping real target evidence.
"""
from __future__ import annotations

import textwrap

from accessible_surfaceome.tools._shared import gene_gazetteer as g

# Minimal HGNC-complete-set-shaped fixture: only the columns the loader reads.
_FIXTURE = textwrap.dedent(
    """\
    symbol\tname\tstatus\talias_symbol\tprev_symbol
    TF\ttransferrin\tApproved\tPRO1557|PRO2086\t
    F3\tcoagulation factor III, tissue factor\tApproved\tCD142|TF\t
    EGFR\tepidermal growth factor receptor\tApproved\tERBB1\tHER1
    """
)


def _fixture(tmp_path):
    p = tmp_path / "hgnc.tsv"
    p.write_text(_FIXTURE)
    g._gene_token_map.cache_clear()  # path-keyed lru; clear so the fixture wins
    return str(p)


def test_homonym_detects_f3_as_tf_competitor(tmp_path):
    path = _fixture(tmp_path)
    target = g.build_target_names("TF", ("PRO1557", "PRO2086"))
    distinguishing, shared = g.homonym_competitor_tokens("TF", target, path=path)
    # CD142 is the >=3-char distinguishing token; the bare 2-char F3 is floored out.
    assert "CD142" in distinguishing
    assert "TF" in shared  # the ambiguous shared symbol


def test_non_homonym_has_no_competitor(tmp_path):
    path = _fixture(tmp_path)
    target = g.build_target_names("EGFR", ("ERBB1",), ("HER1",))
    distinguishing, shared = g.homonym_competitor_tokens("EGFR", target, path=path)
    assert not distinguishing and not shared


def test_competing_sentence_reclassified(tmp_path):
    path = _fixture(tmp_path)
    target = g.build_target_names("TF", ("PRO1557", "PRO2086"))
    distinguishing, shared = g.homonym_competitor_tokens("TF", target, path=path)
    gz = g.load_gazetteer(path)
    core = target - shared
    # An F3/tissue-factor sentence carrying the shared "TF" token + CD142.
    f3 = "Anti-CD142 (tissue factor, TF) antibody stained the live-cell surface by flow cytometry."
    assert (
        g.sentence_subject(f3, target_names=target, gazetteer=gz,
                           competitors=distinguishing, target_core=core)
        == "competing"
    )


def test_real_serotransferrin_sentence_not_dropped(tmp_path):
    path = _fixture(tmp_path)
    target = g.build_target_names("TF", ("PRO1557", "PRO2086"))
    distinguishing, shared = g.homonym_competitor_tokens("TF", target, path=path)
    gz = g.load_gazetteer(path)
    core = target - shared
    # A serotransferrin sentence with no competitor-distinguishing token must
    # NOT be reclassified competing by the homonym guard.
    ser = "Serotransferrin is a secreted plasma glycoprotein that ferries iron."
    assert (
        g.sentence_subject(ser, target_names=target, gazetteer=gz,
                           competitors=distinguishing, target_core=core)
        != "competing"
    )


def test_homonym_guard_is_opt_in(tmp_path):
    # With no competitor args, behaviour is unchanged (backwards compatible).
    path = _fixture(tmp_path)
    gz = g.load_gazetteer(path)
    target = g.build_target_names("TF", ("PRO1557", "PRO2086"))
    f3 = "Anti-CD142 antibody stained the surface."
    # CD142 is a competing gene symbol -> the plain check already says competing.
    assert g.sentence_subject(f3, target_names=target, gazetteer=gz) == "competing"
