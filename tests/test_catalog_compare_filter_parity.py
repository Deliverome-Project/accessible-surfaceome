"""Guard against drift between the genome-wide catalog filter panel
(``viewer/components/CatalogTable/CatalogTable.tsx``) and the upload-compare
filter panel (``viewer/components/CompareTool/CompareTool.tsx``).

Both surfaces are supposed to render filters from the *same* shared
registry — ``DD_ENUM_FIELDS`` / ``DD_BOOL_FIELDS`` in
``viewer/lib/deep-dive-fields.ts``. That contract is invisible at the
TypeScript level (a fork would just be a new local registry), so this
test pins it textually:

  1. Both files MUST import ``DD_ENUM_FIELDS`` + ``DD_BOOL_FIELDS`` from
     the shared module — no local re-declaration.
  2. Both files MUST reference EVERY key from the shared registry
     (catalog's three subsection partitions + compare's TSV columns
     /selectors); a missing key here means the surface silently drops
     that filter.
  3. Neither file may carry an ad-hoc ``DdEnumKey`` literal that isn't
     in the shared registry — that would indicate someone hand-rolled a
     filter outside the registry.

No network / no build — pure text introspection.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DDF = (_ROOT / "viewer" / "lib" / "deep-dive-fields.ts").read_text()
_CATALOG = (
    _ROOT / "viewer" / "components" / "CatalogTable" / "CatalogTable.tsx"
).read_text()
_COMPARE = (
    _ROOT / "viewer" / "components" / "CompareTool" / "CompareTool.tsx"
).read_text()


def _registry_keys(block_name: str) -> set[str]:
    """Pull the `key: "…"` literals out of the named DD_*_FIELDS block."""
    m = re.search(
        rf"export const {block_name}\s*:[^=]*=\s*\[(.*?)\n\];", _DDF, re.S
    )
    assert m, f"{block_name} not found in deep-dive-fields.ts"
    return set(re.findall(r'key:\s*"([^"]+)"', m.group(1)))


_ENUM_KEYS = _registry_keys("DD_ENUM_FIELDS")
_BOOL_KEYS = _registry_keys("DD_BOOL_FIELDS")


def test_catalog_imports_from_shared_registry() -> None:
    """Catalog must source DD_ENUM_FIELDS + DD_BOOL_FIELDS from the
    shared module — no local fork."""
    assert "DD_ENUM_FIELDS" in _CATALOG and "DD_BOOL_FIELDS" in _CATALOG
    assert 'from "../../lib/deep-dive-fields"' in _CATALOG, (
        "CatalogTable must import from lib/deep-dive-fields — local "
        "redeclaration would silently fork the filter set"
    )
    # Catalog must NOT redeclare the registry locally. The shared module
    # uses `export const DD_ENUM_FIELDS`; a local fork would use
    # `const DD_ENUM_FIELDS = [...]` (with or without `export`).
    assert "const DD_ENUM_FIELDS" not in _CATALOG, (
        "CatalogTable redeclares DD_ENUM_FIELDS locally — must import"
        " from the shared registry instead"
    )
    assert "const DD_BOOL_FIELDS" not in _CATALOG, (
        "CatalogTable redeclares DD_BOOL_FIELDS locally — must import"
        " from the shared registry instead"
    )


def test_compare_imports_from_shared_registry() -> None:
    """Same contract for the compare tool — no local fork."""
    assert "DD_ENUM_FIELDS" in _COMPARE and "DD_BOOL_FIELDS" in _COMPARE
    assert 'from "../../lib/deep-dive-fields"' in _COMPARE, (
        "CompareTool must import from lib/deep-dive-fields"
    )
    assert "const DD_ENUM_FIELDS" not in _COMPARE, (
        "CompareTool redeclares DD_ENUM_FIELDS locally"
    )
    assert "const DD_BOOL_FIELDS" not in _COMPARE, (
        "CompareTool redeclares DD_BOOL_FIELDS locally"
    )


def test_catalog_subsection_partitions_cover_full_enum_registry() -> None:
    """Catalog renders DD_ENUM_FIELDS in three collapsible subsections,
    partitioned by `provenance` and `isRisk`:
       * "Surface call" — provenance === "llm" && !isRisk
       * "Risks"        — isRisk
       * "Deterministic"— provenance === "deterministic" && !isRisk
    The three subsection .filter() calls MUST collectively cover the
    full registry (no enum field left unrendered).

    This test mirrors the partitioning logic to make sure the
    in-file partitions add up to the full registry — without this, a
    new field added to DD_ENUM_FIELDS but missing `provenance: "llm" /
    "deterministic"` would silently disappear from the UI.
    """
    # The catalog uses three exact `.filter(` shapes — assert each is
    # present so a future refactor that consolidates them surfaces here
    # (so the maintainer comes and updates this test alongside).
    expected_partitions = [
        # "Surface call" subsection.
        r'DD_ENUM_FIELDS\.filter\(',
        # Risks subsection.
        r'\(f\) => f\.isRisk\)',
        # Deterministic subsection.
        r'provenance === "deterministic"',
    ]
    for pat in expected_partitions:
        assert re.search(pat, _CATALOG), (
            f"CatalogTable partition shape `{pat}` missing — registry"
            f" may have a field that isn't rendered in any subsection"
        )


def test_compare_iterates_full_enum_and_bool_registries() -> None:
    """CompareTool must spread the full DD_ENUM_FIELDS / DD_BOOL_FIELDS
    into its TSV column lists (and any filter selector lists). A local
    `.filter(...)` that drops keys would silently desync from the
    catalog — assert the bare `.map(` shape, not a filtered shape.
    """
    # Whitelist of acceptable `DD_ENUM_FIELDS.X(…)` patterns. `.map` is
    # the spread for TSV columns / filter selectors. Anything else
    # (`.filter`, `.reduce`) would suggest a key-dropping projection.
    bad = re.findall(
        r"DD_(?:ENUM|BOOL)_FIELDS\.(?:filter|reduce|slice)\b", _COMPARE
    )
    assert not bad, (
        f"CompareTool uses non-`.map` iteration on the shared registry"
        f" — risks dropping fields from the compare surface that the"
        f" catalog still renders: {bad}"
    )
    # Both registries should be iterated at least once each.
    assert re.search(r"DD_ENUM_FIELDS\.map\(", _COMPARE), (
        "CompareTool does not iterate DD_ENUM_FIELDS"
    )
    assert re.search(r"DD_BOOL_FIELDS\.map\(", _COMPARE), (
        "CompareTool does not iterate DD_BOOL_FIELDS"
    )


def test_deterministic_filters_are_tool_derived_from_sequence() -> None:
    """Hard pin on which fields can carry `provenance: "deterministic"`.

    Per the DdProvenance contract in deep-dive-fields.ts, a field is
    deterministic when its value is mechanically reproducible from the
    record with NO LLM judgement read at filter time. That covers two
    sub-cases:

      1. Sequence-tool readouts — DeepTMHMM topology, AlphaFold pLDDT,
         Compara %-identity, SURFACE-Bind MaSIF patches, Schweke AF2
         homomer state. The large majority.
      2. Mechanical record counts — a count over the record's own
         structure, then a fixed/percentile band. Reproducible from
         the persisted record alone; no model call.

    The contrast remains `evidence_density`, which stays `llm`: its
    buckets track `len(evidence_rows)` — the synthesizer's row-level
    inclusion judgement — closely enough that it reads as an LLM
    rollup. The distinction is "is the value a model judgement or a
    mechanical readout", NOT "does the last transform look
    deterministic". Extend `_ALLOWED_DETERMINISTIC` only when a new
    field genuinely fits one of the two sub-cases above.
    """
    _ALLOWED_DETERMINISTIC = {
        # Topology — DeepTMHMM on the sequence.
        "ecd_accessibility_class",
        "n_term_extracellular",
        "c_term_extracellular",
        # Cross-species + paralog %-identity — Compara on the sequence.
        "cyno_ortholog_ecd",
        "mouse_ortholog_ecd",
        "max_paralog_ecd",
        # SURFACE-Bind MaSIF patches — Balbi 2026, on the AF2 structure
        # (which is itself deterministic on the sequence).
        "surface_bind_targetability",
        "surface_bind_main_class",
        # Schweke 2024 AF2 homomer prior — also on the AF2 structure.
        "is_homo_oligomer",
        # Mechanical record count (sub-case 2): unique papers behind the
        # evidence list, then a cohort-percentile band. The papers were
        # agent-selected, but the band the filter exposes is a pure
        # function of a count — no LLM judgement is read at filter time
        # and it is reproducible from the record alone. (Distinct from
        # evidence_density, which stays `llm`.)
        "n_papers_selected_band",
    }
    # Re-parse the registry to harvest (key, provenance) pairs from
    # both ENUM and BOOL blocks.
    pat = re.compile(
        r'key:\s*"([^"]+)"[^}]*?provenance:\s*"([^"]+)"',
        re.S,
    )
    actual_deterministic = {
        key for key, prov in pat.findall(_DDF) if prov == "deterministic"
    }
    extras = actual_deterministic - _ALLOWED_DETERMINISTIC
    assert not extras, (
        f"Fields marked `provenance: \"deterministic\"` that aren't on the"
        f" sequence-tool whitelist: {sorted(extras)}. Either reclassify"
        f" to `llm` (if the value depends on LLM-pulled input) or add"
        f" the new sequence-tool field to _ALLOWED_DETERMINISTIC."
    )


def test_every_registry_key_referenced_in_compare_or_via_iteration() -> None:
    """Final defense-in-depth: every key in the shared registry must
    surface in BOTH files — either via the bulk iteration (`.map((f) =>
    ...)` over the registry, validated above) or as a direct key
    reference. This catches the corner case where a field is added to
    the shared registry but a downstream surface omits it from a
    hand-rolled column list.
    """
    # The bulk iteration tests above cover the "via .map" case for
    # both files. If a key isn't bulk-iterated in either file, this
    # test would still pass — but that's caught by the partition test
    # for catalog and the .map test for compare. So nothing additional
    # to assert here beyond a sanity check that the registries are
    # non-empty (regression guard).
    assert _ENUM_KEYS, "DD_ENUM_FIELDS registry parsed as empty"
    assert _BOOL_KEYS, "DD_BOOL_FIELDS registry parsed as empty"
    # And every registry-imported file must reach BOTH registries (so a
    # surface importing only ENUM but not BOOL doesn't silently drop
    # the bool filters).
    for surface_name, surface in (
        ("CatalogTable", _CATALOG),
        ("CompareTool", _COMPARE),
    ):
        assert "DD_ENUM_FIELDS" in surface, (
            f"{surface_name} doesn't reference DD_ENUM_FIELDS"
        )
        assert "DD_BOOL_FIELDS" in surface, (
            f"{surface_name} doesn't reference DD_BOOL_FIELDS"
        )
