"""Field-level response-shape guard for the shared ``surfaceome-api`` Worker.

WHY THIS EXISTS, CONCRETELY. On 2026-10-15 two deploys each silently deleted a
field the other session had live. A deploy at 03:01 UTC added
``deterministic_features.bindome``; a deploy at 19:04 UTC replaced the script
wholesale and removed it. The second deploy ran the full main/dev-inclusive
checklist in CLAUDE.md and it PASSED, because:

* steps 1-2 compare the Worker SOURCE across ``origin/main`` and ``origin/dev``,
  and the dropped field was in neither — it had been deployed from an unmerged
  branch;
* step 3 compares the live ``/v1`` index's ROUTES and ``row_schema`` against the
  source, and a field nested in a response body is neither;
* step 4 runs the Worker contract tests, which assert the endpoints they know
  about rather than enumerating what production currently promises.

So the class of regression is invisible to every step, and comparing `main` and
`dev` can never catch it: the field is in neither. It is not uncommitted —
``bindome`` was committed a day earlier and pushed with an open PR, which is
precisely why it looked safe. **The only reliable record of what the API
promises is the live response**, so this guard reads production, not git.

Two modes:

``--capture`` walks a fixed probe set and writes every JSON key PATH each
endpoint returns (``deterministic_features.bindome``, ``sites[].position_frame``)
to a baseline file.

``--check`` re-walks the same probes and fails on any path that was in the
baseline and is gone. Added paths are reported and allowed — the deploy contract
is additive.

The probe set is deliberately heterogeneous, because most of these fields are
GATED and a single gene proves nothing: ``deterministic_features.library_designed_*``
appear only for library members (present on KCNN2, absent on CD63 — which is how
the first investigation of this incident briefly reached the wrong conclusion),
``position_frame`` only on a frame-mapped tag site, and the per-gene search facts
only on a gene the literature agent actually ran.

    # before deploying
    uv run python scripts/cloud/worker_shape_guard.py --capture
    # after deploying (or against a preview URL before promoting)
    uv run python scripts/cloud/worker_shape_guard.py --check
    uv run python scripts/cloud/worker_shape_guard.py --check --base <preview-url>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from accessible_surfaceome.paths import REPO_ROOT

DEFAULT_BASE = "https://api.deliverome.org/surfaceome"
BASELINE = REPO_ROOT / "cloudflare/workers/surfaceome_api/tests/live_shape_baseline.json"
# Cloudflare 403s the default urllib UA.
UA = {"user-agent": "Mozilla/5.0 (worker-shape-guard)", "accept": "application/json"}

#: Probes chosen so every GATED field has at least one endpoint that exhibits
#: it. A field that only appears for some inputs is exactly the kind a single
#: smoke probe misses, and that is how this incident went unnoticed.
PROBES: tuple[tuple[str, str], ...] = (
    ("index", "/v1"),
    # A library member: carries library_designed_structure / _topology.
    ("gene_library_member", "/v1/genes/KCNN2"),
    # A non-member deep dive: proves the member-gated keys are gated, not gone.
    ("gene_non_member", "/v1/genes/CD63"),
    # A Bindome-bearing gene: carries deterministic_features.bindome, which only
    # 1,391 of ~5,300 published proteins have. None of the other probes do, so
    # without this one the guard was blind to the very field whose loss it was
    # built to catch.
    ("gene_bindome_member", "/v1/genes/ITGBL1"),
    ("gene_evidence", "/v1/genes/CD63/evidence"),
    # Frame-mapped tag site: carries position_frame.
    ("tag_sites_frame_mapped", "/v1/tag-sites/GABRA4"),
    # Deterministic-only gene: per-gene search facts are null, not absent.
    ("tag_sites_det_only", "/v1/tag-sites/CD63"),
    ("tag_sites_rich", "/v1/tag-sites/TFRC"),
    ("internalization", "/v1/internalization/CD63"),
    ("triage", "/v1/triage/CD63"),
    ("catalog_head", "/v1/catalog"),
)

log = logging.getLogger("worker_shape_guard")


def key_paths(value: Any, prefix: str = "", *, out: set[str] | None = None) -> set[str]:
    """Every JSON key path in ``value``.

    A list contributes ``field[]`` plus the union of its elements' paths, so a
    field present on only some array elements still counts as promised — the
    alternative would let a deploy drop a field from every element but one and
    pass. Array indices are not part of the path, because element ORDER is not
    part of the contract and would make the baseline churn on every data change.
    """
    out = set() if out is None else out
    if isinstance(value, dict):
        for k, v in value.items():
            path = f"{prefix}.{k}" if prefix else k
            out.add(path)
            key_paths(v, path, out=out)
    elif isinstance(value, list):
        if prefix:
            out.add(f"{prefix}[]")
        # Cap the walk: a 5,000-row catalog has the same shape as its first few.
        for item in value[:25]:
            key_paths(item, f"{prefix}[]" if prefix else "[]", out=out)
    return out


#: Generous because ``/v1/catalog`` is ~13 MB and a cold edge miss takes well
#: over a minute. A gate that times out is a gate that gets skipped, and this
#: one treats any failed probe as "shape unknown" rather than clean — so a tight
#: timeout does not merely slow it down, it stops it answering at all.
FETCH_TIMEOUT = 300


def fetch(base: str, path: str, *, timeout: int = FETCH_TIMEOUT) -> Any:
    req = urllib.request.Request(base.rstrip("/") + path, headers=UA)  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        # The catalog is ~13 MB; the shape is in the first slice of it, but a
        # truncated read would yield invalid JSON, so it is read whole and only
        # the first array elements are walked.
        return json.loads(r.read())


def capture(base: str, *, attempts: int = 3) -> dict[str, Any]:
    """Fetch every probe and reduce each response to its key paths.

    Each probe is retried, because one unfetchable probe makes the whole run
    report "shape unknown" rather than clean — which is the right call, but it
    also means a single dropped connection stops the gate answering at all. A
    14 MB ``/v1/catalog`` over a shaky link is enough to do it, and a gate that
    cannot answer is a gate that gets skipped.
    """
    shape: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    for name, path in PROBES:
        for attempt in range(1, attempts + 1):
            try:
                shape[name] = sorted(key_paths(fetch(base, path)))
                errors.pop(name, None)
                break
            except (urllib.error.URLError, OSError, ValueError) as exc:
                errors[name] = f"{type(exc).__name__}: {exc}"
                log.error("  %-24s %s -> attempt %d/%d: %s",
                          name, path, attempt, attempts, errors[name])
                if attempt < attempts:
                    time.sleep(2 * attempt)
        if name in shape:
            log.info("  %-24s %s -> %d key path(s)", name, path, len(shape[name]))
    return {"base": base, "probes": dict(PROBES), "shape": shape, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=DEFAULT_BASE,
                    help="API base; point at a preview URL to check BEFORE promoting")
    ap.add_argument("--capture", action="store_true", help="write the baseline")
    ap.add_argument("--check", action="store_true", help="compare against the baseline")
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.capture == args.check:
        ap.error("pass exactly one of --capture / --check")

    captured = capture(args.base)
    if captured["errors"] and args.check:
        # A probe that cannot be fetched proves nothing about its shape, and
        # treating "no paths" as "no regression" is how a guard lies.
        log.error("FAIL: %d probe(s) could not be fetched; shape unknown, not clean",
                  len(captured["errors"]))
        return 1

    if args.capture:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(captured, indent=2, sort_keys=True) + "\n")
        total = sum(len(v) for v in captured["shape"].values())
        log.info("\nwrote %s (%d probes, %d key paths)",
                 args.baseline.relative_to(REPO_ROOT), len(captured["shape"]), total)
        if captured["errors"]:
            log.warning("NOTE: %d probe(s) errored and are absent from the baseline",
                        len(captured["errors"]))
        return 0

    if not args.baseline.is_file():
        log.error("no baseline at %s — run --capture first", args.baseline)
        return 1
    baseline = json.loads(args.baseline.read_text())

    dropped: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    for name, was in baseline["shape"].items():
        now = set(captured["shape"].get(name, []))
        if name not in captured["shape"]:
            dropped[name] = ["<entire probe unavailable>"]
            continue
        gone = sorted(set(was) - now)
        new = sorted(now - set(was))
        if gone:
            dropped[name] = gone
        if new:
            added[name] = new

    for name, paths in added.items():
        log.info("  + %s: %s", name, ", ".join(paths))
    if not dropped:
        log.info("\nPASS: every key path in the baseline is still served "
                 "(%d added)", sum(len(v) for v in added.values()))
        return 0

    print("\n" + "=" * 78)
    print("FAIL — the deploy DROPPED response fields the API was promising")
    print("=" * 78)
    for name, paths in dropped.items():
        print(f"\n  {name} ({dict(PROBES).get(name, '?')}):")
        for p in paths:
            print(f"    - {p}")
    print(
        "\n  A dropped field is usually another session's work: it can be live "
        "\n  and in neither main nor dev, having been deployed from an unmerged "
        "\n  branch, in which case no source comparison can see it. Find who owns "
        "\n  it before redeploying, and carry it."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
