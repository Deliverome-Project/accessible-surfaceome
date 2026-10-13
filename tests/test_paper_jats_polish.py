"""Tests for paper/jats_polish.py — pandoc JATS → structured JATS.

Pandoc converts a manuscript .docx into JATS that is well-formed and
structureless: empty front matter, the title and abstract as body
sections, each figure a boxed section, the reference list a numbered
list. These pin the restructuring on a miniature of exactly that shape
(the output of the JATS writer after paper/filters/*.lua have run), so
they need lxml only and run in CI without pandoc.
"""
from __future__ import annotations

import sys
from pathlib import Path

import lxml.etree as ET  # ty: ignore[unresolved-import]

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))

XLINK = "http://www.w3.org/1999/xlink"
HREF = f"{{{XLINK}}}href"

LONG_FIG1 = "figure-1.-five-databases-agree-on-only-188-proteins.-upset-plot."
LONG_FIGS2 = "supplementary-figure-2.-identifiers-drive-accuracy.-bars-show-means."

RAW = f"""<article xmlns:xlink="{XLINK}" dtd-version="1.2" article-type="other">
<front><journal-meta><journal-id/><issn/></journal-meta>
<article-meta><permissions></permissions></article-meta></front>
<body>
<sec id="the-paper"><title>The accessible human surfaceome</title>
  <p>Rebecca J. Carlson<sup>1, *</sup>, L. Robert Hollingsworth<sup>1</sup>, Michael J. Smallegan<sup>2</sup></p>
  <p>Authors are listed in alphabetical order</p>
  <p><sup>1</sup>Deliverome Bio, Inc.</p>
  <p><sup>2</sup>Coral Biosciences, LLC</p>
  <p><sup>*</sup>Corresponding author: <email>becca@example.org</email></p>
  <boxed-text><p><ext-link ext-link-type="uri" xlink:href="https://viewer.example"><inline-graphic xlink:href="/abs/paper/assets/viewer.svg"><alt-text>Viewer</alt-text></inline-graphic> Viewer</ext-link></p></boxed-text>
  <sec id="abstract"><title>Abstract</title><p>The abstract text.</p></sec>
  <sec id="introduction"><title>Introduction</title>
    <p>Databases disagree (<xref alt="Figure 1" rid="{LONG_FIG1}">Figure 1</xref>; <xref alt="Betts et al., 2003" rid="ref-betts-2003">Betts et al., 2003</xref>; see <xref alt="Methods" rid="1.-methods-detail">Methods</xref> and <xref alt="Figure S2" rid="{LONG_FIGS2}">Figure S2</xref>, <xref alt="gone" rid="no-such-target">elsewhere</xref>).</p>
    <boxed-text>
      <p><styled-content id="{LONG_FIG1}"></styled-content><inline-graphic mimetype="image" mime-subtype="png" xlink:href="media/image5.png"/></p>
      <sec><title><named-content content-type="caption-lead"><bold>Figure 1. Five databases agree on only 188 proteins.</bold></named-content> UpSet plot of five databases. <ext-link ext-link-type="uri" xlink:href="https://gist.example/1"><underline>Figure data and script.</underline></ext-link></title></sec>
    </boxed-text>
  </sec>
  <sec id="methods"><title>Methods</title>
    <sec id="1.-methods-detail"><title>1. Methods detail</title><p>Detail.</p></sec>
  </sec>
  <sec id="references"><title>References</title>
    <list list-type="order">
      <list-item><p><styled-content id="ref-betts-2003"></styled-content>Betts, M.R., Koup, R.A., 2003. A flow assay. J. Immunol. Methods 281, 65–78. <ext-link ext-link-type="uri" xlink:href="https://doi.org/10.1016/s0022-1759(03)00265-5">https://doi.org/10.1016/s0022-1759(03)00265-5</ext-link></p></list-item>
      <list-item><p><styled-content id="ref-hpa-2026"></styled-content>Plasma membrane (HPA), 2026. URL <ext-link ext-link-type="uri" xlink:href="https://www.proteinatlas.org/x">https://www.proteinatlas.org/x</ext-link></p></list-item>
    </list>
  </sec>
  <sec id="acknowledgments"><title>Acknowledgments</title><p>We thank our reviewers.</p></sec>
  <sec id="competing-interest-statement"><title>Competing Interest Statement</title><p>The authors hold equity.</p></sec>
  <sec id="funding"><title>Funding</title>
    <p>Anthropic (United States) <ext-link ext-link-type="uri" xlink:href="https://ror.org/056y0v115"><underline>https://ror.org/056y0v115</underline></ext-link></p>
    <p>Renaissance Philanthropy.</p>
  </sec>
  <sec id="author-contributions"><title>Author Contributions</title><p><bold>R.J.C.:</bold> everything.</p></sec>
</sec>
<sec id="supplementary-information"><title>Supplementary information</title>
  <table-wrap><table><thead>
    <tr><th>Surface</th><th>Non-surface</th></tr>
    <tr><th>receptor</th><th>cytoplasmic</th></tr>
  </thead><tbody></tbody></table></table-wrap>
  <sec id="supplementary-table-1.-reason-taxonomy."><title><named-content content-type="caption-lead"><bold>Supplementary Table 1. Reason taxonomy.</bold></named-content> Codes assigned with each verdict.</title>
    <boxed-text>
      <p><styled-content id="{LONG_FIGS2}"></styled-content><inline-graphic mimetype="image" mime-subtype="png" xlink:href="media/image7.png"/></p>
      <sec><title><named-content content-type="caption-lead"><bold>Supplementary Figure 2. Identifiers drive accuracy.</bold></named-content> Bars show means.</title></sec>
    </boxed-text>
    <sec id="supplementary-note-1"><title>Supplementary Note 1. Limits.</title><p>Note text.</p></sec>
    <sec id="supplementary-references"><title>Supplementary References</title>
      <list list-type="order"><list-item><p><styled-content id="ref-westergaard-2018-b"></styled-content>Westergaard, D., 2018. Text mining.</p></list-item></list>
    </sec>
  </sec>
</sec>
</body><back></back></article>"""

