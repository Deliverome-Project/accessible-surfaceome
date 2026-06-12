#!/usr/bin/env python3
"""Embed CZI CellxGene enrichment into the per-gene viewer JSON + MD.

For every deep-dive snapshot under ``viewer/public/data/surfaceome/{SYMBOL}.json``,
look up the matching cellxgene record from D1 (or the local
``/tmp/czi_enrichment/`` cache if D1 is unreachable / not configured)
and:

  1. **JSON:** add a top-level ``"cellxgene"`` key holding the entire
     v2.1.1 enrichment payload (cell_class_enrichment, cell_type_enrichment,
     tissue_enrichment, top_cell_types, top_tissues, etc.). Downstream
     readers get the canonical CZI data alongside the surface-annotation
     fields without a second fetch.

  2. **MD:** append a ``## CellxGene RNA enrichment (CZI Census)``
     section summarizing the three classification axes + top 5 cell
     types + top 5 tissues. Idempotent — if the section already exists,
     it's replaced.

Usage::

    # Default: embed for every {SYMBOL}.json present in viewer/public/data/surfaceome/
    uv run python scripts/embed_cellxgene_into_records.py

    # Restrict to one gene
    uv run python scripts/embed_cellxgene_into_records.py --gene EGFR

    # Source from a different cellxgene snapshot dir
    uv run python scripts/embed_cellxgene_into_records.py \
        --cellxgene-dir /tmp/czi_enrichment_v2_1_test

    # Dry-run (print what would change, write nothing)
    uv run python scripts/embed_cellxgene_into_records.py --dry-run

After running, re-sync the viewer JSON snapshots to D1 via the standard
``scripts/upload_viewer_snapshots_to_d1.py --execute`` so the public Worker
serves the augmented record. The cellxgene field is small (~3-10 KB per
gene), well within D1's per-row budget.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO / "viewer" / "public" / "data" / "surfaceome"
DEFAULT_CX_DIR = Path("/tmp/czi_enrichment")

CX_SECTION_MARKER = "## CellxGene RNA enrichment (CZI Census)"
CX_SECTION_END_MARKER = "<!-- /cellxgene -->"


# ---------- MD builders ----------


def _fmt_fold(fold: float | None, infinite: bool) -> str:
    if infinite:
        return "∞×"
    if fold is None:
        return ""
    if fold >= 100:
        return f"{fold:.0f}×"
    return f"{fold:.1f}×"


def _fmt_class_chip(klass: str, entities: list[str], fold: str, tau: float | None = None) -> str:
    """`enriched · Prostate gland · 12.3× · τ=0.97` — chip text."""
    parts = [klass.replace("_", " ")]
    if entities:
        parts.append(" · ".join(entities[:3]))
    if fold:
        parts.append(fold)
    if tau is not None:
        parts.append(f"τ={tau:.2f}")
    return " · ".join(parts)


def build_cellxgene_md_section(cx: dict) -> str:
    """Render the cellxgene record as a markdown section. Self-contained:
    classification chips + top 5 cell types + top 5 tissues + provenance
    line."""
    cc = cx.get("cell_class_enrichment") or {}
    ct = cx.get("cell_type_enrichment") or {}
    ti = cx.get("tissue_enrichment") or {}

    # Resolve leaf CL IDs to human labels via top_cell_types
    cl_to_name = {r["cl_id"]: r["cell_type"] for r in cx.get("top_cell_types", [])}

    def _ent_strings(klass: str, ids: list, label_lookup: dict | None = None) -> list[str]:
        if not ids:
            return []
        if label_lookup is not None:
            return [label_lookup.get(i, i) for i in ids]
        return list(ids)

    chip_lines = []
    if cc.get("class"):
        labels = cc.get("class_labels") or cc.get("class_ids") or []
        chip_lines.append(
            f"- **Cell class (CL ontology graph, ~10 compartments):** "
            f"{_fmt_class_chip(cc['class'], labels, _fmt_fold(cc.get('fold_change'), cc.get('fold_change_infinite', False)), cc.get('tau'))}"
        )
    if ct.get("class"):
        ents = _ent_strings(ct["class"], ct.get("cl_ids", []), cl_to_name)
        chip_lines.append(
            f"- **Cell type (leaf Cell Ontology terms, ~600):** "
            f"{_fmt_class_chip(ct['class'], ents, _fmt_fold(ct.get('fold_change'), ct.get('fold_change_infinite', False)), ct.get('tau'))}"
        )
    if ti.get("class"):
        labels = ti.get("tissue_labels") or ti.get("uberon_ids", []) or []
        chip_lines.append(
            f"- **Tissue (UBERON terms, ~56):** "
            f"{_fmt_class_chip(ti['class'], labels, _fmt_fold(ti.get('fold_change'), ti.get('fold_change_infinite', False)), ti.get('tau'))}"
        )

    def _row(r: dict, label_key: str, id_key: str) -> str:
        mean = r.get("mean_log1p_cp10k") or 0
        pct = (r.get("pct_expressing") or 0) * 100
        n_exp = r.get("n_expressing") or 0
        n_tot = r.get("n_total") or 0
        trace = " (trace)" if r.get("is_trace") else ""
        return f"| {r.get(label_key, '?')} | {r.get(id_key, '')} | {mean:.3f} | {pct:.2f}% | {n_exp:,} / {n_tot:,} |{trace}"

    cell_rows = [_row(r, "cell_type", "cl_id") for r in cx.get("top_cell_types", [])[:5]]
    tissue_rows = [_row(r, "tissue", "uberon_id") for r in cx.get("top_tissues", [])[:5]]

    schema = cx.get("schema_version", "?")
    census = cx.get("census_version", "?")

    parts = [
        CX_SECTION_MARKER,
        "",
        f"*Schema v{schema} · CZI Census {census} · "
        "τ-cutoff classification (Yanai 2005) on linear population mean "
        "(mean × pct, ≈ nTPM): τ≥0.85 enriched, 0.5–0.85 enhanced, <0.5 "
        "low specificity, no eligibles not detected. Cell ontology graph "
        "(cl-basic.obo) walked to ~150 cell-family terms; UBERON ontology "
        "walked to ~150 organ-level tissues. Cutoffs follow HPA's tissue-"
        "specificity nTPM convention. CC-BY 4.0 (CZI Census).*",
        "",
        "**Classification:**",
        "",
        "\n".join(chip_lines) if chip_lines else "_no classification — record missing all three axes_",
        "",
        "**Top 5 cell types (leaf CL, pooled across tissues):**",
        "",
        "| Cell type | CL ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |",
        "|---|---|---|---|---|",
        "\n".join(cell_rows) if cell_rows else "| _none_ | | | | |",
        "",
        "**Top 5 tissues (UBERON, pooled across cell types):**",
        "",
        "| Tissue | UBERON ID | Mean log1p(CP10K) | % expressing | n_expressing / n_total |",
        "|---|---|---|---|---|",
        "\n".join(tissue_rows) if tissue_rows else "| _none_ | | | | |",
        "",
        CX_SECTION_END_MARKER,
    ]
    return "\n".join(parts)


def merge_md_section(md_text: str, section: str) -> str:
    """Append OR replace the cellxgene section in an existing MD. Idempotent.

    If the markers already exist, swap the whole block (so a re-run after a
    new cellxgene rebuild updates without leaving the old block behind).
    Otherwise append at the end."""
    if CX_SECTION_MARKER in md_text and CX_SECTION_END_MARKER in md_text:
        start = md_text.index(CX_SECTION_MARKER)
        end = md_text.index(CX_SECTION_END_MARKER) + len(CX_SECTION_END_MARKER)
        return md_text[:start] + section + md_text[end:]
    if not md_text.endswith("\n"):
        md_text += "\n"
    return md_text + "\n" + section + "\n"


# ---------- Main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene", help="Restrict to one gene symbol (default: all snapshots)")
    ap.add_argument(
        "--cellxgene-dir",
        type=Path,
        default=DEFAULT_CX_DIR,
        help=f"Source dir for {{SYMBOL}}.json cellxgene snapshots (default: {DEFAULT_CX_DIR})",
    )
    ap.add_argument(
        "--snapshot-dir",
        type=Path,
        default=SNAPSHOT_DIR,
        help=f"Viewer snapshot dir to mutate (default: {SNAPSHOT_DIR})",
    )
    ap.add_argument("--dry-run", action="store_true", help="Don't write — just report.")
    args = ap.parse_args()

    snapshot_dir: Path = args.snapshot_dir
    cx_dir: Path = args.cellxgene_dir
    if not snapshot_dir.is_dir():
        print(f"snapshot dir missing: {snapshot_dir}", file=sys.stderr)
        return 2
    if not cx_dir.is_dir():
        print(f"cellxgene dir missing: {cx_dir}", file=sys.stderr)
        return 2

    if args.gene:
        snapshots = [snapshot_dir / f"{args.gene.upper()}.json"]
    else:
        snapshots = sorted(snapshot_dir.glob("*.json"))

    n_done, n_missing_cx, n_skipped, n_written = 0, 0, 0, 0
    for snap in snapshots:
        if not snap.exists():
            print(f"  skip {snap.name}: not in snapshot dir", file=sys.stderr)
            n_skipped += 1
            continue
        symbol = snap.stem
        cx_path = cx_dir / f"{symbol}.json"
        if not cx_path.exists():
            print(f"  {symbol}: no cellxgene record at {cx_path}", file=sys.stderr)
            n_missing_cx += 1
            continue

        rec = json.loads(snap.read_text())
        cx = json.loads(cx_path.read_text())

        # JSON: embed at top level under "cellxgene". Strip the duplicate
        # gene_symbol/hgnc_id keys (already on the outer record) AND slim
        # the long display arrays — embedding all 30/100 top_cell_types
        # with nested tissue subarrays balloons the snapshot to 200+ KB
        # per gene. Keep the top 10 of each (which carries the user-facing
        # signal); the full ranked list stays in the live CellxGene tab
        # via the Worker /v1/genes/{symbol}/cellxgene route + D1.
        cx_compact = {
            k: v for k, v in cx.items()
            if k not in ("gene_symbol", "hgnc_id", "ensembl_gene")
        }
        if isinstance(cx_compact.get("top_cell_types"), list):
            cx_compact["top_cell_types"] = cx_compact["top_cell_types"][:10]
        if isinstance(cx_compact.get("top_tissues"), list):
            cx_compact["top_tissues"] = cx_compact["top_tissues"][:10]
        # cells_by_tissue is the tissue→cell-type reverse map; only used
        # by the interactive cross-filter in the viewer chart. Dropping
        # it from the embedded snapshot keeps the JSON small without
        # losing any data a downloader can't recover from the per-tissue
        # / per-cell-type entries already embedded.
        cx_compact.pop("cells_by_tissue", None)
        existing = rec.get("cellxgene")
        if existing == cx_compact:
            n_skipped += 1
            print(f"  {symbol}: JSON already up-to-date")
        else:
            rec["cellxgene"] = cx_compact
            if not args.dry_run:
                snap.write_text(json.dumps(rec, indent=2) + "\n")
            print(f"  {symbol}: JSON {'would' if args.dry_run else ''} embed cellxgene "
                  f"({len(json.dumps(cx_compact)):,} chars)")
            n_done += 1

        # MD: append/replace the cellxgene section
        md_path = snap.with_suffix(".md")
        if md_path.exists():
            md_text = md_path.read_text()
            section = build_cellxgene_md_section(cx)
            new_md = merge_md_section(md_text, section)
            if new_md != md_text:
                if not args.dry_run:
                    md_path.write_text(new_md)
                n_written += 1
                print(f"  {symbol}: MD {'would update' if args.dry_run else 'updated'}")
        else:
            print(f"  {symbol}: no MD file at {md_path}", file=sys.stderr)

    print(
        f"\nDone: {n_done} JSON embed(s), {n_written} MD update(s), "
        f"{n_missing_cx} missing cellxgene, {n_skipped} skipped",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
