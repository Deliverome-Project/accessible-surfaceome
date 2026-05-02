"""Shared helpers for external dataset download scripts with traceability."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

USER_AGENT = "internalizers-data-fetch/1.0"


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 hex digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_binary(url: str, timeout: int = 120) -> tuple[bytes, dict[str, str]]:
    """Download binary content and return bytes + selected response headers."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        data = response.read()
        headers = {
            "content_type": response.headers.get("Content-Type", ""),
            "content_length_header": response.headers.get("Content-Length", ""),
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
        }
    return data, headers


def relative_to_repo(path: Path, repo_root: Path) -> str:
    """Return POSIX-style relative path to repo root when possible."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.resolve().as_posix()


def build_file_record(
    *,
    repo_root: Path,
    file_path: Path,
    source_url: str,
    dataset: str,
    taxid: str | None = None,
    species: str | None = None,
    status: str,
    response_headers: dict[str, str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Build a traceability record for one local file."""
    record: dict[str, Any] = {
        "dataset": dataset,
        "source_url": source_url,
        "local_path": relative_to_repo(file_path, repo_root),
        "file_name": file_path.name,
        "size_bytes": int(file_path.stat().st_size),
        "sha256": sha256_file(file_path),
        "captured_at_utc": utc_now_iso(),
        "status": status,
        "note": note,
    }
    if taxid is not None:
        record["taxid"] = str(taxid)
    if species is not None:
        record["species"] = species
    if response_headers:
        record["response_headers"] = response_headers
    return record


def write_manifest(path: Path, *, dataset: str, script: str, records: list[dict[str, Any]], extras: dict[str, Any] | None = None) -> None:
    """Write manifest JSON with top-level metadata and file records."""
    payload: dict[str, Any] = {
        "dataset": dataset,
        "generated_at_utc": utc_now_iso(),
        "script": script,
        "n_files": len(records),
        "records": records,
    }
    if extras:
        payload["extras"] = extras
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
