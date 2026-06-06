"""Guard against silent drift between the Cloudflare Worker's served
records and the current ``SurfaceomeRecord`` Pydantic schema.

The Worker enriches at serve time by injecting raw JavaScript objects into
the returned record (the LEFT JOIN blocks in
``cloudflare/workers/surfaceome_api/src/index.js`` ``handleGene()``). Nothing
in the Worker code path validates those injections against the Pydantic
schema — if you add a field to ``HomoOligomerizationFeatures`` /
``ParalogEntry`` / etc. and forget to update the Worker injection, the
served record will be missing the field and the viewer will silently render
``undefined`` for it.

This test fetches a handful of representative production records from the
live Worker at ``api.deliverome.org`` and validates each against
``SurfaceomeRecord.model_validate(...)``. Any drift (missing field, wrong
type, unrecognized field) fails the test with a Pydantic ``ValidationError``
that points directly at the offending field.

Categories of drift this catches:

* **Cat 2 (Worker↔Pydantic):** A new Pydantic field that the Worker doesn't
  inject when enriching old records. The served JSON validates only if every
  enriched record carries every field the schema declares.
* **Schema regressions on the served side:** A type tightening (e.g.
  ``int`` → ``Literal[1, 2, 3]``) that the Worker's injection doesn't
  honor.

Categories this does NOT catch:

* **Cat 1 (Pydantic↔TS):** Use ``check_viewer_types_sync.py`` for that.
* **Cat 3 (orchestrator-post-pass derivations missing on old records):**
  Old records served by the Worker may lack ``accessibility_risks
  .homo_oligomerization_prediction`` etc. because the Worker doesn't mirror
  every orchestrator post-pass. Those fields are defined as ``Optional``
  in the schema so validation passes; the gap is a separate concern,
  documented in the dual-pattern memory entry.

Mark as ``@pytest.mark.network`` so this runs on opt-in / offline runs
skip via ``pytest -m 'not network'`` (the standard pattern used by the
rest of the live-API tests in this repo). Cheap on a warm CDN cache
(~50ms / gene); slower on a cold one.

Sample genes were picked to span:
* A canonical receptor (EGFR — common reference case).
* A globular intracellular kinase (SRC — exercises empty-ECD edge cases).
* An orphan GPCR (GPR75 — exercises sparse-paralog / sparse-ortholog
  branches).
* A Schweke-positive homomer (HSPA5 — exercises ``homo_oligomerization``
  populated path).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

WORKER_BASE = "https://api.deliverome.org/surfaceome"

# Representative gene set. Add to this if a future schema field needs a
# gene whose record exercises a specific branch — e.g. a heavily-shed
# protein for shed_form coverage. Keep the list short; each gene is one
# HTTP fetch on a (potentially) cold cache.
LIVE_GENES = [
    "EGFR",
    "SRC",
    "GPR75",
    "HSPA5",
]


def _fetch_record(symbol: str) -> dict:
    """Fetch the served record for ``symbol`` from the live Worker.

    Strips raw control characters from the response before parsing because
    the Worker's JSON occasionally carries an unescaped \\x00 / \\x01 in
    UniProt comment text that breaks strict ``json.loads``. Returns the
    parsed dict.
    """
    req = urllib.request.Request(
        f"{WORKER_BASE}/v1/genes/{symbol}",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 — public API
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"live Worker unreachable for {symbol}: {exc}")
    clean = "".join(c for c in raw if c >= " " or c in "\n\r\t")
    return json.loads(clean)


@pytest.mark.network
@pytest.mark.parametrize("symbol", LIVE_GENES)
def test_served_record_validates_against_schema(symbol: str) -> None:
    """Each representative record from the live Worker validates against the
    current ``SurfaceomeRecord`` schema.

    A failure here means either:
    1. The Worker's LEFT JOIN injection (handleGene in
       cloudflare/workers/surfaceome_api/src/index.js) is missing a field
       the schema now requires — update the injection to mirror the
       Pydantic shape.
    2. The Pydantic schema added a strict type / required field that an
       old record can't satisfy — either widen the field (default,
       Optional) or extend the Worker's back-compat enrichment.
    3. The record JSON the Worker serves has corrupted (extra/missing
       commas, wrong key names) — unlikely but worth checking.
    """
    record = _fetch_record(symbol)
    try:
        SurfaceomeRecord.model_validate(record)
    except ValidationError as exc:
        pytest.fail(
            f"Worker-served record for {symbol} does not validate against "
            f"SurfaceomeRecord (schema_version={record.get('schema_version')!r}). "
            f"Cat 2 drift between Worker injection and Pydantic schema "
            f"is the likely cause — see test docstring for remediation. "
            f"ValidationError:\n{exc}"
        )
