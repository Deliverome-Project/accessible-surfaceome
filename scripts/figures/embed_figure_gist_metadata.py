"""Embed gist URLs and schema-v1 ``provenance`` JSON into the PDF + PNG
metadata of every figure in ``data/analysis/figures/``. Idempotent —
re-run after any figure regeneration to refresh metadata.

PDFs: pikepdf, XMP ``dc:*`` fields and ``pdf:Keywords``.
PNGs: PIL, ``tEXt`` chunks.

The ``provenance`` JSON conforms to
``src/accessible_surfaceome/_provenance.py`` (schema v1). Existing
``Source`` / ``dc:source`` fields are preserved for back-compat with
the prior convention.

Update :data:`FIGURE_PROVENANCE` below when a figure's gist is
rotated, a new SWHID is minted via Software Heritage's Save Code Now,
or a new figure earns a slot.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# pikepdf + PIL are heavy imports needed only for the actual embedding
# (writing to PDF/PNG metadata). Other consumers — e.g. the
# scripts/release/publish-archive.py audit phase — just read the
# FIGURE_PROVENANCE dict and shouldn't pay the import cost. Lazy-loaded
# inside _embed_pdf / _embed_png below.

from accessible_surfaceome._provenance import build_provenance, validate_provenance
from accessible_surfaceome.paths import REPO_ROOT

FIGURES_DIR = REPO_ROOT / "data/analysis/figures"
REPO_URL = "https://github.com/Deliverome-Project/accessible-surfaceome"

# Reserved DOI of the Zenodo data record this project ships. Preserved
# across draft updates; activates on publish. Single source of truth so
# we don't have to fan it out across every figure's ``doi`` field.
# Defined here so the embedded figure metadata, the publish script, and
# the gist READMEs can all reference the same identifier.
ZENODO_DATA_DOI = "10.5281/zenodo.20805384"

# Per-figure provenance. Keep keys in slug order. Fill ``swhid`` once
# Software Heritage has archived a given gist (see ``docs/figure-
# reproducibility-schema.md`` § Save Code Now). The top-level ``doi``
# is the data-supplement DOI a reader would cite for the figure — i.e.
# ZENODO_DATA_DOI when the figure ships as part of this paper.
# ``data[].doi`` is the per-file DOI, only set when that specific file
# is bundled in the deposit.
FIGURE_PROVENANCE: dict[str, dict[str, Any]] = {
    "db_overlap_venn": {
        "title": "M1 surface DB overlap — 5-way Venn",
        "gist_url": "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa",
        "gist_sha": "c1253926045bfd5aad70cc5cce7598b0024fcd31",
        "swhid": "swh:1:snp:ab608a15f4ee00e602cbb317b3f43313214cec08",
        "doi": ZENODO_DATA_DOI,  # reserved; activates on publish
        "repo": "Deliverome-Project/accessible-surfaceome",
        "repo_path": "scripts/triage_bench_db_venn.py",
        "repo_ref": "898c743d9df4ec7497e7424b80d3408e5ad07c41",
        "repo_tag": None,
        "data": [
            {
                "url": (
                    "https://raw.githubusercontent.com/Deliverome-Project/"
                    "accessible-surfaceome/898c743d9df4ec7497e7424b80d3408e5ad07c41/"
                    "data/processed/candidate_universe/candidate_universe.tsv"
                ),
                "sha256": "2406464f3f86680e76844fe07e9aa32e5550960bc9fa5573137bb31c15ea3ef2",
                # Git-blob SWHID for this file (content-addressed).
                # Resolves via Software Heritage once the repo archive
                # request 2332998 completes its initial crawl.
                "swhid": "swh:1:cnt:e7a29bb9ab3b4a1746ac25726e818377ecac3392",
                # data[].doi stays None — candidate_universe.tsv is NOT
                # yet a deposited artifact in the Zenodo data record.
                # Becomes ZENODO_DATA_DOI if added to EXTRA_FILES.
                "doi": None,
            }
        ],
    },
    # FUTURE: enter the other 7 figures from MEMORY.md figure_gists.md.
    # For figures whose underlying data IS in the Zenodo deposit
    # (triage runs, benchmark) — set the matching ``data[].url`` to
    # the Zenodo file URL and ``data[].doi`` to ZENODO_DATA_DOI. The
    # top-level ``doi`` should be ZENODO_DATA_DOI for every figure
    # shipping as part of this paper.
}

# Legacy slug → secret gist URL. Preserved for back-compat with the
# previous convention. Synthesised from ``FIGURE_PROVENANCE``.
FIGURE_GISTS: dict[str, str] = {
    slug: prov["gist_url"] for slug, prov in FIGURE_PROVENANCE.items() if prov.get("gist_url")
}


def _build_blob(slug: str) -> dict[str, Any]:
    prov = FIGURE_PROVENANCE[slug]
    blob = build_provenance(**prov)
    validate_provenance(blob)
    return blob


def _embed_pdf(path: Path, slug: str, gist_url: str, description: str, blob_json: str) -> None:
    import pikepdf  # noqa: PLC0415 — lazy: see module-level comment
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            meta["dc:title"] = slug
            meta["dc:description"] = description
            meta["dc:subject"] = ["accessible-surfaceome", slug, "reproduction-gist"]
            meta["dc:source"] = gist_url
            meta["pdf:Keywords"] = blob_json
        pdf.save(path)


def _embed_png(path: Path, slug: str, gist_url: str, description: str, blob_json: str) -> None:
    from PIL import Image, PngImagePlugin  # noqa: PLC0415 — lazy
    img = Image.open(path)
    info = PngImagePlugin.PngInfo()
    for k, v in (img.info or {}).items():
        if k == "provenance":  # always rewrite the canonical key from FIGURE_PROVENANCE
            continue
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
    info.add_text("provenance", blob_json)
    img.save(path, "PNG", pnginfo=info)


def main() -> int:
    n_pdf = 0
    n_png = 0
    for slug in FIGURE_PROVENANCE:
        try:
            blob = _build_blob(slug)
        except Exception as exc:
            print(f"  ✗ {slug}: provenance invalid — {exc}")
            continue
        blob_json = json.dumps(blob, separators=(",", ":"))
        gist_url = FIGURE_PROVENANCE[slug].get("gist_url") or ""
        description = f"Reproduction gist: {gist_url}  |  Repo: {REPO_URL}"
        pdf_path = FIGURES_DIR / f"{slug}.pdf"
        png_path = FIGURES_DIR / f"{slug}.png"
        if pdf_path.exists():
            _embed_pdf(pdf_path, slug, gist_url, description, blob_json)
            print(f"  ✓ {pdf_path.name}")
            n_pdf += 1
        else:
            print(f"  ✗ {pdf_path.name}  (missing)")
        if png_path.exists():
            _embed_png(png_path, slug, gist_url, description, blob_json)
            print(f"  ✓ {png_path.name}")
            n_png += 1
        else:
            print(f"  ✗ {png_path.name}  (missing)")
    print(f"\nEmbedded provenance in {n_pdf} PDFs and {n_png} PNGs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
