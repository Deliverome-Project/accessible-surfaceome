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
import ctypes
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


def _stem_for(src: Path) -> str:
    """Normalize the .docx basename into a filesystem-safe stem.

    The user's drafts often have spaces and mixed case (e.g.
    ``2026 Anthropic Surfaceome Technical Draft.docx``); collapse the
    spaces to underscores so the resulting paths play nicely with
    shells, URLs, and Zenodo upload paths.
    """
    return src.stem.replace(" ", "_")


def build(src: Path) -> dict[str, Path]:
    """Run pandoc → HTML → WeasyPrint PDF + pandoc JATS XML.

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
        ],
    )

    # 2. WeasyPrint → PDF. The `base_url` anchors relative paths (the
    #    CSS @import of `../viewer/app/design-tokens.css` and the
    #    extracted-media images) to the HTML file's directory.
    #    WeasyPrint fetches Manrope + Playfair Display from Google
    #    Fonts at render time and embeds the subsets it needs.
    print(f"→ weasyprint → {pdf_path.name}")
    HTML(filename=str(html_path), base_url=str(out_dir)).write_pdf(
        target=str(pdf_path),
        stylesheets=[CSS(filename=str(CSS_PATH))],
    )

    # 3. pandoc → JATS XML. Same source, different writer; machine-
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
    args = parser.parse_args()

    try:
        outputs = build(args.source.resolve())
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