ASSETS = {"1": "figures/db_overlap_upset.svg"}  # no entry for supplementary-2


def _polished():
    from jats_polish import polish  # ty: ignore[unresolved-import]

    root = ET.fromstring(RAW.encode())
    report = polish(root, graphic_for=ASSETS.get)
    return root, report


def _t(el) -> str:
    return " ".join("".join(el.itertext()).split())


def test_front_matter_is_filled_from_the_title_section() -> None:
    root, report = _polished()
    meta = root.find("front/article-meta")
    assert root.get("article-type") == "preprint"
    assert root.find("front/journal-meta") is None
    assert _t(meta.find("title-group/article-title")) == "The accessible human surfaceome"
    names = [(_t(c.find("name/surname")), _t(c.find("name/given-names")))
             for c in meta.findall("contrib-group/contrib")]
    assert names == [("Carlson", "Rebecca J."), ("Hollingsworth", "L. Robert"),
                     ("Smallegan", "Michael J.")]
    first = meta.find("contrib-group/contrib")
    assert first.get("corresp") == "yes"
    assert [x.get("rid") for x in first.findall("xref")] == ["aff1", "cor1"]
    assert [(a.get("id"), _t(a)) for a in meta.findall("aff")] == [
        ("aff1", "1Deliverome Bio, Inc."), ("aff2", "2Coral Biosciences, LLC")]
    assert _t(meta.find("author-notes/corresp/email")) == "becca@example.org"
    assert _t(meta.find("abstract")) == "The abstract text."
    assert report.authors == ["Rebecca J. Carlson", "L. Robert Hollingsworth",
                              "Michael J. Smallegan"]
    assert report.has_abstract and not report.problems


def test_article_meta_children_are_in_schema_order() -> None:
    root, _ = _polished()
    tags = [c.tag for c in root.find("front/article-meta")]
    order = ["title-group", "contrib-group", "aff", "author-notes", "abstract",
             "funding-group", "custom-meta-group"]
    assert tags == sorted(tags, key=order.index)
    assert set(tags) == set(order)


def test_back_matter_sections_move_to_their_jats_homes() -> None:
    root, _ = _polished()
    notes = root.find("front/article-meta/author-notes")
    kinds = {fn.get("fn-type"): _t(fn) for fn in notes.findall("fn")}
    assert kinds["COI-statement"] == "The authors hold equity."
    assert kinds["con"].startswith("R.J.C.:")
    assert kinds["other"] == "Authors are listed in alphabetical order"
    funders = root.findall("front/article-meta/funding-group/award-group")
    assert [_t(f.find(".//institution")) for f in funders] == [
        "Anthropic (United States)", "Renaissance Philanthropy"]
    assert _t(funders[0].find(".//institution-id")) == "https://ror.org/056y0v115"
    assert funders[1].find(".//institution-id") is None
    assert _t(root.find("back/ack")).endswith("We thank our reviewers.")
    # Only real sections are left in the body.
    assert [_t(s.find("title")) for s in root.findall("body/sec")] == ["Introduction", "Methods"]


def test_resource_links_become_custom_meta_without_the_icon_text() -> None:
    root, _ = _polished()
    cm = root.find("front/article-meta/custom-meta-group/custom-meta")
    assert _t(cm.find("meta-name")) == "Viewer"
    assert cm.find("meta-value/ext-link").get(HREF) == "https://viewer.example"
    assert not list(root.iter("inline-graphic"))


