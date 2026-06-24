"""Post-pandoc step: rewrite figure ``<img src>`` to point at the canonical
asset under ``data/analysis/figures/`` (per ``paper/figure_manifest.json``),
and validate the resolution / format before the PDF render.

Why: the .docx the author hands to the build often carries an OUT-OF-DATE
bitmap of each figure (e.g. a Word-pasted PNG that pre-dates the latest
canonical render). The figure in the published PDF must reflect the
current HEAD-of-main render — that's the figure citizens see on the
viewer, the gist, and the Zenodo deposit. This module rewires each
``<figure>`` in the pandoc-emitted HTML to point at the canonical asset
file before WeasyPrint rasterises / vectorises into the PDF.

Resolution checks fail-fast on bad inputs:

  • format='png' → require ≥ ``min_dpi`` (default 600). PIL reads the
    PNG ``dpi`` tEXt; matplotlib's ``save_figure`` helper writes
    600 DPI by default after the 2026-06-24 bump.
  • format='svg' → require a real SVG (root element is ``<svg>``).
    Pure-vector SVGs need no DPI check; SVGs that wrap an embedded
    base64 raster get flagged with a soft warning (the wrapped
    raster keeps its own resolution).
  • format='pdf' → require a real PDF (header starts with ``%PDF-``).

Strict mode (``--strict``) escalates warnings to errors. Default mode
keeps the build moving and prints a list of issues so the author can
choose to re-render or accept.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from lxml import html as lxml_html


# ── Public types ───────────────────────────────────────────────────────


@dataclass
class FigureSpec:
    """One row from ``paper/figure_manifest.json``."""

    slug: str
    format: str
    min_dpi: int | None = None
    optional: bool = False
    description: str = ""

    @property
    def filename(self) -> str:
        return f"{self.slug}.{self.format}"


@dataclass
class SwapReport:
    """Outcome of a figure-swap pass. ``issues`` are human-readable
    strings; ``swapped`` and ``skipped`` are img→canonical maps."""

    swapped: dict[str, Path] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


# ── Manifest loader ────────────────────────────────────────────────────


def load_manifest(path: Path) -> dict[str, FigureSpec]:
    """Parse the manifest into ``{key: FigureSpec}`` where key is
    ``"N"`` for main figures and ``"appendix-N"`` for appendix figures.
    Matches the id shape pandoc emits for figure captions
    (``id="figure-N"`` or ``id="appendix-figure-N"``)."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text())
    out: dict[str, FigureSpec] = {}
    for n, entry in (raw.get("figures") or {}).items():
        out[str(n)] = _entry_to_spec(entry)
    for n, entry in (raw.get("appendix_figures") or {}).items():
        out[f"appendix-{n}"] = _entry_to_spec(entry)
    return out


def _entry_to_spec(entry: dict) -> FigureSpec:
    return FigureSpec(
        slug=entry["slug"],
        format=entry["format"],
        min_dpi=entry.get("min_dpi"),
        optional=bool(entry.get("optional", False)),
        description=entry.get("description", ""),
    )


# ── Resolution / format validator ─────────────────────────────────────


def validate_canonical_asset(spec: FigureSpec, figures_dir: Path) -> list[str]:
    """Check that the canonical asset exists and meets the format / DPI
    requirements declared in the manifest. Returns a list of
    human-readable issues (empty if everything checks out)."""
    issues: list[str] = []
    path = figures_dir / spec.filename
    if not path.is_file():
        msg = f"{spec.filename}: canonical asset missing at {path}"
        return [msg] if not spec.optional else [f"{msg} (marked optional)"]

    fmt = spec.format.lower()
    if fmt == "png":
        issues.extend(_validate_png(path, spec))
    elif fmt == "svg":
        issues.extend(_validate_svg(path, spec))
    elif fmt == "pdf":
        issues.extend(_validate_pdf(path, spec))
    else:
        issues.append(
            f"{spec.filename}: unknown format {fmt!r} "
            f"(expected 'png', 'svg', or 'pdf')"
        )
    return issues


def _validate_png(path: Path, spec: FigureSpec) -> list[str]:
    """PNG: require ≥ min_dpi (default 600). DPI lives in the ``info['dpi']``
    tuple Pillow exposes for PNG/JPEG. Matplotlib emits this when
    ``save_figure`` is called with ``dpi=N`` (which the project's
    ``_plotting_config.save_figure`` does at 600 by default since
    2026-06-24)."""
    try:
        from PIL import Image  # transitively via WeasyPrint
    except ImportError:
        return [f"{path.name}: cannot validate PNG DPI — Pillow not installed"]
    try:
        with Image.open(path) as img:
            dpi = img.info.get("dpi")
    except Exception as exc:  # noqa: BLE001 — surface arbitrary PIL errors
        return [f"{path.name}: failed to read PNG metadata: {exc}"]
    min_dpi = spec.min_dpi or 600
    if dpi is None:
        return [
            f"{path.name}: PNG has no DPI metadata (required ≥ {min_dpi}). "
            f"Re-render with `dpi={min_dpi}` so the writer embeds it."
        ]
    # ``round()`` not ``int()`` — matplotlib's PNG writer emits DPI as
    # 599.9988 when asked for 600 (libpng rounding quirk). Truncating
    # would falsely fail on every figure we render.
    actual = min(round(dpi[0]), round(dpi[1]))
    if actual < min_dpi:
        return [
            f"{path.name}: PNG DPI {actual} < required {min_dpi}. "
            f"Re-render with `dpi={min_dpi}`."
        ]
    return []


