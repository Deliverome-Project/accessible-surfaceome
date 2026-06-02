"""Enforce TS↔Pydantic schema sync for the viewer.

Walks the ``SurfaceomeRecord`` Pydantic tree, collects every model
class transitively reachable from the record, then parses
``viewer/lib/surfaceome-types.ts`` for the matching TS interfaces and
reports any field-set drift.

**Pydantic is the source of truth.** Fields the Pydantic model emits
but the TS interface doesn't declare are ERRORS — the viewer silently
drops them at runtime, so a drifted TS file masks real data. Fields
TS declares but Pydantic doesn't are warnings only — the TS file
carries Worker-payload shapes (BenchmarkRow, BenchmarkMatrix, …) and
deliberately-richer documented fields the agents don't emit yet.

Exits non-zero on any ERROR. Wired into ``scripts/check-py.sh`` so
CI / pre-commit catch drift the same place ruff + ty catch other
drift.

Run manually::

    uv run python scripts/check_viewer_types_sync.py
    uv run python scripts/check_viewer_types_sync.py --verbose

The companion task on schema drift (PR #38 follow-up list) hand-keeps
the TS file synced; this script is the tripwire that fires when
someone forgets.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
TS_TYPES_PATH = REPO_ROOT / "viewer" / "lib" / "surfaceome-types.ts"

# Pydantic class name → TS interface name when they differ. Keep small;
# the checker should mostly rely on name equality. Each entry is an
# explicit aliasing decision — comment why.
_NAME_ALIASES: dict[str, str] = {
    # Python convention: ``ECDSizeAssessment`` (acronym uppercased).
    # TS convention: ``EcdSizeAssessment`` (PascalCase).
    "ECDSizeAssessment": "EcdSizeAssessment",
    # Python ``Orthologs`` → TS ``OrthologSet``.
    "Orthologs": "OrthologSet",
    # The simpler ``CellTypeContextV1`` (used in
    # ``BiologicalContext.cell_types``) gets the unqualified TS
    # interface name because that's what the viewer card consumes.
    # The Pydantic ``CellTypeContext`` (the deeper assay-level
    # cell-identity shape used in ``AssayContext``) is skipped below
    # — the viewer doesn't render evidence rows down to that depth.
    "CellTypeContextV1": "CellTypeContext",
}

# Pydantic class names that should be SKIPPED from the check entirely.
# Used for v0.x draft shells, deep evidence-row internals the viewer
# never renders, etc.
_SKIP_CLASSES: set[str] = {
    # Draft variants — schema is identical to the final post-promotion
    # shape, no separate TS interface.
    "SurfaceomeRecordDraft",
    "SurfaceEvidenceDraft",
    "BiologicalContextDraft",
    # Assay-level cell-type identity (lives inside ``AssayContext``).
    # The viewer renders the simpler ``CellTypeContextV1`` shape that
    # ``BiologicalContext.cell_types`` carries; never reaches into the
    # per-evidence-row assay context.
    "CellTypeContext",
    # Audit-only ledger metadata attached to each Evidence row. The
    # viewer's EvidenceDrawer reads the top-level ``Evidence`` fields
    # + ``EvidenceSpan`` content; everything inside AssayContext
    # (cell type at assay time, species inferred, etc.) is filtered
    # out by intent — these were emitted for downstream re-analysis,
    # not for the per-gene page.
    "AssayContext",
}

# Per-class Pydantic fields the viewer DELIBERATELY doesn't render —
# audit-only provenance, computed counts, internal validation flags.
# Adding a field here is a design decision: \"this is for the JSON
# audit reader, not the viewer.\" Each entry is one explicit field
# the checker treats as if it WERE declared in TS.
_INTENTIONALLY_PYDANTIC_ONLY: dict[str, set[str]] = {
    # Audit / provenance hashes + timestamps. Not surfaced to the
    # human reader; lives in the JSON for downstream re-analysis +
    # tamper detection.
    "SourceRef": {
        "content_sha256",
        "retrieved_at",
        "retraction_checked_at",
    },
    # Evidence-row internals the viewer doesn't render — the per-
    # evidence audit trail. Surfaced by the JSON export, not the
    # per-gene page. ``assay_context`` deep-nests into another whole
    # tree (see _SKIP_CLASSES above).
    "Evidence": {
        "assay_context",
        "direction",
        "entailment_audit_passed",
        "evidence_type",
        "validation_warnings",
    },
    # SearchEntry tail-fields used by the audit log only — the viewer
    # shows just the query string in the search log.
    "SearchEntry": {
        "contributed_evidence_ids",
        "mode",
        "n_results",
        "retrieved_at",
        "sources_seen",
        "tool",
    },
    # Counts derivable client-side from ``rec.evidence``. Viewer
    # computes these inline (see ``GeneHeader.tierCounts``).
    "SurfaceomeRecord": {
        "evidence_count",
        "primary_evidence_count",
        "secondary_evidence_count",
    },
}


def _walk_pydantic_tree(
    root: type[BaseModel],
    out: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    """Return ``{class_name: {field_name, ...}}`` for every Pydantic
    model transitively reachable from ``root`` through ``model_fields``."""
    if out is None:
        out = {}
    if root.__name__ in out or root.__name__ in _SKIP_CLASSES:
        return out
    out[root.__name__] = set(root.model_fields.keys())
    for finfo in root.model_fields.values():
        for nested in _unwrap_model_types(finfo.annotation):
            _walk_pydantic_tree(nested, out)
    return out


def _unwrap_model_types(annotation: object) -> list[type[BaseModel]]:
    """Yield every Pydantic-BaseModel subclass inside an annotation.

    Handles ``Optional[X]``, ``Union[X, None]``, ``list[X]``,
    ``dict[K, X]``, generics, etc. Non-model types (str, int, Literal,
    enum types) are ignored.
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    origin = get_origin(annotation)
    if origin is None:
        return []
    out: list[type[BaseModel]] = []
    for arg in get_args(annotation):
        out.extend(_unwrap_model_types(arg))
    return out


