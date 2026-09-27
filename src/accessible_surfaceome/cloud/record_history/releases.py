"""Numbered data releases: fixed per-gene pointers into record history."""

from __future__ import annotations

import io
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from accessible_surfaceome.cloud.record_history.store import blob_key

# 3 columns per member row; D1 caps a statement at 100 bound parameters.
MEMBER_ROWS_PER_INSERT = 100 // 3


class ReleaseError(RuntimeError):
    pass


class ReleaseExistsError(ReleaseError):
    pass


class _D1(Protocol):
    def query(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]: ...


def latest_members(d1: _D1) -> list[tuple[str, int]]:
    """(gene_symbol, latest revision) for every gene currently live."""
    rows = d1.query(
        "SELECT r.gene_symbol AS gene_symbol, MAX(r.revision) AS revision "
        "FROM record_revision r "
        "WHERE EXISTS (SELECT 1 FROM surface_annotation s "
        "               WHERE s.gene_symbol = r.gene_symbol COLLATE NOCASE) "
        "GROUP BY r.gene_symbol ORDER BY r.gene_symbol",
        [],
    )
    return [(r["gene_symbol"], int(r["revision"])) for r in rows]


def create_release(
    d1: _D1,
    *,
    version: str,
    cut_at: str,
    github_tag: str | None,
    zenodo_version_doi: str | None,
    notes: str | None,
    members: list[tuple[str, int]],
) -> None:
    if d1.query("SELECT 1 FROM data_release WHERE version = ?", [version]):
        raise ReleaseExistsError(f"release {version} already exists")
    d1.query(
        "INSERT INTO data_release (version, cut_at, github_tag, zenodo_version_doi, n_genes, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [version, cut_at, github_tag, zenodo_version_doi, len(members), notes],
    )
    for i in range(0, len(members), MEMBER_ROWS_PER_INSERT):
        chunk = members[i : i + MEMBER_ROWS_PER_INSERT]
        placeholders = ",".join(["(?, ?, ?)"] * len(chunk))
        params: list[Any] = []
        for sym, revision in chunk:
            params += [version, sym, revision]
        d1.query(
            f"INSERT INTO data_release_member (version, gene_symbol, revision) VALUES {placeholders}",
            params,
        )


def set_zenodo_doi(d1: _D1, version: str, doi: str) -> None:
    """Record the published Zenodo version DOI. Allowed exactly once."""
    rows = d1.query(
        "SELECT zenodo_version_doi FROM data_release WHERE version = ?", [version]
    )
    if not rows:
        raise ReleaseError(f"release {version} does not exist")
    if rows[0]["zenodo_version_doi"]:
        raise ReleaseError(
            f"release {version} already has DOI {rows[0]['zenodo_version_doi']}"
        )
    d1.query(
        "UPDATE data_release SET zenodo_version_doi = ? WHERE version = ?",
        [doi, version],
    )


def export_release(
    d1: _D1,
    version: str,
    out_dir: Path,
    *,
    get_blob: Callable[[str], bytes],
) -> Path:
    """Write ``deep_dives_{version}.tar.gz`` from the release's archived parts.

    ``get_blob(key)`` must return the bytes or raise — a release export
    with a missing record is never acceptable.
    """
    rows = d1.query(
        "SELECT m.gene_symbol AS gene_symbol, r.hgnc_id AS hgnc_id, m.revision AS revision, "
        "       r.json_hash AS json_hash, r.evidence_hash AS evidence_hash, r.md_hash AS md_hash "
        "FROM data_release_member m JOIN record_revision r "
        "  ON r.gene_symbol = m.gene_symbol COLLATE NOCASE AND r.revision = m.revision "
        "WHERE m.version = ? ORDER BY m.gene_symbol",
        [version],
    )
    if not rows:
        raise ReleaseError(f"release {version} has no members")
    out = out_dir / f"deep_dives_{version}.tar.gz"
    lines = ["gene_symbol\thgnc_id\trevision\tjson_hash\tevidence_hash\tmd_hash"]

    # Fixed mtime so re-exporting a release yields a byte-identical member
    # listing (tar embeds each member's mtime; a wall-clock timestamp would
    # make two exports of the same release diverge even with identical
    # content).
    def add(tf: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mtime = 0
        tf.addfile(info, io.BytesIO(data))

    with tarfile.open(out, "w:gz") as tf:
        for r in rows:
            sym = r["gene_symbol"]
            add(tf, f"genes/{sym}.json", get_blob(blob_key(r["json_hash"], "json")))
            if r["evidence_hash"]:
                add(
                    tf,
                    f"genes/{sym}.evidence.json",
                    get_blob(blob_key(r["evidence_hash"], "json")),
                )
            if r["md_hash"]:
                add(tf, f"genes/{sym}.md", get_blob(blob_key(r["md_hash"], "md")))
            lines.append(
                "\t".join(
                    str(r[k] or "")
                    for k in (
                        "gene_symbol",
                        "hgnc_id",
                        "revision",
                        "json_hash",
                        "evidence_hash",
                        "md_hash",
                    )
                )
            )
        add(tf, "manifest.tsv", ("\n".join(lines) + "\n").encode())
    return out
