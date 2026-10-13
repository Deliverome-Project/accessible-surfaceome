"""The Worker and the archiver must agree on the degraded-response header name."""

from __future__ import annotations

import re
from pathlib import Path

from accessible_surfaceome.cloud.record_history.archive import DEGRADED_HEADER

_WORKER = (
    Path(__file__).resolve().parents[1]
    / "cloudflare/workers/surfaceome_api/src/index.js"
)


def test_worker_and_archiver_use_the_same_degraded_header() -> None:
    m = re.search(
        r'const DEGRADED_HEADER = "([^"]+)";', _WORKER.read_text(encoding="utf-8")
    )
    assert m, "DEGRADED_HEADER literal not found in the Worker"
    assert m.group(1) == DEGRADED_HEADER