# Regex parsing of the TS file. The grammar we care about is narrow:
# ``export interface Name {\n  field: Type;\n  field2?: Type2;\n  ...\n}``
# — no inline-object types we need to descend into for this check.

_INTERFACE_HEADER_RE = re.compile(
    r"^export\s+interface\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b[^{]*\{"
)
_FIELD_RE = re.compile(
    # name, optional `?`, `:`, type (we don't capture the type — only
    # the name matters for field-presence checking).
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\??\s*:"
)


def _parse_ts_interfaces(text: str) -> dict[str, set[str]]:
    """Extract ``{interface_name: {field_name, ...}}`` from a TS file."""
    out: dict[str, set[str]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _INTERFACE_HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group("name")
        fields: set[str] = set()
        # Walk forward to the matching closing brace, tracking depth so
        # nested object types inside a single interface don't confuse
        # the field extractor.
        depth = lines[i].count("{") - lines[i].count("}")
        j = i + 1
        while j < len(lines) and depth > 0:
            line = lines[j]
            # Field detection only fires at top depth (== 1). Below
            # that we're inside a nested object literal.
            if depth == 1:
                stripped = line.lstrip()
                if stripped and not stripped.startswith(("//", "/*", "*")):
                    fm = _FIELD_RE.match(line)
                    if fm:
                        fields.add(fm.group("name"))
            depth += line.count("{") - line.count("}")
            j += 1
        out[name] = fields
        i = j
    return out


def _compare(
    pyd: dict[str, set[str]],
    ts: dict[str, set[str]],
    *,
    verbose: bool,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings).

    Errors = Pydantic field with no TS counterpart (viewer silently
    drops). Warnings = TS field with no Pydantic counterpart (worker
    payload or speculative shape — fine).
    """
    errors: list[str] = []
    warnings: list[str] = []
    for py_name, py_fields in sorted(pyd.items()):
        ts_name = _NAME_ALIASES.get(py_name, py_name)
        if ts_name not in ts:
            errors.append(
                f"[MISSING TS INTERFACE] Pydantic {py_name!r} "
                f"(expected TS interface {ts_name!r}) — viewer can't render this shape"
            )
            continue
        ts_fields = ts[ts_name]
        # Fields the viewer deliberately doesn't render (audit-only,
        # provenance, derived counts) count as \"covered\" for sync
        # purposes — adding them to _INTENTIONALLY_PYDANTIC_ONLY is
        # the explicit declaration.
        intentional = _INTENTIONALLY_PYDANTIC_ONLY.get(py_name, set())
        missing_in_ts = py_fields - ts_fields - intentional
        extra_in_ts = ts_fields - py_fields
        if missing_in_ts:
            for f in sorted(missing_in_ts):
                errors.append(
                    f"[DRIFT] {py_name}.{f} — emitted by Pydantic, "
                    f"absent from TS interface {ts_name} (viewer silently drops it)"
                )
        if extra_in_ts and verbose:
            for f in sorted(extra_in_ts):
                warnings.append(
                    f"[TS-ONLY] {ts_name}.{f} — declared in TS, "
                    f"not in Pydantic {py_name} (worker payload? add to "
                    f"{py_name} or remove from TS)"
                )
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verbose", action="store_true",
        help="Also report TS fields absent from Pydantic (warnings; "
             "they don't fail the check).",
    )
    args = ap.parse_args()

    pyd = _walk_pydantic_tree(SurfaceomeRecord)
    ts_text = TS_TYPES_PATH.read_text()
    ts = _parse_ts_interfaces(ts_text)

    errors, warnings = _compare(pyd, ts, verbose=args.verbose)

    if warnings:
        print("WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)
        print(file=sys.stderr)

    if errors:
        print("ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        print(
            f"\n{len(errors)} drift error{'s' if len(errors) != 1 else ''} "
            f"between Pydantic ({len(pyd)} models walked) and TS "
            f"({TS_TYPES_PATH.relative_to(REPO_ROOT)}).\n"
            f"Fix: update the TS interfaces to mirror Pydantic. "
            f"Pydantic is the source of truth — the viewer reads JSON "
            f"the Pydantic schema validated, so missing TS fields are "
            f"data the viewer silently throws away.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK — TS interfaces cover all {sum(len(f) for f in pyd.values())} "
        f"fields across {len(pyd)} Pydantic models reachable from "
        f"SurfaceomeRecord."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
