"""Provenance schema v1 — figure-reproducibility metadata.

Defines the canonical JSON blob embedded into figure metadata
(PNG ``tEXt`` chunk ``provenance``, PDF ``Keywords`` field). Mirrors
the schema documented in
``docs/figure-reproducibility-schema.md``.

Stable identifiers are the goal of this module: a downstream tool
should be able to verify byte-identical reproduction given just the
figure file.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

SCHEMA_VERSION = "1"

_SWHID_RE = re.compile(r"^swh:1:(cnt|dir|rev|rel|snp):[0-9a-f]{40}(;.*)?$")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceError(ValueError):
    """Raised when a provenance blob fails schema validation."""


def build_provenance(
    *,
    title: str,
    gist_url: str | None = None,
    gist_sha: str | None = None,
    swhid: str | None = None,
    zenodo_doi: str | None = None,
    repo: str | None = None,
    repo_path: str | None = None,
    repo_ref: str | None = None,
    repo_tag: str | None = None,
    data: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct a provenance blob with ``schema_version`` set.

    Pass only the fields you have; unknown identifiers should be left
    as ``None``. Run :func:`validate_provenance` on the result to
    confirm at least one durable identifier is present and that all
    string fields are well-formed.
    """
    blob: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "gist_url": gist_url,
        "gist_sha": gist_sha,
        "swhid": swhid,
        "zenodo_doi": zenodo_doi,
        "repo": repo,
        "repo_path": repo_path,
        "repo_ref": repo_ref,
        "repo_tag": repo_tag,
        "data": list(data) if data is not None else [],
    }
    return blob


def validate_provenance(blob: dict[str, Any]) -> None:
    """Raise :class:`ProvenanceError` if ``blob`` does not satisfy the schema.

    Returns ``None`` on success. Validates:

    * ``schema_version`` is the supported value.
    * ``title`` is a non-empty string.
    * ``swhid``, ``zenodo_doi``, ``gist_sha``, ``repo_ref`` (when
      present) match their respective formats.
    * Each entry in ``data`` has a string ``url``; if ``sha256`` is
      present it is 64 hex characters.
    * At least one durable identifier is present:
      ``swhid``, ``zenodo_doi``, or ``repo`` + ``repo_path`` +
      ``repo_ref``.
    """
    if blob.get("schema_version") != SCHEMA_VERSION:
        raise ProvenanceError(
            f"schema_version must be {SCHEMA_VERSION!r}, got {blob.get('schema_version')!r}"
        )
    if not isinstance(blob.get("title"), str) or not blob["title"]:
        raise ProvenanceError("title must be a non-empty string")

    swhid = blob.get("swhid")
    if swhid is not None:
        if not isinstance(swhid, str) or not _SWHID_RE.match(swhid):
            raise ProvenanceError(
                "swhid must start with 'swh:1:<cnt|dir|rev|rel|snp>:' followed by 40 hex chars"
            )

    doi = blob.get("zenodo_doi")
    if doi is not None and not (isinstance(doi, str) and _DOI_RE.match(doi)):
        raise ProvenanceError("zenodo_doi must match the DOI format 10.NNNN/...")

    repo_ref = blob.get("repo_ref")
    if repo_ref is not None and not (
        isinstance(repo_ref, str) and _COMMIT_SHA_RE.match(repo_ref)
    ):
        raise ProvenanceError(
            "repo_ref must be a 40-char hex commit SHA (tags are mutable; use repo_tag for tags)"
        )

    gist_sha = blob.get("gist_sha")
    if gist_sha is not None and not (
        isinstance(gist_sha, str) and _COMMIT_SHA_RE.match(gist_sha)
    ):
        raise ProvenanceError("gist_sha must be a 40-char hex commit SHA")

    data = blob.get("data")
    if data is not None:
        if not isinstance(data, list):
            raise ProvenanceError("data must be a list")
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise ProvenanceError(f"data[{i}] must be an object")
            url = entry.get("url")
            if not (isinstance(url, str) and url.startswith(("http://", "https://"))):
                raise ProvenanceError(f"data[{i}].url must be an http(s) URL")
            sha = entry.get("sha256")
            if sha is not None and not (isinstance(sha, str) and _SHA256_RE.match(sha)):
                raise ProvenanceError(f"data[{i}].sha256 must be 64 hex chars")

    has_durable = bool(
        swhid
        or doi
        or (blob.get("repo") and blob.get("repo_path") and repo_ref)
    )
    if not has_durable:
        raise ProvenanceError(
            "at least one durable identifier required: swhid, zenodo_doi, or "
            "(repo + repo_path + repo_ref-as-commit-sha)"
        )
