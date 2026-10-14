"""Manuscript → structured JATS, as one step two callers share.

``paper/build.py`` writes the JATS beside the PDF; the Zenodo release
script (``scripts/release/publish-archive.py``) writes the copy that is
deposited. They used to convert separately, and the release script's was
pandoc's raw output — so the deposited XML had no title, authors,
abstract, figures or reference list while the build's did. Both now call
:func:`build_jats`.

It shells out to a ``pandoc`` binary the caller names, so it needs
neither ``pypandoc`` nor WeasyPrint: the build passes the one bundled
with pypandoc, the release script the one on ``PATH``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from figure_swap import load_manifest, resolve_asset  # ty: ignore[unresolved-import]
from jats_polish import PolishReport, polish_jats  # ty: ignore[unresolved-import]

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
FILTERS_DIR = PAPER_DIR / "filters"
# Order matters: refs_dois unwraps the Zotero link around each reference
# before citations indexes them; sections indexes the headings figures
# leaves behind.
JATS_FILTERS = ("refs_dois.lua", "figures.lua", "sections.lua", "citations.lua")
FIGURE_MANIFEST = PAPER_DIR / "figure_manifest.json"
FIGURE_SEARCH_PATH = [PAPER_DIR / "figures", REPO_ROOT / "data" / "analysis" / "figures"]


def build_jats(
    src: Path,
    xml_path: Path,
    *,
    pandoc: str = "pandoc",
    figures_out: Path | None = None,
    href_prefix: str = "figures/",
    extra_args: tuple[str, ...] | list[str] = (),
) -> tuple[PolishReport, list[Path]]:
    """Convert ``src`` to structured JATS at ``xml_path``.

    Each figure's canonical asset is copied into ``figures_out`` and the
    XML names it as ``href_prefix + filename`` — ``"figures/"`` for a
    build directory, ``""`` for a deposit with a flat file namespace,
    where the figures sit beside the XML. With ``figures_out=None``
    nothing is copied and the XML keeps the images the ``.docx``
    embedded.

    Returns the polish report and the figure files written.
    """
    env = dict(os.environ)
    env["PAPER_ASSETS_DIR"] = str(PAPER_DIR / "assets")
    env.pop("PAPER_WEB_EXTRAS", None)  # the web-only resource links
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        pandoc, str(src), "--standalone", "--metadata=lang:en-US",
        "--to", "jats", "-o", str(xml_path),
        *(f"--lua-filter={FILTERS_DIR / name}" for name in JATS_FILTERS),
        *extra_args,
    ]
    try:
        subprocess.run(cmd, check=True, cwd=REPO_ROOT, env=env)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"pandoc JATS conversion failed (exit {exc.returncode}). "
            f"Command: {' '.join(cmd)}"
        ) from exc

    manifest = load_manifest(FIGURE_MANIFEST)
    written: list[Path] = []

    def graphic_for(key: str) -> str | None:
        if figures_out is None:
            return None
        spec = manifest.get(key)
        asset = resolve_asset(spec, FIGURE_SEARCH_PATH) if spec else None
        if asset is None:
            return None
        figures_out.mkdir(parents=True, exist_ok=True)
        dest = figures_out / asset.name
        shutil.copyfile(asset, dest)
        if dest not in written:
            written.append(dest)
        return f"{href_prefix}{asset.name}"

    report = polish_jats(xml_path, graphic_for)
    return report, written
