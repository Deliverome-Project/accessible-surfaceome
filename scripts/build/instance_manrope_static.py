"""Instance static Manrope weights from the bundled variable font.

matplotlib cannot select a weight inside a variable font, so figures need one
static file per weight. These are cut from ``assets/fonts/Manrope-VariableFont_wght.ttf``
(Google Fonts Manrope) rather than downloaded, so every weight carries the
variable font's full character set. The ``.otf`` statics they replace were an
older Manrope release missing ≥ ≤ ≈, super/subscript digits and µ.

``instantiateVariableFont`` leaves the variable font's name records in place
("Manrope ExtraLight"), which mislabels the embedded font in PDFs, so the name
table is rewritten for each weight.

Usage:
    uv run python scripts/build/instance_manrope_static.py
"""
from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

REPO = Path(__file__).resolve().parents[2]
FONTS = REPO / "assets" / "fonts"
VARIABLE = FONTS / "Manrope-VariableFont_wght.ttf"

WEIGHTS = {
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
}


def _rename(font: TTFont, style: str) -> None:
    """Point every family/style name record at this static weight."""
    names = {
        1: "Manrope",
        2: style,
        3: f"Manrope-{style};instanced",
        4: f"Manrope {style}",
        6: f"Manrope-{style}",
        16: "Manrope",
        17: style,
    }
    table = font["name"]
    for name_id in (1, 2, 3, 4, 6, 16, 17, 25):
        table.removeNames(nameID=name_id)
    for name_id, value in names.items():
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)


def main() -> None:
    for style, wght in WEIGHTS.items():
        font = instantiateVariableFont(TTFont(VARIABLE), {"wght": wght})
        _rename(font, style)
        font["OS/2"].usWeightClass = wght
        out = FONTS / f"Manrope-{style}.ttf"
        font.save(out)
        print(f"wrote {out.relative_to(REPO)} (wght={wght}, {len(font.getBestCmap())} chars)")


if __name__ == "__main__":
    main()