def _validate_svg(path: Path, _spec: FigureSpec) -> list[str]:
    """SVG: parse with lxml, require root tag = ``svg``. Soft-warn if
    the SVG contains a base64-embedded raster (the embedded image
    keeps its own resolution; the SVG wrapper doesn't gain anything
    from being vector in that case)."""
    try:
        tree = lxml_html.fromstring(path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        return [f"{path.name}: failed to parse SVG: {exc}"]
    root_tag = (tree.tag or "").split("}")[-1].lower()
    if root_tag != "svg":
        return [
            f"{path.name}: root element is <{root_tag}>, expected <svg>"
        ]
    if b"data:image" in path.read_bytes():
        return [
            f"{path.name}: SVG wraps a base64-embedded raster — "
            f"the embedded bitmap's resolution is whatever it was when "
            f"exported, not 'vector-quality at any zoom'."
        ]
    return []


def _validate_pdf(path: Path, _spec: FigureSpec) -> list[str]:
    head = path.read_bytes()[:8]
    if not head.startswith(b"%PDF-"):
        return [f"{path.name}: not a PDF (file header = {head!r})"]
    return []


# ── HTML rewrite ──────────────────────────────────────────────────────


def swap_figures(
    html_path: Path,
    manifest: dict[str, FigureSpec],
    figures_dir: Path,
) -> SwapReport:
    """Walk the pandoc-emitted HTML, find each anchored figure paragraph
    (``<p><span id="figure-N"></span><img></p>``), look up the matching
    manifest entry, validate the canonical asset, and rewrite the
    ``<img src>`` to point at it (absolute path so WeasyPrint resolves
    cleanly regardless of base_url)."""
    report = SwapReport()
    if not manifest:
        return report

    doc = lxml_html.parse(str(html_path)).getroot()
    spans = doc.xpath(
        "//span[starts-with(@id, 'figure-') or starts-with(@id, 'appendix-figure-')]"
    )
    for span in spans:
        span_id = span.get("id", "")
        key = _key_from_span_id(span_id)
        if key is None:
            continue
        spec = manifest.get(key)
        if spec is None:
            report.skipped.append(
                f"{span_id}: no manifest entry for key {key!r}"
            )
            continue

        # The <p> containing the span SHOULD also contain the <img>.
        parent_p = span.getparent()
        if parent_p is None or parent_p.tag != "p":
            report.skipped.append(
                f"{span_id}: anchor span not inside a <p>"
            )
            continue
        imgs = parent_p.xpath(".//img")
        if not imgs:
            report.skipped.append(f"{span_id}: <p> has no <img> to swap")
            continue

        # Validate canonical asset first; surface every issue
        # regardless of swap outcome so the author sees all problems
        # in one build.
        report.issues.extend(validate_canonical_asset(spec, figures_dir))

        canonical_path = (figures_dir / spec.filename).resolve()
        for img in imgs:
            img.set("src", str(canonical_path))
            # Drop any in-docx sizing hints so the print CSS controls
            # the figure card's width (img max-width: 100%).
            for attr in ("width", "height", "style"):
                if attr in img.attrib:
                    del img.attrib[attr]
        report.swapped[span_id] = canonical_path

    # Write back. Use method='html' to keep tag self-closing where
    # appropriate (e.g. <img />) and avoid lxml's xml-mode quirks.
    html_path.write_bytes(
        lxml_html.tostring(doc, method="html", encoding="utf-8", doctype="<!DOCTYPE html>")
    )
    return report


def _key_from_span_id(span_id: str) -> str | None:
    """Pull the manifest key out of an anchor id. Pandoc emits ids like
    ``figure-2-deep-dive-final-categories`` (slugified caption) — we
    only need the leading number. Appendix figures: ``appendix-figure-1-…``
    → key=``"appendix-1"``."""
    if span_id.startswith("appendix-figure-"):
        rest = span_id[len("appendix-figure-"):]
        num, _, _ = rest.partition("-")
        return f"appendix-{num}" if num.isdigit() else None
    if span_id.startswith("figure-"):
        rest = span_id[len("figure-"):]
        num, _, _ = rest.partition("-")
        return num if num.isdigit() else None
    return None


def format_report(report: SwapReport) -> str:
    """Pretty-print a SwapReport for the build log."""
    lines: list[str] = []
    if report.swapped:
        lines.append(f"  swapped {len(report.swapped)} figure(s):")
        for span_id, p in sorted(report.swapped.items()):
            lines.append(f"    {span_id}  →  {p.name}")
    if report.skipped:
        lines.append(f"  skipped {len(report.skipped)} figure(s):")
        for s in report.skipped:
            lines.append(f"    {s}")
    if report.issues:
        lines.append(f"  ⚠ {len(report.issues)} resolution / format issue(s):")
        for i in report.issues:
            lines.append(f"    {i}")
    return "\n".join(lines) if lines else "  (manifest empty or no figures matched)"


# ── CLI entry — useful for ad-hoc validation without a full build ─────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical figure assets named in "
            "paper/figure_manifest.json against their format / DPI "
            "requirements. Standalone — no docx required."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent / "figure_manifest.json",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/analysis/figures",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero if any resolution / format check fails.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if not manifest:
        print(f"no manifest entries at {args.manifest}")
        return 0

    all_issues: list[str] = []
    for key, spec in sorted(manifest.items()):
        issues = validate_canonical_asset(spec, args.figures_dir)
        prefix = f"figure {key}: {spec.filename}"
        if not issues:
            print(f"  ✓ {prefix}")
        else:
            print(f"  ✗ {prefix}")
            for i in issues:
                print(f"      {i}")
            all_issues.extend(issues)

    if args.strict and all_issues:
        print(f"\n{len(all_issues)} issue(s) — strict mode → exit 1", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
