"""Static integrity checks for the modular Cloudflare Worker source tree."""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from _worker_test_util import WORKER_SRC_DIR

_EXPORT_DECL_RE = re.compile(
    r"^export\s+(?:async\s+)?(?:function|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
    re.MULTILINE,
)
_IMPORT_BLOCK_RE = re.compile(r"import\s*\{([^}]+)\}\s*from")
_LOCAL_DECL_RE = re.compile(
    r"\b(?:function|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"
)


def test_every_worker_module_has_valid_js_syntax() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    js_files = sorted(WORKER_SRC_DIR.rglob("*.js"))
    assert js_files, f"no Worker JS files found under {WORKER_SRC_DIR}"
    for js_file in js_files:
        proc = subprocess.run(
            [node, "--check", str(js_file)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"Syntax error in {js_file.relative_to(WORKER_SRC_DIR)}:\n{proc.stderr}"
        )


def test_no_missing_cross_module_imports_in_worker() -> None:
    """Catch forgotten cross-module imports (including `...SPREAD` usages) statically."""
    js_files = sorted(WORKER_SRC_DIR.rglob("*.js"))
    exports: dict[str, str] = {}
    for path in js_files:
        rel = path.relative_to(WORKER_SRC_DIR).as_posix()
        for m in _EXPORT_DECL_RE.finditer(path.read_text(encoding="utf-8")):
            exports[m.group(1)] = rel

    missing: list[str] = []
    for path in js_files:
        rel = path.relative_to(WORKER_SRC_DIR).as_posix()
        raw = path.read_text(encoding="utf-8")
        no_comments = re.sub(r"//.*", "", raw)
        no_comments = re.sub(r"/\*[\s\S]*?\*/", "", no_comments)

        imported: set[str] = set()
        for m in _IMPORT_BLOCK_RE.finditer(no_comments):
            for tok in m.group(1).split(","):
                tok = tok.strip()
                if tok:
                    imported.add(tok.split(" as ")[-1].strip())
        local_decls = set(_LOCAL_DECL_RE.findall(no_comments))

        for sym, owner in sorted(exports.items()):
            if owner == rel or sym in imported or sym in local_decls:
                continue
            # `json` appears inside `'application/json'` string literals.
            if sym == "json":
                continue
            pattern = re.compile(
                rf"(?:\.\.\.|(?<![.\w$])){re.escape(sym)}(?![\w$])"
            )
            for m in pattern.finditer(no_comments):
                if not re.match(r"\s*:", no_comments[m.end() : m.end() + 5]):
                    missing.append(f"{rel} references `{sym}` (exported by {owner})")
                    break

    assert not missing, "Missing Worker ES module imports:\n  " + "\n  ".join(missing)
