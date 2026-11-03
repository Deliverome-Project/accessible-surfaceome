"""Fold a built web edition into one self-contained HTML file.

``build.py --web OUT`` writes ``OUT/index.html`` beside an ``assets/``
directory, which is the right shape for a static site and the wrong one
for sending to a colleague: the page is useless without its folder. This
inlines the stylesheet, the script and every figure (as ``data:`` URIs)
so the single file opens anywhere.

Web fonts still come from Google Fonts, so offline the page falls back to
system fonts; everything else is in the file.

Usage::

    uv run python paper/inline_web.py paper/_draft/web/index.html out.html
"""
from __future__ import annotations

import base64
import mimetypes
import re
import sys
from pathlib import Path

ASSET_ATTR = re.compile(r'(?P<attr>\b(?:src|href|data-[\w-]+|poster))="(?P<path>assets/[^"]+)"')


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix == ".webp":
        mime = "image/webp"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def inline(index: Path) -> tuple[str, list[str]]:
    """Return (html, missing) for the page at ``index``."""
    root = index.parent
    html = index.read_text(encoding="utf-8")
    missing: list[str] = []

    def stylesheet(m: re.Match[str]) -> str:
        css = root / m.group("path")
        if not css.is_file():
            missing.append(m.group("path"))
            return m.group(0)
        return f"<style>\n{css.read_text(encoding='utf-8')}\n</style>"

    html = re.sub(
        r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="(?P<path>assets/[^"]+)"[^>]*>',
        stylesheet, html,
    )

    def script(m: re.Match[str]) -> str:
        js = root / m.group("path")
        if not js.is_file():
            missing.append(m.group("path"))
            return m.group(0)
        # `defer` means nothing on an inline script, so wait for the DOM
        # the way the deferred file did. "</script" inside the source
        # would end the element early.
        body = js.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return ("<script>document.addEventListener('DOMContentLoaded', function () {\n"
                f"{body}\n}});</script>")

    html = re.sub(
        r'<script\b[^>]*\bsrc="(?P<path>assets/[^"]+)"[^>]*>\s*</script>',
        script, html,
    )

    cache: dict[str, str] = {}

    def asset(m: re.Match[str]) -> str:
        rel = m.group("path")
        if rel not in cache:
            path = root / rel
            if not path.is_file():
                missing.append(rel)
                return m.group(0)
            cache[rel] = _data_uri(path)
        return f'{m.group("attr")}="{cache[rel]}"'

    html = ASSET_ATTR.sub(asset, html)
    return html, missing


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 64
    src, dest = Path(sys.argv[1]), Path(sys.argv[2])
    html, missing = inline(src)
    dest.write_text(html, encoding="utf-8")
    print(f"✓ Wrote {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")
    if missing:
        print("  ⚠ not found, left as links: " + ", ".join(sorted(set(missing))))
    left = len(re.findall(r'="assets/', html))
    if left:
        print(f"  ⚠ {left} reference(s) to assets/ remain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
