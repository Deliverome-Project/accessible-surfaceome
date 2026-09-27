"""Numbered data releases: fixed per-gene pointers into record history."""

from __future__ import annotations

import gzip
import io
import os
import re
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from accessible_surfaceome.cloud.record_history.store import blob_key

# 3 columns per member row; D1 caps a statement at 100 bound parameters.
MEMBER_ROWS_PER_INSERT = 100 // 3

_DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")


class ReleaseError(RuntimeError):
    pass


class ReleaseExistsError(ReleaseError):
    pass


class _D1(Protocol):
    def query(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]: ...


def latest_members(d1: _D1) -> list[tuple[str, int]]:
    """(gene_symbol, latest revision) for every gene currently live.

    ``IN (SELECT gene_symbol FROM surface_annotation)`` is one scan of
    ``surface_annotation`` compared against ``record_revision``'s own
    ``COLLATE NOCASE`` column — the correlated ``EXISTS`` form re-scanned
    ``surface_annotation`` once per ``record_revision`` row.
    """
    rows = d1.query(
        "SELECT r.gene_symbol AS gene_symbol, MAX(r.revision) AS revision "
        "FROM record_revision r "
        "WHERE r.gene_symbol IN (SELECT gene_symbol FROM surface_annotation) "
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
    """Cut a numbered release, safe under partial failure and D1's at-least-once retries.

    Ordering matters: the member rows are written first and the
    ``data_release`` row is written LAST (and only after the member count
    is verified). That way a crash or a raised exception anywhere before
    the final insert leaves NO ``data_release`` row — so a retried call
    for the same ``version`` re-enters cleanly instead of tripping
    :class:`ReleaseExistsError` on a half-cut release. Member inserts use
    ``ON CONFLICT ... DO NOTHING`` so a duplicated batch (an HTTP-level
    retry replaying an insert that actually already landed) is a no-op,
    not an error or a double-count.
    """
    if not members:
        raise ReleaseError("create_release requires at least one member")
    seen: set[str] = set()
    for sym, _rev in members:
        key = sym.casefold()
        if key in seen:
            raise ReleaseError(f"duplicate member symbol (case-insensitive): {sym}")
        seen.add(key)

    if d1.query("SELECT 1 FROM data_release WHERE version = ?", [version]):
        raise ReleaseExistsError(f"release {version} already exists")

    # Clear any orphaned member rows from a prior failed attempt at this
    # same version. Safe: we just confirmed no data_release row exists,
    # so this version was never actually cut.
    d1.query("DELETE FROM data_release_member WHERE version = ?", [version])

    for i in range(0, len(members), MEMBER_ROWS_PER_INSERT):
        chunk = members[i : i + MEMBER_ROWS_PER_INSERT]
        placeholders = ",".join(["(?, ?, ?)"] * len(chunk))
        params: list[Any] = []
        for sym, revision in chunk:
            params += [version, sym, revision]
        d1.query(
            f"INSERT INTO data_release_member (version, gene_symbol, revision) "
            f"VALUES {placeholders} ON CONFLICT(version, gene_symbol) DO NOTHING",
            params,
        )

    count_rows = d1.query(
        "SELECT count(*) AS n FROM data_release_member WHERE version = ?", [version]
    )
    n_written = int(count_rows[0]["n"])
    if n_written != len(members):
        raise ReleaseError(
            f"release {version}: expected {len(members)} members, found {n_written}"
        )

    d1.query(
        "INSERT INTO data_release (version, cut_at, github_tag, zenodo_version_doi, n_genes, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(version) DO NOTHING",
        [version, cut_at, github_tag, zenodo_version_doi, len(members), notes],
    )
    if not d1.query("SELECT 1 FROM data_release WHERE version = ?", [version]):
        raise ReleaseError(f"release {version}: failed to record the release row")


def set_zenodo_doi(d1: _D1, version: str, doi: str) -> None:
    """Record the published Zenodo version DOI.

    Idempotent under retry: a repeat call with the SAME doi succeeds
    silently (an at-least-once HTTP retry replaying a write that already
    landed). A call with a DIFFERENT doi than what's already stored, or
    for a release that doesn't exist, raises :class:`ReleaseError`.
    """
    if not _DOI_RE.match(doi):
        raise ReleaseError(f"not a Zenodo data-record DOI: {doi!r}")

    updated = d1.query(
        "UPDATE data_release SET zenodo_version_doi = ? "
        "WHERE version = ? AND zenodo_version_doi IS NULL "
        "RETURNING version",
        [doi, version],
    )
    if updated:
        return

    rows = d1.query(
        "SELECT zenodo_version_doi FROM data_release WHERE version = ?", [version]
    )
    if not rows:
        raise ReleaseError(f"release {version} does not exist")
    existing = rows[0]["zenodo_version_doi"]
    if existing == doi:
        return  # idempotent retry: same DOI already recorded
    raise ReleaseError(f"release {version} already has DOI {existing}")


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

    The tarball is byte-reproducible: the gzip wrapper is built with a
    fixed ``mtime`` and no embedded filename, and every tar member has its
    mtime/uid/gid/uname/gname/mode pinned, so two exports of the same
    release produce identical bytes. The write is atomic — content is
    staged at ``<name>.tar.gz.partial`` and only renamed into place via
    ``os.replace`` once every part has been fetched and written; on any
    failure the partial file is removed and neither it nor the final
    tarball is left behind.
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
    for r in rows:
        sym = r["gene_symbol"]
        if "/" in sym or ".." in sym:
            raise ReleaseError(f"unsafe gene symbol in release {version}: {sym!r}")

    out = out_dir / f"deep_dives_{version}.tar.gz"
    partial = out_dir / f"{out.name}.partial"
    lines = ["gene_symbol\thgnc_id\trevision\tjson_hash\tevidence_hash\tmd_hash"]

    def add(tf: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mode = 0o644
        tf.addfile(info, io.BytesIO(data))

    try:
        with (
            partial.open("wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz,
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf,
        ):
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
        os.replace(partial, out)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return out
