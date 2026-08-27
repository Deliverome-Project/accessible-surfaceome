"""Render a .docx manuscript into a Deliverome-branded PDF + JATS XML.

Usage:
    uv run python paper/build.py path/to/manuscript.docx
    bash paper/build.sh path/to/manuscript.docx   # thin wrapper, same thing

Outputs three files under <docx-dir>/build/:

    <stem>.html  — pandoc-rendered HTML with deliverome-print.css
                   attached. Intermediate; useful for debugging the
                   print layout in a browser (Chrome DevTools →
                   Rendering → Emulate CSS media type: print shows
                   exactly what WeasyPrint will see).
    <stem>.pdf   — WeasyPrint output. The polished publication-style
                   PDF — feed it to the manuscript bundle's
                   `pdf_path` in scripts/release/publish-archive.py.
    <stem>.xml   — pandoc-rendered JATS XML. Feed it to the
                   manuscript bundle's `jats_filename`.

Dependencies are uv-native — install once with::

    uv sync --extra paper

That pulls in `pypandoc-binary` (bundles the pandoc binary inside
the wheel — no `brew install pandoc` needed) and `weasyprint` (pure-
Python; on macOS WeasyPrint uses CoreText, on Linux it needs Pango +
Cairo system packages, which the WeasyPrint docs cover).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _patch_cffi_for_macos_brew() -> None:
    """Make WeasyPrint find Pango/GLib/Cairo on macOS Homebrew.

    Background: WeasyPrint uses cffi → ``dlopen`` to call native
    Pango / GLib / Cairo, which on macOS live under Homebrew's prefix
    (``/opt/homebrew/lib`` on Apple Silicon, ``/usr/local/lib`` on
    Intel). dlopen searches the dyld cache, ``DYLD_*`` env vars, and
    the process's rpath. macOS System Integrity Protection **strips
    DYLD_* env vars from hardened-runtime binaries**, which the
    uv-managed Python is — so setting ``DYLD_FALLBACK_LIBRARY_PATH``
    in build.sh doesn't survive the hop into Python.

    Workaround: monkey-patch ``cffi.api.FFI.dlopen`` to fall through
    to absolute Homebrew paths when a bare-name lookup fails. We
    iterate the common dylib name forms Homebrew emits (e.g.
    ``libgobject-2.0-0`` → ``/opt/homebrew/lib/libgobject-2.0.0.dylib``).
    Original behavior is preserved when the bare-name lookup
    succeeds (Linux / when DYLD_* survives) — only the failure path
    is augmented.

    No-op on non-darwin platforms; no-op when neither Homebrew prefix
    exists.
    """
    if sys.platform != "darwin":
        return
    brew_lib_dirs = [
        Path(p) / "lib" for p in ("/opt/homebrew", "/usr/local")
        if Path(p, "lib").is_dir()
    ]
    if not brew_lib_dirs:
        return

    import cffi.api

    original_dlopen = cffi.api.FFI.dlopen

    def patched_dlopen(self, name, flags=0):  # type: ignore[no-untyped-def]
        try:
            return original_dlopen(self, name, flags)
        except OSError as original_err:
            if not isinstance(name, str):
                raise
            # Translate the cffi name into common Homebrew dylib
            # filename forms and probe each brew prefix. Homebrew
            # version-suffix convention is ``-N.M.X.dylib`` where
            # the cffi name uses ``-N.M-X`` (the trailing
            # version-component is dash-separated in the name and
            # dot-separated in the dylib filename).
            candidates: list[str] = []
            for raw in (name, name + ".dylib"):
                candidates.append(raw)
            # libgobject-2.0-0 → libgobject-2.0.0.dylib
            # libpango-1.0-0 → libpango-1.0.0.dylib
            if "-" in name and not name.endswith(".dylib"):
                head, _, tail = name.rpartition("-")
                if tail.isdigit():
                    candidates.append(f"{head}.{tail}.dylib")
            for lib_dir in brew_lib_dirs:
                for c in candidates:
                    abs_path = lib_dir / c
                    if abs_path.exists():
                        try:
                            return original_dlopen(self, str(abs_path), flags)
                        except OSError:
                            continue
            raise original_err

    cffi.api.FFI.dlopen = patched_dlopen


_patch_cffi_for_macos_brew()

import pypandoc  # noqa: E402 — must come after the cffi patch
from weasyprint import CSS, HTML  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = REPO_ROOT / "paper" / "deliverome-print.css"
WEB_CSS_PATH = REPO_ROOT / "paper" / "deliverome-web.css"
WEB_JS_PATH = REPO_ROOT / "paper" / "deliverome-web.js"
REFS_DOIS_FILTER = REPO_ROOT / "paper" / "filters" / "refs_dois.lua"
FIGURES_FILTER = REPO_ROOT / "paper" / "filters" / "figures.lua"
SECTIONS_FILTER = REPO_ROOT / "paper" / "filters" / "sections.lua"
CITATIONS_FILTER = REPO_ROOT / "paper" / "filters" / "citations.lua"
# Brand marks (GitHub / Zenodo) set beside the front-matter resource
# links. Exported to the environment because a Lua filter has no way
# to learn the repo root, and WeasyPrint resolves <img src> against
# the build directory rather than paper/.
PAPER_ASSETS_DIR = REPO_ROOT / "paper" / "assets"
FIGURE_MANIFEST = REPO_ROOT / "paper" / "figure_manifest.json"
CANONICAL_FIGURES_DIR = REPO_ROOT / "data" / "analysis" / "figures"
# Print-ready derived assets (e.g. vector SVGs converted from the
# canonical PDFs) take precedence over the curated figure library, so
# the print build can carry a print-specific rendition of a figure
# without mutating data/analysis/figures/.
PAPER_FIGURES_DIR = REPO_ROOT / "paper" / "figures"
FIGURE_SEARCH_PATH = [PAPER_FIGURES_DIR, CANONICAL_FIGURES_DIR]


def _stem_for(src: Path) -> str:
    """Normalize the .docx basename into a filesystem-safe stem.

    The user's drafts often have spaces and mixed case (e.g.
    ``2026 Anthropic Surfaceome Technical Draft.docx``); collapse the
    spaces to underscores so the resulting paths play nicely with
    shells, URLs, and Zenodo upload paths.
    """
    return src.stem.replace(" ", "_")


def build(src: Path, strict_figures: bool = False) -> dict[str, Path]:
    """Run pandoc → HTML → figure swap → WeasyPrint PDF + pandoc JATS XML.

    Between pandoc and WeasyPrint, ``figure_swap.swap_figures`` rewrites
    each ``<img src>`` to point at the canonical asset in
    ``data/analysis/figures/`` per ``paper/figure_manifest.json``. This
    guarantees the published PDF carries the current HEAD render of each
    figure rather than whatever bitmap the .docx had pasted in. Set
    ``strict_figures=True`` to fail the build on any missing-asset / DPI /
    format issue; otherwise issues are reported and the build continues
    with whatever the manifest pointed at (or the original .docx bitmap
    if the manifest entry was missing).

    Returns the three output paths so callers can wire them straight
    into a publish/upload step.
    """
    if not src.is_file():
        raise FileNotFoundError(f"source manuscript not found: {src}")
    if not CSS_PATH.is_file():
        raise FileNotFoundError(
            f"deliverome-print.css missing at {CSS_PATH} — "
            "ensure paper/ is intact"
        )

    stem = _stem_for(src)
    out_dir = src.parent / "build"
    out_dir.mkdir(exist_ok=True)
    media_dir = out_dir / f"media-{stem}"

    html_path = out_dir / f"{stem}.html"
    pdf_path = out_dir / f"{stem}.pdf"
    xml_path = out_dir / f"{stem}.xml"

    # 1. pandoc → standalone HTML5 with the deliverome stylesheet linked.
    #    --extract-media pulls embedded .docx images out to disk so
    #    WeasyPrint can load them; the link path is relative to the HTML.
    os.environ["PAPER_ASSETS_DIR"] = str(PAPER_ASSETS_DIR)
    os.environ.pop("PAPER_WEB_EXTRAS", None)
    print(f"→ pandoc {src.name} → {html_path.name}")
    pypandoc.convert_file(
        str(src),
        to="html5",
        format="docx",
        outputfile=str(html_path),
        extra_args=[
            "--standalone",
            # NOTE: NOT passing --section-divs. With it, pandoc wraps
            # each heading + its content in a <section class="levelN">,
            # which makes the body's headings and figures grandchildren
            # of <body> instead of direct children. column-span:all only
            # spans the immediate multi-column container, so a heading
            # or figure nested two levels deep can't span. Flat structure
            # (headings + paragraphs as direct body children) is what
            # the print stylesheet expects.
            f"--extract-media={media_dir}",
            f"--css={CSS_PATH}",
            # Re-shapes the References section: unwraps Zotero google-
            # docs anchors so each reference reads as plain prose, and
            # promotes the DOI URL inside to its own <a class="doi">
            # link the stylesheet paints maroon.
            f"--lua-filter={REFS_DOIS_FILTER}",
            # Two figure-related transformations: split <h5><img>caption</h5>
            # (and any heading-level variant) into <p><img></p> + <hN>caption</hN>,
            # and linkify "Figure N" / "Appendix Figure N" body-text
            # references so they jump to the matching caption.
            f"--lua-filter={FIGURES_FILTER}",
            # Linkify body-text section cross-references ("see Methods")
            # to the matching heading. MUST come after figures.lua:
            # that filter rewrites heading/figure structure, and this
            # one indexes the headings that survive it. Supplementary
            # labels (Figure S3 / Table S1) are deliberately left as
            # plain text — the supplement is a separate file, so an
            # intra-document anchor would be a dead link.
            f"--lua-filter={SECTIONS_FILTER}",
            # Re-point Zotero's in-text citations at the matching
            # References entry and lift the brackets out of the link
            # text. MUST come after refs_dois.lua, which unwraps the
            # Zotero link around each reference entry.
            f"--lua-filter={CITATIONS_FILTER}",
        ],
    )

    # 2. Figure swap — rewrite each in-doc <img> to point at the
    #    canonical asset under data/analysis/figures/, and verify
    #    resolution / format. See paper/figure_swap.py for the
    #    full contract; manifest at paper/figure_manifest.json.
    #    Sibling import: when this file runs as ``python paper/build.py``
    #    the paper/ directory is what's on sys.path, not its parent.
    #    Static checkers (ty) walk from the repo root and can't see
    #    the sibling — silence the unresolved-import diagnostic.
    from figure_swap import (  # ty: ignore[unresolved-import]
        format_report,
        load_manifest,
        swap_figures,
    )
    manifest = load_manifest(FIGURE_MANIFEST)
    if manifest:
        print(f"→ figure-swap   ({len(manifest)} manifest entries)")
        report = swap_figures(html_path, manifest, FIGURE_SEARCH_PATH)
        formatted = format_report(report)
        if formatted:
            print(formatted)
        if strict_figures and report.has_issues:
            raise RuntimeError(
                f"--strict figure-swap: {len(report.issues)} unresolved issue(s); "
                f"fix or relax the manifest, then re-run."
            )

    # 3. WeasyPrint → PDF. The `base_url` anchors relative paths (the
    #    CSS @import of `../viewer/app/design-tokens.css` and the
    #    extracted-media images) to the HTML file's directory.
    #    WeasyPrint fetches Manrope + Playfair Display from Google
    #    Fonts at render time and embeds the subsets it needs.
    print(f"→ weasyprint → {pdf_path.name}")
    HTML(filename=str(html_path), base_url=str(out_dir)).write_pdf(
        target=str(pdf_path),
        stylesheets=[CSS(filename=str(CSS_PATH))],
    )

    # 4. pandoc → JATS XML. Same source, different writer; machine-
    #    readable references + figure metadata for the Zenodo deposit.
    print(f"→ pandoc {src.name} → {xml_path.name}")
    pypandoc.convert_file(
        str(src),
        to="jats",
        format="docx",
        outputfile=str(xml_path),
        extra_args=["--standalone"],
    )

    return {"html": html_path, "pdf": pdf_path, "xml": xml_path}


def _downsample_raster(src: Path, dest: Path, max_width: int) -> Path | None:
    """Re-encode a raster asset as a width-capped WebP, or return None.

    The canonical figures are 600-DPI renders 6,000-13,000 px wide,
    which is right for print and absurd for a web page: shipped as-is
    they made the paper directory 41 MB. A figure displays at roughly
    930 CSS px here, so ~2,400 px still covers a 2.5x display with
    room to spare — and the lightbox, which is the only place a figure
    is seen larger, is viewport-bound anyway.

    WebP rather than PNG: these are dense plots with text, where WebP
    at high quality lands far smaller than PNG for no visible loss.
    Between the width cap and the format the paper directory drops
    from ~41 MB to a few MB.

    Vector assets are never touched; they're already small and scale
    for free. Returns the written path, or None when the file isn't a
    raster or Pillow can't read it, so the caller falls back to a
    plain copy.
    """
    if src.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        Image.MAX_IMAGE_PIXELS = None  # these are legitimately huge
        out = dest.with_suffix(".webp")
        with Image.open(src) as im:
            if im.width > max_width:
                height = round(im.height * max_width / im.width)
                im = im.resize((max_width, height), Image.LANCZOS)
            im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB").save(
                out, format="WEBP", quality=92, method=6
            )
        return out
    except Exception as exc:  # noqa: BLE001 — fall back to copying
        print(f"  ⚠ could not re-encode {src.name} ({exc}); copying as-is")
        return None


def build_web(
    src: Path,
    out_dir: Path,
    asset_prefix: str = "assets",
    max_raster_width: int = 2400,
    biorxiv_url: str | None = None,
) -> Path:
    """Render the manuscript as a self-contained web page.

    Same pandoc pass and same filters as the PDF build — so the
    citation, section and figure cross-references are identical — but
    the output is a directory that can be dropped into any static
    site:

        <out_dir>/index.html
        <out_dir>/assets/…            images, brand marks, stylesheet

    Differences from the print build:
      * ``--toc`` adds a table of contents; the web stylesheet docks
        it beside the text on wide screens.
      * every ``<img src>`` is rewritten to a RELATIVE ``assets/…``
        path and the file copied in, because the PDF build leaves
        absolute local paths that mean nothing on a web server.
      * deliverome-web.css replaces the print sheet.

    Returns the written index.html.
    """
    from figure_swap import (  # ty: ignore[unresolved-import]
        format_report,
        load_manifest,
        swap_figures,
    )
    from lxml import html as lxml_html

    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    stem = _stem_for(src)
    work = out_dir / f"_{stem}.html"
    media_dir = out_dir / f"_media-{stem}"

    os.environ["PAPER_ASSETS_DIR"] = str(PAPER_ASSETS_DIR)
    # Web-only front-matter links. Set to the bioRxiv URL (a placeholder
    # until the preprint is posted); the filter also adds a PDF download
    # beside it. Neither makes sense inside the PDF itself.
    os.environ["PAPER_WEB_EXTRAS"] = biorxiv_url or "https://www.biorxiv.org/"
    print(f"→ pandoc {src.name} → web html")
    pypandoc.convert_file(
        str(src),
        to="html5",
        format="docx",
        outputfile=str(work),
        extra_args=[
            "--standalone",
            "--toc",
            # Depth 2 = the <h1> title plus the <h2> section headings
            # (Introduction, Results, Discussion, Methods…). Depth 3
            # pulled in every <h3> subsection and buried the majors.
            # Keyed on heading LEVEL, so it tracks the document
            # structure rather than a hand-kept list of section names.
            "--toc-depth=2",
            f"--extract-media={media_dir}",
            f"--lua-filter={REFS_DOIS_FILTER}",
            f"--lua-filter={FIGURES_FILTER}",
            f"--lua-filter={SECTIONS_FILTER}",
            f"--lua-filter={CITATIONS_FILTER}",
        ],
    )

    manifest = load_manifest(FIGURE_MANIFEST)
    if manifest:
        print(f"→ figure-swap   ({len(manifest)} manifest entries)")
        report = swap_figures(work, manifest, FIGURE_SEARCH_PATH)
        formatted = format_report(report)
        if formatted:
            print(formatted)

    # Localise every image: copy the file next to the page and point
    # the tag at a relative path. Content-addressed by index so two
    # sources with the same basename can't collide.
    doc = lxml_html.parse(str(work)).getroot()
    copied: dict[str, str] = {}
    for i, img in enumerate(doc.xpath("//img")):
        raw = img.get("src") or ""
        if raw.startswith(("http://", "https://", "data:")) or raw.startswith(asset_prefix + "/"):
            continue
        srcpath = Path(raw)
        if not srcpath.is_absolute():
            srcpath = (work.parent / srcpath).resolve()
        if not srcpath.is_file():
            print(f"  ⚠ image not found, left as-is: {raw}")
            continue
        key = str(srcpath)
        if key not in copied:
            name = f"{i:02d}-{srcpath.name}"
            dest = assets_dir / name
            written = _downsample_raster(srcpath, dest, max_raster_width)
            if written is None:
                shutil.copy2(srcpath, dest)
            else:
                name = written.name
            copied[key] = f"{asset_prefix}/{name}"
        img.set("src", copied[key])

    # Prune supplementary sub-entries from the contents rail. The
    # supplement's own "Supplementary Note N" / "Supplementary
    # References" headings are <h2>, so --toc-depth=2 pulls them in
    # alongside the paper's major sections and the rail stops reading
    # as a map of the argument. The parent "Supplementary information"
    # entry stays, so the section is still reachable.
    toc = doc.get_element_by_id("TOC", None)
    if toc is not None:
        pruned = 0
        for a in toc.xpath(".//a"):
            label = " ".join((a.text_content() or "").split())
            if label.startswith("Supplementary ") and label != "Supplementary information":
                li = a.getparent()
                while li is not None and li.tag != "li":
                    li = li.getparent()
                if li is not None and li.getparent() is not None:
                    li.getparent().remove(li)
                    pruned += 1
        if pruned:
            print(f"  pruned {pruned} supplementary sub-entr(y/ies) from the TOC")

    # Build a real title band. The .docx carries no title metadata, so
    # pandoc emits a bare <h1> followed by loose author / affiliation /
    # resource paragraphs rather than its usual #title-block-header.
    # Group everything before the first <h2> into one <header> so the
    # stylesheet has something to anchor the banner on.
    body = doc.find("body")
    if body is not None:
        first_h2 = body.find("h2")
        if first_h2 is not None:
            header = lxml_html.Element("header")
            header.set("class", "paper-header")
            for node in list(body):
                if node is first_h2:
                    break
                if node.tag in ("nav", "meta", "script", "style"):
                    continue
                body.remove(node)
                header.append(node)
            body.insert(0, header)

    # Point the stylesheet at the copied web CSS.
    shutil.copy2(WEB_CSS_PATH, assets_dir / "paper.css")
    shutil.copy2(WEB_JS_PATH, assets_dir / "paper.js")
    for link in doc.xpath("//link[@rel='stylesheet']"):
        link.getparent().remove(link)
    # Drop pandoc's built-in <style> too. --standalone injects a default
    # sheet whose `body { max-width: 36em; margin: auto }` silently
    # overrode our layout and squeezed the whole page into a 274px
    # column, TOC gutter and all.
    for style in doc.xpath("//head/style"):
        style.getparent().remove(style)
    head = doc.find("head")
    if head is not None:
        head.append(lxml_html.fromstring(
            f'<link rel="stylesheet" href="{asset_prefix}/paper.css"/>'
        ))
        head.append(lxml_html.fromstring(
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        ))
    if body is not None:
        # `defer` so the parser is never blocked; the script only
        # enhances links that already work without it.
        body.append(lxml_html.fromstring(
            f'<script src="{asset_prefix}/paper.js" defer></script>'
        ))

    # Standalone pages need the scope class the stylesheet keys off;
    # embedded pages get it from the wrapper div instead.
    if body is not None:
        existing = body.get("class", "")
        body.set("class", (existing + " paper-root").strip())

    index = out_dir / "index.html"
    index.write_bytes(lxml_html.tostring(
        doc, method="html", encoding="utf-8", doctype="<!DOCTYPE html>"))

    # Tidy the intermediates — the published directory should contain
    # only what the page actually serves.
    work.unlink(missing_ok=True)
    shutil.rmtree(media_dir, ignore_errors=True)
    print(f"  copied {len(copied)} image(s) → {assets_dir}")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a .docx manuscript into a Deliverome-branded "
            "PDF + JATS XML using pandoc + WeasyPrint."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to the .docx manuscript",
    )
    parser.add_argument(
        "--strict-figures",
        action="store_true",
        help=(
            "Fail the build if any figure-swap resolution / format check "
            "fails (missing canonical asset, PNG DPI below the manifest "
            "minimum, SVG that wraps a raster, etc.). Default: warn and "
            "continue."
        ),
    )
    parser.add_argument(
        "--biorxiv-url",
        default=None,
        help=(
            "bioRxiv URL for the web build's front-matter link. "
            "Defaults to biorxiv.org as a placeholder until the "
            "preprint is posted."
        ),
    )
    parser.add_argument(
        "--max-raster-width",
        type=int,
        default=2400,
        help=(
            "Downsample raster figures wider than this when building "
            "for web (default: 2400 px). Print-resolution 600-DPI "
            "sources are 6,000-13,000 px wide, which no screen needs. "
            "Vector assets are unaffected."
        ),
    )
    parser.add_argument(
        "--asset-prefix",
        default="assets",
        help=(
            "URL prefix written into the page's <img>/<link>/<script> "
            "paths (default: 'assets', i.e. relative). Set an absolute "
            "prefix like '/paper/<slug>/assets' when the HTML will be "
            "served by a route whose URL differs from where the asset "
            "files actually live."
        ),
    )
    parser.add_argument(
        "--web",
        type=Path,
        metavar="OUT_DIR",
        help=(
            "Render a self-contained web page into OUT_DIR instead of "
            "building the PDF. Writes OUT_DIR/index.html plus an "
            "assets/ directory, ready to drop into a static site."
        ),
    )
    args = parser.parse_args()

    if args.web is not None:
        try:
            index = build_web(
                args.source.resolve(),
                args.web.resolve(),
                args.asset_prefix,
                args.max_raster_width,
                args.biorxiv_url,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 66
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print()
        print(f"✓ Wrote {index}")
        print(f"  open {index} in a browser to check it.")
        return 0

    try:
        outputs = build(args.source.resolve(), strict_figures=args.strict_figures)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 66
    except Exception as exc:  # noqa: BLE001 — surface arbitrary pandoc/wp errors
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print()
    print("✓ Wrote:")
    for key in ("html", "pdf", "xml"):
        print(f"  {outputs[key]}")
    print()
    print("Iterating on the print look:")
    print(f"  open {outputs['html']} in a browser — Chrome DevTools'")
    print("  Rendering → 'Emulate CSS media type: print' shows exactly")
    print("  what WeasyPrint sees. Tweak paper/deliverome-print.css and")
    print("  re-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
