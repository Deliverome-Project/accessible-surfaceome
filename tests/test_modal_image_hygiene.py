"""Guard against Modal container images accidentally baking local secrets.

``modal.Image.add_local_dir(".", ..., copy=True, ignore=[...])`` does not read
``.gitignore`` — it only skips patterns listed in ``ignore``. Omitting ``.env``
or ``wrangler.toml`` bakes live developer credentials into cached Modal layers.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODAL_DIR = Path(__file__).resolve().parents[1] / "modal"
_REQUIRED_IGNORES = {".env", ".env.*", "**/wrangler.toml"}


def _string_list(node: ast.AST | None) -> set[str]:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return set()
    return {
        elt.value
        for elt in node.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    }


def test_modal_repo_copies_ignore_local_secrets() -> None:
    checked = 0
    for path in sorted(_MODAL_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute) and node.func.attr == "add_local_dir"):
                continue
            src = node.args[0] if node.args else None
            if not (isinstance(src, ast.Constant) and src.value == "."):
                continue
            checked += 1
            ignore_kw = next((kw.value for kw in node.keywords if kw.arg == "ignore"), None)
            ignored = _string_list(ignore_kw)
            missing = sorted(_REQUIRED_IGNORES - ignored)
            assert not missing, (
                f"{path.name}:{node.lineno}: add_local_dir('.') must ignore {missing} "
                "so local secrets are never baked into Modal image layers"
            )
    assert checked >= 1, "expected at least one modal add_local_dir('.') call to verify"