def test_figures_become_fig_with_label_caption_and_canonical_graphic() -> None:
    root, report = _polished()
    fig = root.find(".//fig[@id='fig1']")
    assert _t(fig.find("label")) == "Figure 1"
    assert _t(fig.find("caption/title")) == "Five databases agree on only 188 proteins."
    assert _t(fig.find("caption/p")) == "UpSet plot of five databases. Figure data and script."
    graphic = fig.find("graphic")
    assert graphic.get(HREF) == "figures/db_overlap_upset.svg"
    assert (graphic.get("mimetype"), graphic.get("mime-subtype")) == ("image", "svg+xml")
    assert report.figures == ["Figure 1", "Supplementary Figure 2"]
    assert not list(root.iter("boxed-text"))
    assert not list(root.iter("underline"))


def test_a_figure_without_a_canonical_asset_keeps_the_docx_image_and_is_reported() -> None:
    root, report = _polished()
    fig = root.find(".//fig[@id='figS2']")
    assert fig.find("graphic").get(HREF) == "media/image7.png"
    assert report.unswapped_figures == ["Supplementary Figure 2"]


def test_references_become_a_ref_list_with_doi_identifiers() -> None:
    root, report = _polished()
    refs = root.findall("back/ref-list/ref")
    assert [r.get("id") for r in refs] == ["ref-betts-2003", "ref-hpa-2026"]
    doi = refs[0].find("mixed-citation/pub-id")
    assert doi.get("pub-id-type") == "doi" and doi.text == "10.1016/s0022-1759(03)00265-5"
    assert _t(refs[0].find("mixed-citation")).startswith("Betts, M.R., Koup, R.A., 2003.")
    # A plain web reference keeps its link.
    assert refs[1].find("mixed-citation/ext-link").get(HREF) == "https://www.proteinatlas.org/x"
    assert report.references == 3  # two main + one supplementary


def test_cross_references_are_typed_and_retargeted() -> None:
    root, report = _polished()
    xrefs = {_t(x): (x.get("ref-type"), x.get("rid")) for x in root.iter("xref")
             if x.get("ref-type") not in {"aff", "corresp"}}
    assert xrefs["Figure 1"] == ("fig", "fig1")
    assert xrefs["Figure S2"] == ("fig", "figS2")
    assert xrefs["Betts et al., 2003"] == ("bibr", "ref-betts-2003")
    # A heading id that starts with a digit is not a legal XML id.
    assert xrefs["Methods"] == ("sec", "sec-1.-methods-detail")
    assert root.find(".//sec[@id='sec-1.-methods-detail']") is not None
    # A link whose target is gone degrades to its text, and is reported.
    assert "elsewhere" not in xrefs
    assert "elsewhere" in _t(root.find("body/sec/p"))
    assert report.dropped_xrefs == ["elsewhere"]
    assert (report.citations, report.figure_xrefs, report.section_xrefs) == (1, 2, 1)


def test_every_xref_resolves_and_ids_are_unique() -> None:
    root, _ = _polished()
    ids = [e.get("id") for e in root.iter() if isinstance(e.tag, str) and e.get("id")]
    assert len(ids) == len(set(ids))
    assert all(x.get("rid") in ids for x in root.iter("xref"))


def test_the_supplement_becomes_an_appendix_with_its_own_table_and_ref_list() -> None:
    root, report = _polished()
    app = root.find("back/app-group/app")
    assert [c.tag for c in app] == ["title", "table-wrap", "fig", "sec", "ref-list"]
    wrap = app.find("table-wrap")
    assert wrap.get("id") == "tblS1"
    assert _t(wrap.find("label")) == "Supplementary Table 1"
    assert _t(wrap.find("caption/title")) == "Reason taxonomy."
    assert _t(wrap.find("caption/p")) == "Codes assigned with each verdict."
    assert [c.tag for c in wrap] == ["label", "caption", "table"]
    assert app.find("ref-list/ref").get("id") == "ref-westergaard-2018-b"
    assert report.tables == ["Supplementary Table 1"]


def test_table_rows_pandoc_read_as_headers_move_to_the_body() -> None:
    root, _ = _polished()
    table = root.find(".//table")
    assert len(table.find("thead")) == 1
    body_rows = table.findall("tbody/tr")
    assert len(body_rows) == 1
    assert [c.tag for c in body_rows[0]] == ["td", "td"]


def test_a_manuscript_missing_its_parts_is_reported_not_crashed() -> None:
    from jats_polish import polish  # ty: ignore[unresolved-import]

    root = ET.fromstring(
        b"<article><front><article-meta/></front><body>"
        b"<sec><title>Only a title</title><p>Body text.</p></sec></body><back/></article>"
    )
    report = polish(root)
    assert any("author" in p for p in report.problems)
    assert any("Abstract" in p for p in report.problems)
    assert any("References" in p for p in report.problems)
