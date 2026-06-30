"""Catch broken-shape public-D1 records before they crash the Pages deploy.

Failure mode this guards against
================================

Cloudflare Pages SSG iterates every gene in ``surface_annotation`` via
``generateStaticParams`` and the viewer's ``[symbol]/page.tsx``. If a
record predates the current schema (no ``deterministic_features``, no
``surface_bind`` block, etc.), the page renderer throws::

    TypeError: Cannot read properties of undefined (reading 'surface_bind')

The build then exits non-zero and Pages keeps serving the previous
deploy — production silently freezes.

Why hand-listed gene drift tests didn't catch it
================================================

``tests/test_worker_response_shape.py`` already calls
``SurfaceomeRecord.model_validate`` per gene, but only on a hand-curated
4-gene list (EGFR, SRC, GPR75, HSPA5). Any broken record outside that
list slips through. We hit this exact failure with ``OLDREC`` (0.5.0),
``FAKE3`` (1.0.0), then ``FAKE1`` (1.1.0) in three consecutive deploys.

This test enumerates **every** row in public D1 ``surface_annotation``
— no allowlist to update — and verifies each one carries the specific
fields the v2.x viewer page renderer hard-dereferences. Any new broken
record fails CI on the PR that introduced it, not three deploys later.

Why not full ``SurfaceomeRecord.model_validate`` here
====================================================

Strict Pydantic over-fires on legacy v1.x records: they carry removed
fields like ``cell_states`` (merged into ``accessibility_modulation`` in
2.5.0) that Pydantic's ``extra='forbid'`` rejects, but the viewer reads
specific fields only and renders these legacy records cleanly. We
care about renderer-crashing drift, not historical-shape drift —
matching the renderer's actual access pattern is what catches the
right thing.

When the renderer starts dereferencing a new field, extend
``REQUIRED_PATHS``. Drift in the other direction (a field the renderer
stops touching) just leaves a dead entry — harmless but worth pruning.

Skipping rules
==============

Skips when the public-D1 credentials aren't in the environment. Local
``pytest -q`` runs without ``.env`` will skip; CI runs that wire the
secrets into ``ci.yml`` enforce the check.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Paths the v2.x viewer page renderer (viewer/app/[symbol]/page.tsx and
# its child cards) hard-dereferences. Each tuple is a chain of keys; the
# leaf must be neither missing nor ``None``. Verified by reading the
# Page.tsx exports + the failure traces from the 2026-06-07 deploys.
REQUIRED_PATHS: tuple[tuple[str, ...], ...] = (
    # Root-level — the renderer pulls these straight off the record.
    ("schema_version",),
    ("gene",),
    ("executive_summary",),
    ("filters",),
    ("surface_evidence",),
    ("biological_context",),
    ("deterministic_features",),
    ("accessibility_risks",),
    # The exact crash we've now hit 3× in a row. The renderer does
    # `rec.deterministic_features.surface_bind.has_data` with NO defensive
    # `?.` chain (per CLAUDE.md). If surface_bind is missing the whole
    # SSG dies, so this nested path needs its own assertion.
    ("deterministic_features", "surface_bind"),
)


def _public_d1_creds_available() -> bool:
    """Mirror the env-var set ``D1Config.from_env_public`` reads."""
    # Try to load .env if present (no-op in CI, where env is injected).
    try:
        from accessible_surfaceome.env import load_env

        load_env()
    except Exception:  # noqa: BLE001 — best-effort
        pass
    required = (
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
    )
    return all(os.environ.get(k) for k in required)


def _missing_required_paths(rec: dict) -> list[str]:
    """Return human-readable descriptions of every REQUIRED_PATH that is
    either absent or has a ``None`` leaf in ``rec``. Empty list = OK."""
    out: list[str] = []
    for path in REQUIRED_PATHS:
        cur = rec
        for i, k in enumerate(path):
            if not isinstance(cur, dict) or k not in cur:
                out.append(f"missing {'.'.join(path[: i + 1])}")
                break
            cur = cur[k]
        else:
            if cur is None:
                out.append(f"{'.'.join(path)} is None")
    return out


def test_every_published_record_carries_renderer_required_fields() -> None:
    """Every row in public ``surface_annotation`` must carry the fields
    the v2.x viewer page renderer dereferences without a defensive ``?.``
    chain.

    Failure surfaces the offending ``(gene_symbol, schema_version)``
    tuples plus the specific missing path(s), so the operator can decide
    whether to drop the row, re-annotate it, or extend the renderer's
    defensive coverage.
    """
    if not _public_d1_creds_available():
        pytest.skip(
            "Public-D1 creds absent (CLOUDFLARE_API_TOKEN / _ACCOUNT_ID / "
            "_D1_SURFACEOME_PUBLIC_ID) — wire them in CI to enforce the "
            "shape guard. See .github/workflows/ci.yml for the env block."
        )

    from accessible_surfaceome.cloud.d1_client import D1Client, D1Config

    with D1Client(D1Config.from_env_public()) as pub:
        rows = pub.query(
            "SELECT gene_symbol, schema_version, annotation_json "
            "FROM surface_annotation ORDER BY gene_symbol;"
        )

    assert rows, (
        "No published records in public-D1 surface_annotation — either the "
        "table was wiped, or the credentials point at the wrong DB."
    )

    failures: list[tuple[str, str, list[str]]] = []
    for r in rows:
        sym = r["gene_symbol"]
        sv = r["schema_version"]
        try:
            rec = json.loads(r["annotation_json"])
        except Exception as e:  # noqa: BLE001
            failures.append((sym, sv, [f"annotation_json is not valid JSON: {e}"]))
            continue
        missing = _missing_required_paths(rec)
        if missing:
            failures.append((sym, sv, missing))

    if failures:
        lines = [
            f"{len(failures)} record(s) in public-D1 surface_annotation would",
            "crash the Cloudflare Pages SSG build (missing fields the v2.x",
            "viewer page renderer hard-dereferences):",
            "",
        ]
        for sym, sv, missing in failures:
            lines.append(f"  • {sym}  (schema_version={sv}):")
            for m in missing:
                lines.append(f"      – {m}")
            lines.append("")
        lines.append(
            "Drop the row from D1 (if it's a test fixture) OR re-annotate "
            "at the current schema. Do NOT add defensive `?.` chains in "
            "the viewer (see CLAUDE.md → 'Records source of truth')."
        )
        pytest.fail("\n".join(lines))


# --------------------------------------------------------------------------- #
# Markdown-export drift guard
# --------------------------------------------------------------------------- #
#
# `viewer/scripts/build-markdown-exports.mjs` renders every committed
# `viewer/public/data/surfaceome/{symbol}.json` snapshot to a matching
# `.md` deliverable (the downloadable brief on each gene page). The
# exporter handles schema v1.x and v2.x snapshots; committed JSON without
# a matching non-empty `.md` is drift.
#
# This test makes both halves loud: every committed snapshot must render,
# and every D1-published row should eventually have a committed snapshot.
# Repo root is two levels up from tests/ — same heuristic as
# scripts/check_viewer_types_sync.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_VIEWER_DATA_DIR = _REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

# Exemption list for ``test_every_in_tree_record_has_markdown_export``: committed
# in-tree snapshots whose ``.md`` the exporter can't yet render (e.g. an
# unsupported schema). Empty today — every committed snapshot has its brief.
# (It previously also exempted D1-published genes that lacked a snapshot, but
# the deep-dive rollout publishes thousands of genes to public D1 and no longer
# requires a committed snapshot per D1 gene — see
# ``test_committed_snapshots_have_live_d1_records``.)
KNOWN_NO_MARKDOWN_EXPORT: frozenset[str] = frozenset()


def test_every_in_tree_record_has_markdown_export() -> None:
    """Every committed ``viewer/public/data/surfaceome/{symbol}.json``
    must have a non-empty matching ``{symbol}.md`` rendered from it by
    ``viewer/scripts/build-markdown-exports.mjs``.

    This is the local-only half of the markdown-drift guard — it runs in
    CI WITHOUT needing the public-D1 credentials (the in-tree snapshots
    are the exporter's actual input). The D1 side (every published gene
    should have an in-tree snapshot+md) is a separate concern; tracked
    in ``KNOWN_NO_MARKDOWN_EXPORT`` so the gap is visible without
    blocking offline builds.

    Failures surface (a) in-tree JSONs whose .md is missing/empty AND
    (b) allowlist entries that are no longer needed (so the list can't
    silently rot).
    """
    if not _VIEWER_DATA_DIR.is_dir():
        pytest.skip(f"viewer snapshot dir not present at {_VIEWER_DATA_DIR}")

    json_files = sorted(_VIEWER_DATA_DIR.glob("*.json"))
    if not json_files:
        pytest.skip(
            f"No in-tree JSON snapshots at {_VIEWER_DATA_DIR} — "
            "build-markdown-exports.mjs has nothing to render."
        )

    actually_missing: list[tuple[str, str]] = []
    no_longer_missing: list[str] = []
    for j in json_files:
        sym = j.stem
        try:
            sv = str(json.loads(j.read_text()).get("schema_version") or "?")
        except Exception:  # noqa: BLE001
            sv = "?"
        md = j.with_suffix(".md")
        present_and_nonempty = md.is_file() and md.stat().st_size > 0
        in_allowlist = sym in KNOWN_NO_MARKDOWN_EXPORT
        if not present_and_nonempty and not in_allowlist:
            actually_missing.append((sym, sv))
        elif present_and_nonempty and in_allowlist:
            no_longer_missing.append(sym)

    problems: list[str] = []
    if actually_missing:
        problems.append("In-tree snapshots missing a matching .md export:")
        for sym, sv in actually_missing:
            problems.append(f"  • {sym}.json  (schema_version={sv})")
        problems.append("")
        problems.append(
            "Either re-run `cd viewer && npm run build:exports` and commit "
            "the resulting .md, OR (if the exporter can't yet handle that "
            "schema version) add the symbol to KNOWN_NO_MARKDOWN_EXPORT "
            "in this file with a tracking note."
        )
    if no_longer_missing:
        if problems:
            problems.append("")
        problems.append(
            "Allowlist has stale entries (markdown export EXISTS now, "
            "remove from KNOWN_NO_MARKDOWN_EXPORT):"
        )
        for sym in no_longer_missing:
            problems.append(f"  • {sym}")
    if problems:
        pytest.fail("\n".join(problems))


def test_committed_snapshots_have_live_d1_records() -> None:
    """Every committed in-tree snapshot must correspond to a published record in
    public D1 — catches a stale / orphan snapshot (committed but never published,
    or left behind after its D1 row was removed or replaced).

    The reverse — every D1-published gene having a committed snapshot — is
    deliberately NOT enforced. The deep-dive rollout publishes thousands of genes
    to public D1, which the viewer serves directly from D1 (its primary path);
    committing a snapshot + ``.md`` for each would bloat the repo and doesn't
    scale. Committed snapshots are a curated subset (showcase + validation genes)
    kept for the viewer's offline fallback + downloadable briefs. The
    snapshot → ``.md`` half is covered by
    ``test_every_in_tree_record_has_markdown_export``.

    Skips when the public-D1 secrets aren't available (need CLOUDFLARE_API_TOKEN
    + _ACCOUNT_ID + _D1_SURFACEOME_PUBLIC_ID).
    """
    if not _public_d1_creds_available():
        pytest.skip("Public-D1 creds absent.")
    if not _VIEWER_DATA_DIR.is_dir():
        pytest.skip(f"viewer snapshot dir not present at {_VIEWER_DATA_DIR}")

    snapshots = sorted(
        p.stem for p in _VIEWER_DATA_DIR.glob("*.json") if p.stat().st_size > 0
    )
    if not snapshots:
        pytest.skip("No committed snapshots to check.")

    from accessible_surfaceome.cloud.d1_client import D1Client, D1Config

    with D1Client(D1Config.from_env_public()) as pub:
        d1_genes = {
            r["gene_symbol"]
            for r in pub.query("SELECT gene_symbol FROM surface_annotation;")
        }
    assert d1_genes, "No published records in public-D1 surface_annotation."

    orphan = [s for s in snapshots if s not in d1_genes]
    assert not orphan, (
        "Committed in-tree snapshots with NO public-D1 record (stale / orphan). "
        "Either publish them — `uv run python "
        "scripts/upload_viewer_snapshots_to_d1.py --execute` — or remove the "
        f"snapshot + .md: {orphan}"
    )
