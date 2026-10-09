"""Publish tag-sites to public D1's ``tag_site_public`` table.

One row per :class:`TaggedSite` (the ``viewer/lib/tag-sites-types.ts`` contract,
i.e. exactly what ``viewer/public/tag-sites/{SYMBOL}.json`` already holds). Mirrors
:mod:`accessible_surfaceome.cloud.internalization` / ``surface_annotation``
(INSERT OR REPLACE; replace-all-per-gene so a re-derivation that drops a site
never leaves a stale row). The Worker serves these at ``/v1/tag-sites/:symbol``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client

# DDL kept in sync with cloudflare/d1_tag_sites_schema.sql. D1's HTTP API rejects
# multi-statement batches, so each statement is submitted separately.
DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS tag_site_public (
      gene_symbol                TEXT NOT NULL,
      uniprot_acc                TEXT NOT NULL,
      site_id                    TEXT NOT NULL,
      provenance                 TEXT NOT NULL,
      det_path                   TEXT,
      site_kind                  TEXT NOT NULL,
      insert_after_residue       INTEGER,
      residue_before             TEXT,
      residue_after              TEXT,
      residue_label              TEXT,
      residue_range              TEXT,
      topology_state             TEXT,
      extracellular              INTEGER NOT NULL,
      compartment                TEXT,
      tag_type                   TEXT,
      tag_length_aa              INTEGER,
      linker                     TEXT,
      evidence_type              TEXT,
      functional_impact_measured TEXT,
      confidence                 TEXT,
      rationale                  TEXT,
      sources_json               TEXT,
      plddt                      REAL,
      conservation_rank          INTEGER,
      median_conservation        REAL,
      tag_sites_version          TEXT NOT NULL,
      synced_at                  TEXT NOT NULL,
      PRIMARY KEY (uniprot_acc, site_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_tag_site_symbol "
    "ON tag_site_public (gene_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_tag_site_provenance "
    "ON tag_site_public (provenance);",
)

_COLS: tuple[str, ...] = (
    "gene_symbol", "uniprot_acc", "site_id", "provenance", "det_path", "site_kind",
    "insert_after_residue", "residue_before", "residue_after", "residue_label",
    "residue_range", "topology_state", "extracellular", "compartment", "tag_type",
    "tag_length_aa", "linker", "evidence_type", "functional_impact_measured",
    "confidence", "rationale", "sources_json", "plddt", "conservation_rank",
    "median_conservation", "tag_sites_version", "synced_at",
)


def ensure_table(client: D1Client) -> None:
    """Idempotently create the table + indexes (one statement per call)."""
    for stmt in DDL:
        client.query(stmt, [])


def flat_row(
    site: dict[str, Any], *, gene_symbol: str, uniprot_acc: str, version: str, synced_at: str
) -> dict[str, Any]:
    """Project one TaggedSite dict into the flat ``tag_site_public`` columns.
    ``sources`` (a JSON array) is serialized to ``sources_json``; ``extracellular``
    becomes 0/1."""
    return {
        "gene_symbol": site.get("gene_symbol", gene_symbol),
        "uniprot_acc": site.get("uniprot_acc", uniprot_acc),
        "site_id": site["site_id"],
        "provenance": site["provenance"],
        "det_path": site.get("det_path"),
        "site_kind": site["site_kind"],
        "insert_after_residue": site.get("insert_after_residue"),
        "residue_before": site.get("residue_before"),
        "residue_after": site.get("residue_after"),
        "residue_label": site.get("residue_label"),
        "residue_range": site.get("residue_range"),
        "topology_state": site.get("topology_state"),
        "extracellular": 1 if site.get("extracellular") else 0,
        "compartment": site.get("compartment"),
        "tag_type": site.get("tag_type"),
        "tag_length_aa": site.get("tag_length_aa"),
        "linker": site.get("linker"),
        "evidence_type": site.get("evidence_type"),
        "functional_impact_measured": site.get("functional_impact_measured"),
        "confidence": site.get("confidence"),
        "rationale": site.get("rationale"),
        "sources_json": json.dumps(site.get("sources", [])),
        "plddt": site.get("plddt"),
        "conservation_rank": site.get("conservation_rank"),
        "median_conservation": site.get("median_conservation"),
        "tag_sites_version": version,
        "synced_at": synced_at,
    }


def rows_for_file(data: dict[str, Any], *, version: str, synced_at: str) -> list[dict[str, Any]]:
    """Flatten a TaggedSitesFile dict into per-site rows (pure; used by tests)."""
    gene = data["gene_symbol"]
    acc = data["uniprot_acc"]
    return [
        flat_row(s, gene_symbol=gene, uniprot_acc=acc, version=version, synced_at=synced_at)
        for s in data.get("sites", [])
    ]



def enrich_sources_with_paper_metadata(
    rows: list[dict[str, Any]], *, client: D1Client
) -> int:
    """Join ``paper_metadata`` into each row's ``sources_json`` and return the
    number of sources enriched.

    A tag-site citation carried only a PMID, so the viewer could render "PMID
    29725305" and nothing a reader recognises. The deep dive solved this
    already: the same table, keyed the same way, is joined into
    ``/v1/genes/{sym}/evidence`` at serve time. The tag-sites route is deployed
    from a Worker whose source is not in this repo, so the join happens here
    instead — which also enriches every row already published rather than only
    what a future run produces.

    Missing metadata is left alone: a preprint with no PMID has no row to join,
    and a citation without a title is still a citation."""
    import json as _json

    pmids: set[str] = set()
    parsed: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for row in rows:
        try:
            srcs = _json.loads(row.get("sources_json") or "[]")
        except Exception:  # noqa: BLE001 - a malformed blob must not fail the sync
            continue
        if not isinstance(srcs, list):
            continue
        parsed.append((row, srcs))
        pmids.update(str(s["pmid"]) for s in srcs if isinstance(s, dict) and s.get("pmid"))
    if not pmids:
        return 0

    meta: dict[str, dict[str, Any]] = {}
    ordered = sorted(pmids)
    for i in range(0, len(ordered), 50):  # D1 caps bound parameters per query
        chunk = ordered[i : i + 50]
        marks = ", ".join(["?"] * len(chunk))
        for m in client.query(
            f"SELECT pmid, title, authors_short, journal, year FROM paper_metadata "
            f"WHERE pmid IN ({marks});",
            chunk,
        ):
            if m.get("pmid"):
                meta[str(m["pmid"])] = m

    n = 0
    for row, srcs in parsed:
        changed = False
        for src in srcs:
            if not isinstance(src, dict):
                continue
            m = meta.get(str(src.get("pmid") or ""))
            if not m:
                continue
            src["title"] = m.get("title")
            src["authors"] = m.get("authors_short")
            src["journal"] = m.get("journal")
            src["year"] = m.get("year")
            changed, n = True, n + 1
        if changed:
            row["sources_json"] = _json.dumps(srcs)
    return n


def publish_tag_sites(
    data: dict[str, Any],
    *,
    tag_sites_version: str,
    client: D1Client | None = None,
    provenances: Iterable[str] | None = None,
) -> int:
    """UPSERT one gene's tag-sites into public D1 and return the row count written.

    UPSERT by ``site_id``, with stale-row cleanup scoped to the PROVENANCES this
    file speaks for — not replace-all.

    It used to delete every row for the gene first. One file is written by two
    independent pipelines (deterministic and literature), so a file carrying only
    literature sites would delete the gene's deterministic rows: a sync from
    snapshots that had drifted below D1 removed 40 live rows that way, including
    every deterministic site for a gene whose in-tree JSON had lost them at an
    earlier commit while D1 kept serving them.

    Scoping the delete keeps what it was for — a re-derivation that DROPS a site
    must not leave a stale row behind — without letting one pipeline's output
    silently erase another's. Pass ``provenances`` explicitly when a run must be
    authoritative for a provenance its output no longer contains (a literature
    re-run that legitimately found nothing still has to clear the old literature
    rows); the default infers it from the file, which cannot express that.

    Idempotent — re-runs converge on the same rows. Caller owns ``client`` when
    passed; otherwise a public client is opened + closed."""
    synced_at = datetime.now(UTC).isoformat()
    rows = rows_for_file(data, version=tag_sites_version, synced_at=synced_at)
    scope = sorted(set(provenances)) if provenances is not None else sorted(
        {r["provenance"] for r in rows if r.get("provenance")}
    )

    owns = client is None
    client = client or D1Client.public()
    try:
        ensure_table(client)
        enrich_sources_with_paper_metadata(rows, client=client)
        if scope:
            keep = [r["site_id"] for r in rows]
            marks = ", ".join(["?"] * len(scope))
            sql = (
                f"DELETE FROM tag_site_public WHERE gene_symbol = ? "
                f"AND provenance IN ({marks})"
            )
            params: list[Any] = [data["gene_symbol"], *scope]
            if keep:
                sql += f" AND site_id NOT IN ({', '.join(['?'] * len(keep))})"
                params += keep
            client.query(sql + ";", params)
        cols = ", ".join(_COLS)
        placeholders = ", ".join(["?"] * len(_COLS))
        for row in rows:
            client.query(
                f"INSERT OR REPLACE INTO tag_site_public ({cols}) VALUES ({placeholders});",
                [row[c] for c in _COLS],
            )
    finally:
        if owns:
            client.close()
    return len(rows)
