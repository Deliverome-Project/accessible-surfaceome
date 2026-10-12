"""Every figure/export query on ``topology_public`` must pin a topology version.

``topology_public`` holds more than the served DeepTMHMM 1.0.24 release: test
runs, rescue fills, and since 2026-09-27 a full DeepTMHMM2 sweep under its own
unregistered versions. A query that filters only on cohort/species returns
whichever version's row comes first, silently mixing two predictors. That is
how the S14 exports came to read DeepTMHMM2 topology for 88 genes. The records'
loader pins the served version; the exports must too.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [
    *sorted((ROOT / "scripts/figures").glob("*.py")),
    *sorted((ROOT / "scripts/tsv-export").glob("*.py")),
    ROOT / "src/accessible_surfaceome/tools/surface_bind.py",
]
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"


def _unpinned_queries(path: Path) -> list[int]:
    bad = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            sql = node.value
            if "FROM topology_public" in sql and "topology_version" not in sql:
                bad.append(node.lineno)
    return bad


def test_worker_topology_public_queries_pin_a_version() -> None:
    """Same rule for the Worker's serve-time enrichment (template-literal SQL)."""
    import re

    src = WORKER.read_text(encoding="utf-8")
    unpinned = [
        src[: m.start()].count("\n") + 1
        for m in re.finditer(r"`([^`]*FROM\s+topology_public[^`]*)`", src)
        if "topology_version" not in m.group(1)
    ]
    assert not unpinned, f"unpinned topology_public queries in the Worker at lines {unpinned}"


def test_topology_public_queries_pin_a_version() -> None:
    offenders = {
        str(p.relative_to(ROOT)): lines for p in SCANNED if (lines := _unpinned_queries(p))
    }
    assert not offenders, (
        "topology_public queries without a topology_version filter (would mix "
        f"DeepTMHMM releases): {offenders}"
    )
