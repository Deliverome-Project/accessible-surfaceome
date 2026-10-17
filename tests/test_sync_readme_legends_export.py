"""Guard `sync_readme_legends.py --export` against the manuscript's real shapes.

A Drive dump of the manuscript does not hand us a clean ``##### **Figure N.``
heading for every legend. Two artifacts sit between the heading mark and the
figure label, and either one used to hide the legend from the exporter:

* an inline image anchored to the legend paragraph renders as ``\\[image\\]``,
  *before* the bold marker when the anchor is not itself bold and *after* it
  when it is — 14 of the 23 legends carried one;
* a dump taken with ``includeComments`` wraps each commented span in
  ``<comment_start id=…>`` / ``<comment_end id=…>``, and for several legends the
  commented span is the figure label itself, so the tag lands mid-label.

The lines below are copied from a real dump. Together they used to yield 9 of
23 legends; the exporter now strips both artifacts before reading the line.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/figures/sync_readme_legends.py"

# Verbatim legend headings from a Drive dump of the manuscript, one per shape.
PLAIN = "##### **Figure 2. A tool-free triage agent beats the databases.** Bars show accuracy."
IMAGE_THEN_BOLD = r"##### \[image\]**Figure 5. Every protein resolves to a tier.** a) The full set."
BOLD_THEN_IMAGE = r"##### **\[image\]Figure 4. Calls select the deep-dive set.** a) Every protein."
TAG_SPLITS_LABEL = (
    r"##### **\[image\]<comment_start id=AAACHKOK38w>Figure 3<comment_end id=AAACHKOK38w>. "
    "The agent rescues candidates.** The two-stage run."
)
TAG_BEFORE_LABEL = (
    "##### **<comment_start id=AAACFK90vX0>Supplementary<comment_end id=AAACFK90vX0> "
    "Figure 14. Triage calls agree with curation.** a) Fraction of proteins."
)
TAG_IN_PROSE = (
    "##### **Supplementary Figure 9. Each source is enriched for a topology.** Bubble "
    "matrix of <comment_start id=AAACHuSCH9M>surface sources<comment_end id=AAACHuSCH9M>."
)
# An earlier draft's leftover: bold, but no heading mark. Must stay skipped.
STRAY_BOLD = "**Figure 1. A superseded wording of the first legend.** Not a legend any more."


@pytest.fixture(scope="module")
def sync():
    spec = importlib.util.spec_from_file_location("_srl", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dump(tmp_path: Path, lines: list[str], name: str = "dump.json") -> Path:
    """Write a Drive ``read_file_content``-shaped dump of those lines."""
    path = tmp_path / name
    body = "Some body prose.\n" + "\n".join(lines) + "\nMore prose.\n"
    path.write_text(json.dumps({"fileContent": body}), encoding="utf-8")
    return path


def test_both_image_anchor_shapes_are_found(sync, tmp_path: Path) -> None:
    found = sync._export(
        _dump(tmp_path, [PLAIN, IMAGE_THEN_BOLD, BOLD_THEN_IMAGE]),
        {"Figure 2", "Figure 4", "Figure 5"},
    )
    assert sorted(found) == ["Figure 2", "Figure 4", "Figure 5"]
    assert "[image]" not in "".join(found.values())


def test_comment_tags_do_not_hide_a_legend(sync, tmp_path: Path) -> None:
    found = sync._export(
        _dump(tmp_path, [TAG_SPLITS_LABEL, TAG_BEFORE_LABEL, TAG_IN_PROSE]),
        {"Figure 3", "S14", "S9"},
    )
    assert sorted(found) == ["Figure 3", "S14", "S9"]
    assert "<comment_" not in "".join(found.values())


def test_cleaned_legend_carries_no_export_artifacts(sync, tmp_path: Path) -> None:
    found = sync._export(_dump(tmp_path, [TAG_SPLITS_LABEL, TAG_IN_PROSE]), {"Figure 3", "S9"})
    assert sync._clean(found["Figure 3"]).startswith("The agent rescues candidates.")
    assert sync._clean(found["S9"]) == (
        "Each source is enriched for a topology. Bubble matrix of surface sources."
    )


def test_stray_bold_paragraph_is_still_skipped(sync, tmp_path: Path) -> None:
    """The heading mark is the guard that keeps old draft prose out."""
    with pytest.raises(SystemExit, match="legends not found"):
        sync._export(_dump(tmp_path, [STRAY_BOLD]), {"Figure 1"})


def test_dump_without_artifacts_still_parses(sync, tmp_path: Path) -> None:
    """A dump taken without comments, before the figures were placed."""
    found = sync._export(_dump(tmp_path, [PLAIN]), {"Figure 2"})
    assert found["Figure 2"].startswith("**Figure 2.")
