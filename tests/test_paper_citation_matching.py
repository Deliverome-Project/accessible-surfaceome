"""Tests for citation ↔ reference matching in the paper build.

``paper/filters/citations.lua`` re-points each Zotero in-text citation at
its entry in the reference list. These pin the citation shapes it used to
leave unlinked, the two-way check it reports (a citation with no entry, an
entry nothing cites), and the handling of a paper that appears in both
References and Supplementary References. ``refs_dois.lua`` runs first in
the real build, so it runs first here.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

pypandoc = pytest.importorskip("pypandoc")

FILTERS = Path(__file__).resolve().parents[1] / "paper/filters"
ZOTERO = "https://www.zotero.org/google-docs/?x"


def _cite(text: str) -> str:
    return f"[({text})]({ZOTERO})"


def _ref(text: str) -> str:
    # The trailing blank line makes the list loose, so each item holds a
    # Para — the shape the .docx gives, and the one refs_dois.lua unwraps.
    return f"1. [{text}]({ZOTERO})\n"


def _run(markdown: str, *, strict: bool = False) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PAPER_STRICT_CITATIONS", None)
    if strict:
        env["PAPER_STRICT_CITATIONS"] = "1"
    return subprocess.run(
        [
            pypandoc.get_pandoc_path(), "-f", "markdown", "-t", "html5",
            f"--lua-filter={FILTERS / 'refs_dois.lua'}",
            f"--lua-filter={FILTERS / 'citations.lua'}",
        ],
        input=markdown, capture_output=True, text=True, env=env,
    )


def _target(html: str, link_text: str) -> str | None:
    """The href of the link whose text is ``link_text`` (whitespace-insensitive)."""
    for href, text in re.findall(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', html, re.S):
        if re.sub(r"\s+", " ", text).strip() == link_text:
            return href
    return None


REFS = "\n".join([
    "## References",
    "",
    _ref("Carlson, R., Smallegan, M., 2026. The data record. https://doi.org/10.1/data"),
    _ref("Carlson, R.J., Smallegan, M.J., 2026. The code record. https://doi.org/10.1/code"),
    _ref("George, B.M., Eleftheriou, M., 2026a. First paper. Nature 1, 2. https://doi.org/10.1/a"),
    _ref("George, B.M., Porat, J., 2026b. Second paper. Nature 3, 4. https://doi.org/10.1/b"),
    _ref("Mighell, T.L., Lehner, B., 2025. A stabilizer. Nat. Struct. Mol. Biol. 32, 1. "
         "https://doi.org/10.1/m"),
    "",
])


def test_two_author_citation_links_to_the_first_author_entry() -> None:
    out = _run(f"Text {_cite('Mighell and Lehner, 2025')}.\n\n{REFS}")
    assert _target(out.stdout, "Mighell and Lehner, 2025") == "#ref-mighell-2025"


def test_year_letters_pick_the_matching_entry() -> None:
    out = _run(f"Text {_cite('George et al., 2026a; George et al., 2026b')}.\n\n{REFS}")
    assert _target(out.stdout, "George et al., 2026a") == "#ref-george-2026a"
    assert _target(out.stdout, "George et al., 2026b") == "#ref-george-2026b"


def test_initials_tell_two_same_surname_same_year_entries_apart() -> None:
    cite = _cite("R. Carlson and Smallegan, 2026; R. J. Carlson and Smallegan, 2026")
    out = _run(f"Text {cite}.\n\n{REFS}")
    assert _target(out.stdout, "R. Carlson and Smallegan, 2026") == "#ref-carlson-2026"
    assert _target(out.stdout, "R. J. Carlson and Smallegan, 2026") == "#ref-carlson-2026-b"
    # Both anchors exist, so neither link is dead.
    assert 'id="ref-carlson-2026"' in out.stdout
    assert 'id="ref-carlson-2026-b"' in out.stdout


def test_a_doi_containing_brackets_is_linked_whole() -> None:
    refs = "## References\n\n" + _ref(
        "Betts, M.R., Koup, R.A., 2003. A flow cytometric assay. J. Immunol. Methods "
        "281, 65–78. https://doi.org/10.1016/s0022-1759(03)00265-5"
    ) + "\n"
    out = _run(f"Text {_cite('Betts et al., 2003')}.\n\n{refs}")
    assert 'href="https://doi.org/10.1016/s0022-1759(03)00265-5"' in out.stdout
    assert ">https://doi.org/10.1016/s0022-1759(03)00265-5</a>" in out.stdout


def test_a_url_inside_a_parenthesis_does_not_take_the_closing_bracket() -> None:
    refs = "## References\n\n" + _ref(
        "Brase, J., 2009. DataCite (see https://doi.org/10.1109/COINFO.2009.66)."
    ) + "\n"
    out = _run(f"Text {_cite('Brase, 2009')}.\n\n{refs}")
    assert 'href="https://doi.org/10.1109/COINFO.2009.66"' in out.stdout


def test_accented_surnames_get_a_clean_anchor_id() -> None:
    refs = "## References\n\n" + _ref(
        "Müller, T., Klein, F., 2021. Title. J. 1, 2. https://doi.org/10.1/mu"
    ) + "\n"
    out = _run(f"Text {_cite('Müller et al., 2021')}.\n\n{refs}")
    ids = re.findall(r'id="(ref-[^"]*)"', out.stdout)
    assert ids and all(i.isascii() and "�" not in i for i in ids)
    assert _target(out.stdout, "Müller et al., 2021") == f"#{ids[0]}"


# ── The two-way check ────────────────────────────────────────────────

def test_report_is_clean_when_citations_and_references_match() -> None:
    cites = " ".join([
        _cite("Mighell and Lehner, 2025"),
        _cite("George et al., 2026a; George et al., 2026b"),
        _cite("R. Carlson and Smallegan, 2026; R. J. Carlson and Smallegan, 2026"),
    ])
    out = _run(f"Text {cites}.\n\n{REFS}", strict=True)
    assert out.returncode == 0, out.stderr
    assert "every citation has a reference and every reference is cited" in out.stderr


def test_a_reference_nothing_cites_is_reported() -> None:
    out = _run(f"Text {_cite('Mighell and Lehner, 2025')}.\n\n{REFS}")
    assert out.returncode == 0
    assert "never cited in the text" in out.stderr
    assert "george 2026a" in out.stderr


def test_a_citation_with_no_reference_is_reported() -> None:
    out = _run(f"Text {_cite('Nobody et al., 1999')}.\n\n{REFS}")
    assert "matched NO reference" in out.stderr
    assert "nobody 1999" in out.stderr


def test_strict_mode_fails_the_build_on_a_mismatch() -> None:
    out = _run(f"Text {_cite('Nobody et al., 1999')}.\n\n{REFS}", strict=True)
    assert out.returncode != 0


# ── A paper listed in both reference lists ───────────────────────────

_WEST = ("Westergaard, D., Brunak, S., 2018. Text mining. PLoS Comput. Biol. 14, 1. "
         "https://doi.org/10.1/w")


def _two_lists(main_text: str) -> str:
    return "\n".join([
        main_text, "",
        "## References", "",
        _ref("Mighell, T.L., Lehner, B., 2025. A stabilizer. J. 32, 1. https://doi.org/10.1/m"),
        _ref(_WEST), "",
        "# Supplementary information", "",
        f"Note text {_cite('Westergaard et al., 2018')}.", "",
        "## Supplementary References", "",
        _ref(_WEST), "",
    ])


def test_a_supplement_only_reference_leaves_the_main_list() -> None:
    out = _run(_two_lists(f"Main {_cite('Mighell and Lehner, 2025')}."), strict=True)
    assert out.returncode == 0, out.stderr
    main, supp = out.stdout.split("Supplementary information", 1)
    assert "Westergaard" not in main
    assert "Westergaard, D." in supp
    # The supplement's citation points at the supplementary copy, which exists.
    href = _target(out.stdout, "Westergaard et al., 2018")
    assert href is not None and f'id="{href[1:]}"' in supp
    assert "supplement-only reference" in out.stderr


def test_a_reference_cited_in_both_places_keeps_both_entries() -> None:
    main_text = (f"Main {_cite('Mighell and Lehner, 2025')} and "
                 f"{_cite('Westergaard et al., 2018')}.")
    out = _run(_two_lists(main_text), strict=True)
    assert out.returncode == 0, out.stderr
    main, supp = out.stdout.split("Supplementary information", 1)
    assert "Westergaard, D." in main
    assert "Westergaard, D." in supp
