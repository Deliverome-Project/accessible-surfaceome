"""Tests for the HGNC gene-symbol gazetteer + the snippet subject filter.

Covers:

* **Normalization & tokenization** — ``normalize_symbol`` /
  ``extract_symbol_tokens`` agree on what counts as a symbol mention,
  and are case-sensitive so English words don't collide with genes.
* **Target-name building** — ``build_target_names`` keeps clean,
  long-enough aliases and drops short/ambiguous/phrase ones.
* **Gazetteer loading** — only ``Approved`` rows, alias columns
  expanded, denylist applied, graceful empty on a missing TSV.
* **Subject classification** — ``sentence_subject`` returns
  target/competing/neither, short-circuits on target, no-ops on empty
  dictionaries.
* **Filter integration** — ``_extract_snippets`` drops competing-gene
  sentences and boosts target sentences (the CALR→CD47 misfire).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.tools import evidence_retrieval as er
from accessible_surfaceome.tools._shared import gene_gazetteer as gg
from accessible_surfaceome.tools._shared.models import Paper, PaperSection


# ---------------------------------------------------------------------------
# normalize_symbol / extract_symbol_tokens
# ---------------------------------------------------------------------------


def test_normalize_symbol_strips_hyphens_and_upcases() -> None:
    assert gg.normalize_symbol("HER-2") == "HER2"
    assert gg.normalize_symbol("her2") == "HER2"
    assert gg.normalize_symbol("CD340") == "CD340"


def test_normalize_symbol_rejects_phrase_aliases() -> None:
    # Slashes, parentheses, spaces -> not symbol-shaped -> "".
    assert gg.normalize_symbol("HER-2/neu") == ""
    assert gg.normalize_symbol("p185(erbB2)") == ""
    assert gg.normalize_symbol("MLN 19") == ""
    assert gg.normalize_symbol("") == ""


def test_extract_symbol_tokens_is_case_sensitive() -> None:
    # Uppercase gene-shaped tokens are extracted; lowercase prose is not.
    assert gg.extract_symbol_tokens("CD47-positive tumor cells were stained") == ["CD47"]
    assert gg.extract_symbol_tokens("the cells were fixed and permeabilized") == []
    assert gg.extract_symbol_tokens("Unlike CD47, CALR is exposed") == ["CD47", "CALR"]


def test_extract_symbol_tokens_drops_short_tokens() -> None:
    # 2-char tokens ("AR", "RO") are too ambiguous to count.
    assert gg.extract_symbol_tokens("AR and RO were measured") == []
    assert "CD8" in gg.extract_symbol_tokens("CD8 T cells")


# ---------------------------------------------------------------------------
# build_target_names
# ---------------------------------------------------------------------------


def test_build_target_names_keeps_clean_aliases_drops_ambiguous() -> None:
    names = gg.build_target_names("CALR", ["RO", "SSA", "cC1qR", "CRT"], [])
    assert "CALR" in names          # canonical symbol
    assert "CRT" in names           # clean 3-char alias kept
    assert "RO" not in names        # 2-char -> dropped
    assert "CC1QR" in names         # "cC1qR" normalizes to a clean 5-char token


def test_build_target_names_drops_phrase_aliases() -> None:
    names = gg.build_target_names("ERBB2", ["HER2", "HER-2/neu", "p185(erbB2)"], ["NGL"])
    assert "ERBB2" in names
    assert "HER2" in names
    assert "NGL" in names
    # phrase aliases never make it in
    assert all("/" not in n and "(" not in n for n in names)


# ---------------------------------------------------------------------------
# load_gazetteer
# ---------------------------------------------------------------------------


def _write_hgnc_fixture(tmp_path: Path) -> Path:
    tsv = tmp_path / "hgnc_complete_set.tsv"
    header = "\t".join(["hgnc_id", "symbol", "status", "alias_symbol", "prev_symbol"])
    rows = [
        "\t".join(["HGNC:1", "ERBB2", "Approved", "NEU|HER2", "NGL"]),
        "\t".join(["HGNC:2", "CD47", "Approved", "", ""]),
        "\t".join(["HGNC:3", "TNFRSF17", "Approved", "BCMA|BCM", ""]),
        # not Approved -> excluded entirely
        "\t".join(["HGNC:4", "WDRAWN1", "Entry Withdrawn", "GHOST", ""]),
        # symbol coincides with a denylisted lab acronym -> excluded
        "\t".join(["HGNC:5", "DNA", "Approved", "", ""]),
    ]
    tsv.write_text(header + "\n" + "\n".join(rows) + "\n")
    return tsv


def test_load_gazetteer_includes_approved_symbols_and_aliases(tmp_path: Path) -> None:
    gg.load_gazetteer.cache_clear()
    g = gg.load_gazetteer(str(_write_hgnc_fixture(tmp_path)))
    assert "ERBB2" in g
    assert "HER2" in g        # alias column expanded
    assert "TNFRSF17" in g
    assert "BCMA" in g        # alias of TNFRSF17
    assert "NGL" in g         # prev_symbol column expanded


def test_load_gazetteer_excludes_non_approved_and_denylisted(tmp_path: Path) -> None:
    gg.load_gazetteer.cache_clear()
    g = gg.load_gazetteer(str(_write_hgnc_fixture(tmp_path)))
    assert "GHOST" not in g   # row was "Entry Withdrawn" -> whole row skipped
    assert "WDRAWN1" not in g
    assert "DNA" not in g     # denylisted lab acronym, even though Approved
    assert "NEU" in g         # 3-char alias, not denylisted -> kept


def test_load_gazetteer_missing_file_returns_empty(tmp_path: Path) -> None:
    gg.load_gazetteer.cache_clear()
    g = gg.load_gazetteer(str(tmp_path / "does_not_exist.tsv"))
    assert g == frozenset()


# ---------------------------------------------------------------------------
# sentence_subject
# ---------------------------------------------------------------------------


def test_sentence_subject_classifies_target_competing_neither() -> None:
    target = frozenset({"CALR", "CRT"})
    gazetteer = frozenset({"CALR", "CRT", "CD47", "CD55", "ERBB2"})

    assert gg.sentence_subject(
        "CALR is exposed on the cell surface", target_names=target, gazetteer=gazetteer
    ) == "target"
    assert gg.sentence_subject(
        "CD47 surface expression was analyzed by flow cytometry",
        target_names=target, gazetteer=gazetteer,
    ) == "competing"
    assert gg.sentence_subject(
        "The protein was detected on the surface of intact cells",
        target_names=target, gazetteer=gazetteer,
    ) == "neither"


def test_sentence_subject_short_circuits_on_target() -> None:
    # A sentence naming both the target and a sibling is kept as "target".
    target = frozenset({"CALR"})
    gazetteer = frozenset({"CALR", "CD47"})
    assert gg.sentence_subject(
        "Unlike CD47, CALR is surface-exposed during ICD",
        target_names=target, gazetteer=gazetteer,
    ) == "target"


def test_sentence_subject_noop_when_dictionaries_empty() -> None:
    # Backwards-compatible default: no dictionaries -> always "neither".
    assert gg.sentence_subject(
        "CD47 whatever", target_names=frozenset(), gazetteer=frozenset()
    ) == "neither"


# ---------------------------------------------------------------------------
# Filter integration in _extract_snippets
# ---------------------------------------------------------------------------


def _paper_with(sections: list[PaperSection]) -> Paper:
    return Paper(
        pmid=1,
        pmc_id="PMC1",
        title="multi-target immunotherapy paper",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=sections,
    )


def test_extract_snippets_drops_competing_gene_sentence() -> None:
    """The CALR->CD47 misfire: a CD47 surface sentence in a CALR query
    must not be returned."""
    paper = _paper_with([
        PaperSection(
            name="figure_legends",
            text=(
                "CD47 surface expression was analyzed using flow cytometry "
                "in lymphoma cell lines. "
                "CALR surface expression was confirmed by flow cytometry "
                "on intact tumor cells."
            ),
        )
    ])
    target = frozenset({"CALR", "CRT"})
    gazetteer = frozenset({"CALR", "CRT", "CD47"})
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=5,
        target_names=target,
        gazetteer=gazetteer,
    )
    texts = " || ".join(s.text for s in snippets)
    assert "CALR surface expression" in texts
    assert "CD47 surface expression" not in texts


def test_extract_snippets_boosts_target_sentence() -> None:
    """A sentence that names the target outranks an anaphoric one."""
    paper = _paper_with([
        PaperSection(
            name="results",
            text=(
                "The protein showed surface expression by flow cytometry. "
                "GPRC5D surface expression was confirmed by flow cytometry on intact cells."
            ),
        )
    ])
    target = frozenset({"GPRC5D"})
    gazetteer = frozenset({"GPRC5D"})
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=5,
        target_names=target,
        gazetteer=gazetteer,
    )
    assert snippets
    # The target-naming sentence ranks first thanks to the boost.
    assert "GPRC5D" in snippets[0].text


def test_extract_snippets_noop_without_dictionaries() -> None:
    """With empty dictionaries the filter is inert — competing-gene
    sentences are NOT dropped (backwards-compatible behaviour)."""
    paper = _paper_with([
        PaperSection(
            name="figure_legends",
            text="CD47 surface expression was analyzed using flow cytometry.",
        )
    ])
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=5,
    )
    assert any("CD47" in s.text for s in snippets)


# ---------------------------------------------------------------------------
# accepts_paper_level_evidence — per-category relaxation for high-throughput
# methods (mass_spec_surfaceome, surface_biotinylation, western_blot_paired)
# ---------------------------------------------------------------------------


def test_paper_level_evidence_keeps_competing_when_section_mentions_target() -> None:
    """For high-throughput methods, a methods sentence describing the
    experiment that happens to name a competing gene (sibling target) is
    kept *as long as the target also appears in the same section* — the
    paper as a whole is about a surfaceome experiment that included the
    target, even if the methods sentence describes the experiment
    generically.
    """
    paper = _paper_with([
        PaperSection(
            name="methods",
            text=(
                "We surface-biotinylated TCDB-expressing HEK293T cells using "
                "sulfo-NHS-SS-biotin and enriched with streptavidin beads. "
                "Captured proteins, including CD81, were eluted and analyzed by LC-MS/MS."
            ),
        )
    ])
    target = frozenset({"CD81"})
    gazetteer = frozenset({"CD81", "TCDB"})
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["surface_biotinylation"],
        max_snippets=5,
        target_names=target,
        gazetteer=gazetteer,
    )
    # The first sentence names TCDB (competing) but the section also mentions
    # CD81 (target), so the methods description survives the proximity filter.
    texts = " || ".join(s.text for s in snippets)
    assert "sulfo-NHS-SS-biotin" in texts.lower() or "biotinylated" in texts.lower()


def test_paper_level_evidence_still_drops_when_section_lacks_target() -> None:
    """Relaxation is bounded: when the section doesn't mention the target
    anywhere, competing-gene methods sentences are still dropped. The
    point of the relaxation is "paper-level evidence about the target,"
    not "any surfaceome paper anywhere."
    """
    paper = _paper_with([
        PaperSection(
            name="methods",
            text=(
                "TCDB-expressing HEK293T cells were surface-biotinylated using "
                "sulfo-NHS-SS-biotin and enriched with streptavidin beads."
            ),
        )
    ])
    target = frozenset({"CD81"})
    gazetteer = frozenset({"CD81", "TCDB"})
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["surface_biotinylation"],
        max_snippets=5,
        target_names=target,
        gazetteer=gazetteer,
    )
    assert snippets == []


def test_paper_level_relaxation_does_not_affect_flow_cytometry() -> None:
    """The relaxation is opt-in per category. Antibody-based assays
    (``flow_cytometry``) keep the strict filter — the CALR/CD47
    sibling-misfire guarantee in
    :func:`test_extract_snippets_drops_competing_gene_sentence` stays
    intact even when the section happens to mention both genes.
    """
    paper = _paper_with([
        PaperSection(
            name="figure_legends",
            text=(
                "CD47 surface expression was analyzed using flow cytometry "
                "in lymphoma cell lines. "
                "CALR was used as a positive control in a parallel experiment."
            ),
        )
    ])
    target = frozenset({"CALR", "CRT"})
    gazetteer = frozenset({"CALR", "CRT", "CD47"})
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=5,
        target_names=target,
        gazetteer=gazetteer,
    )
    texts = " || ".join(s.text for s in snippets)
    # The CD47-subject sentence must still be dropped despite CALR being
    # mentioned in a *different* sentence of the same section —
    # flow_cytometry is sentence-level strict by design, even though
    # the section contains the target.
    assert "CD47 surface expression" not in texts
