"""Shared helpers for staging and inspecting the Cloudflare Worker in tests."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_SRC_DIR = REPO_ROOT / "cloudflare" / "workers" / "surfaceome_api" / "src"

_CATALOG_PRESETS_IMPORT_RE = re.compile(
    r'^import \{[^}]*\} from "[^"]*catalog-presets";\s*$',
    re.MULTILINE,
)

DEFAULT_CATALOG_PRESETS_STUB = (
    "const deepDiveTier = () => ({ tier: 'likely', facet: null });\n"
    "const isLowLiteratureSurface = () => false;"
)


def stage_worker_for_node(
    dest_dir: Path,
    *,
    catalog_presets_stub: str = DEFAULT_CATALOG_PRESETS_STUB,
) -> Path:
    """Copy the Worker ES module tree into ``dest_dir`` and expose ``worker.mjs``.

    Replaces the cross-directory ``viewer/lib/catalog-presets`` TypeScript
    import (which wrangler/esbuild resolves at bundle time, not plain Node)
    with ``catalog_presets_stub`` wherever it appears, writes a ``package.json``
    with ``{"type": "module"}`` so relative ``.js`` imports resolve as ESM, and
    creates ``dest_dir / "worker.mjs"`` re-exporting ``./index.js``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "package.json").write_text(
        json.dumps({"type": "module"}) + "\n", encoding="utf-8"
    )
    stubbed_count = 0
    for src_file in sorted(WORKER_SRC_DIR.rglob("*.js")):
        rel = src_file.relative_to(WORKER_SRC_DIR)
        dst = dest_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src_file.read_text(encoding="utf-8")
        patched, n = _CATALOG_PRESETS_IMPORT_RE.subn(catalog_presets_stub, text)
        stubbed_count += n
        if n:
            dst.write_text(patched, encoding="utf-8")
        else:
            shutil.copy2(src_file, dst)

    assert stubbed_count == 1, (
        f"expected exactly one catalog-presets import to stub across {WORKER_SRC_DIR}; "
        f"found {stubbed_count}"
    )

    worker_entry = dest_dir / "worker.mjs"
    worker_entry.write_text(
        'export { default } from "./index.js";\nexport * from "./index.js";\n',
        encoding="utf-8",
    )
    return worker_entry


def read_all_worker_source() -> str:
    """Return concatenated source of all Worker ``.js`` modules in deterministic order."""
    return "\n".join(
        f"// === {p.relative_to(WORKER_SRC_DIR).as_posix()} ===\n"
        + p.read_text(encoding="utf-8")
        for p in sorted(WORKER_SRC_DIR.rglob("*.js"))
    )
