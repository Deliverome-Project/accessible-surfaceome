"""Embed gist URLs into the PDF + PNG metadata of every figure in
``data/analysis/figures/``. Idempotent — re-run after any figure
regeneration to refresh metadata.

PDFs: pikepdf, XMP dc:* fields.
PNGs: PIL, tEXt chunks.

Update the FIGURE_GISTS map below when a figure's gist is rotated or
a new figure earns a slot.
"""
from __future__ import annotations

from pathlib import Path

import pikepdf
from PIL import Image, PngImagePlugin

from accessible_surfaceome.paths import REPO_ROOT

FIGURES_DIR = REPO_ROOT / "data/analysis/figures"
REPO_URL = "https://github.com/Deliverome-Project/accessible-surfaceome"

# slug → secret gist URL. Update when a gist is rotated or a new
# figure is promoted.
FIGURE_GISTS: dict[str, str] = {
    "db_overlap_venn":            "https://gist.github.com/beccajcarlson/f0cfd8281a9d512174ac49c32d051bde",
    "db_correctness_by_class":    "https://gist.github.com/beccajcarlson/b4d7c89ddd810bf38213b123512f9075",
    "db_cutoff_tradeoff":         "https://gist.github.com/beccajcarlson/06d053b54810285af495886871ee7f8a",
    "db_correctness_overall":     "https://gist.github.com/beccajcarlson/1e3d464fa905536611df4d5ee0950558",
    "benchmark_cost_vs_accuracy": "https://gist.github.com/beccajcarlson/774ff119060c9d4c81a3f020afb576f7",
}


def _embed_pdf(path: Path, slug: str, gist_url: str, description: str) -> None:
    keywords = ["accessible-surfaceome", slug, "reproduction-gist"]
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            meta["dc:title"] = slug
            meta["dc:description"] = description
            meta["dc:subject"] = keywords
            meta["dc:source"] = gist_url
        pdf.save(path)


def _embed_png(path: Path, slug: str, gist_url: str, description: str) -> None:
    img = Image.open(path)
    info = PngImagePlugin.PngInfo()
    for k, v in (img.info or {}).items():
        if not isinstance(v, (str, bytes)):
            continue
        try:
            info.add_text(k, v if isinstance(v, str) else v.decode("utf-8", "replace"))
        except Exception:
            pass
    info.add_text("Title", slug)
    info.add_text("Description", description)
    info.add_text("Source", gist_url)
    info.add_text("Software", "matplotlib (gist link embedded post-render)")
    img.save(path, "PNG", pnginfo=info)


def main() -> int:
    n_pdf = 0
    n_png = 0
    for slug, gist_url in FIGURE_GISTS.items():
        description = f"Reproduction gist: {gist_url}  |  Repo: {REPO_URL}"
        pdf_path = FIGURES_DIR / f"{slug}.pdf"
        png_path = FIGURES_DIR / f"{slug}.png"
        if pdf_path.exists():
            _embed_pdf(pdf_path, slug, gist_url, description)
            print(f"  ✓ {pdf_path.name}")
            n_pdf += 1
        else:
            print(f"  ✗ {pdf_path.name}  (missing)")
        if png_path.exists():
            _embed_png(png_path, slug, gist_url, description)
            print(f"  ✓ {png_path.name}")
            n_png += 1
        else:
            print(f"  ✗ {png_path.name}  (missing)")
    print()
    print(f"Embedded gist URLs in {n_pdf} PDF + {n_png} PNG files "
          f"under {FIGURES_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
