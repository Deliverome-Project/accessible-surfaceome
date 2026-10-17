"""Convert canonical figure PDFs into the paper build's vector SVGs.

``paper/figure_manifest.json`` points most figures at ``paper/figures/<slug>.svg``,
converted from ``data/analysis/figures/<slug>.pdf``. Each SVG is stamped with
the SHA-256 of the PDF it came from, so ``tests/test_paper_figure_svgs_current.py``
can tell a stale SVG from a current one in any checkout, shallow CI clones
included. Re-run this after re-rendering a figure.

    uv run python paper/convert_figure_svgs.py                 # every manifest SVG
    uv run python paper/convert_figure_svgs.py surfaceome_deterministic_features
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "paper/figure_manifest.json"
PDF_DIR = ROOT / "data/analysis/figures"
SVG_DIR = ROOT / "paper/figures"
STAMP_PREFIX = "<!-- source-pdf-sha256: "
# SVGs built by a composer script rather than converted from <slug>.pdf. The
# composer writes the same file to paper/figures/ and data/analysis/figures/,
# so the test checks those two copies agree instead of a PDF hash.
COMPOSED = {"deep_dive_flow": "scripts/figures/compose_deep_dive_figure.py"}


def svg_slugs() -> list[str]:
    """Manifest slugs rendered as SVG from a canonical PDF."""
    m = json.loads(MANIFEST.read_text())
    return sorted(
        e["slug"]
        for key in ("figures", "appendix_figures", "supplementary_figures")
        for e in (m.get(key) or {}).values()
        if e["format"] == "svg"
        and e["slug"] not in COMPOSED
        and (PDF_DIR / f"{e['slug']}.pdf").is_file()
    )


def pdf_sha256(slug: str) -> str:
    return hashlib.sha256((PDF_DIR / f"{slug}.pdf").read_bytes()).hexdigest()


def stamp_of(svg: Path) -> str | None:
    """The source-PDF hash recorded in an SVG, or None if it has none."""
    for line in svg.read_text(encoding="utf-8").splitlines()[:3]:
        if line.startswith(STAMP_PREFIX):
            return line.removeprefix(STAMP_PREFIX).removesuffix(" -->").strip()
    return None


def convert(slug: str) -> Path:
    out = SVG_DIR / f"{slug}.svg"
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "out.svg"
        subprocess.run(
            ["pdftocairo", "-svg", str(PDF_DIR / f"{slug}.pdf"), str(raw)], check=True
        )
        lines = raw.read_text(encoding="utf-8").splitlines(keepends=True)
    head = 1 if lines and lines[0].startswith("<?xml") else 0
    lines.insert(head, f"{STAMP_PREFIX}{pdf_sha256(slug)} -->\n")
    out.write_text("".join(lines), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "slugs", nargs="*", help="figure slugs (default: every manifest SVG)"
    )
    args = ap.parse_args()
    for slug in args.slugs or svg_slugs():
        print(f"wrote {convert(slug).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
