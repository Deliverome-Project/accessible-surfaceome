"""Publish a v2 deep-dive ``SurfaceomeRecord`` to the surfaces that serve it.

The viewer reads per-gene records from two surfaces:

* ``viewer/public/data/surfaceome/{SYMBOL}.json`` — committed snapshot, used
  as the offline / Worker-down fallback.
* Public Cloudflare D1 ``surface_annotation.annotation_json`` — what the
  ``api.deliverome.org/surfaceome/v1/genes/:symbol`` Worker serves on each
  per-gene page load.

After a v2 annotate run completes, both surfaces need to receive the new
record. If only the local file is written, the viewer keeps serving the
stale (often field-incomplete) D1 row and the page either crashes or
silently renders missing sections.

:func:`publish_record` writes both surfaces atomically (snapshot first,
then D1). The D1 push is skipped with a clear log when Cloudflare env
vars aren't set (CI without secrets, offline dev), so callers can wire
it into their default path without breaking those environments.

This module is the canonical "publish a record" path — both the v2
annotate driver and the maintenance script
(``scripts/upload_viewer_snapshots_to_d1.py``) call into it so the two
surfaces never drift.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.cloud.d1_client import D1Config
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

# Public base the Worker route serves under. Used only to build the exact
# URLs to purge from Cloudflare's edge cache after a D1 write — see
# ``_purge_urls_for``. Matches the ``[[routes]]`` pattern in
# ``cloudflare/workers/surfaceome_api/wrangler.toml``
# (``api.deliverome.org/surfaceome/*``).
PUBLIC_API_BASE = "https://api.deliverome.org/surfaceome"

# Mirrors ``cloudflare/d1_public_schema.sql::surface_annotation``. Keep in
# sync with ``scripts/sync_public_d1.py::sync_surface_annotations``.
_COLS = [
    "gene_symbol",
    "uniprot_acc",
    "schema_version",
    "annotation_json",
    "confidence",
    "triage_signal",
    "surface_status",
    "model_path",
    "evidence_count",
    "primary_evidence_count",
    "annotated_at",
]


@dataclass
class PublishResult:
    """Outcome of one :func:`publish_record` call."""

    gene_symbol: str
    snapshot_path: Path | None
    d1_written: bool
    d1_database_id: str | None
    stale_versions_dropped: list[str]
    skipped_reason: str | None = None
    # Edge-cache purge outcome after the D1 write:
    #   None  — not attempted (no D1 write, or CLOUDFLARE_ZONE_ID unset)
    #   True  — purge_cache POST succeeded; new record is live immediately
    #   False — purge attempted but failed; record goes live on TTL instead
    cache_purged: bool | None = None


def _public_config_from_env() -> D1Config | None:
    """Build a public-DB :class:`D1Config` from env, or return ``None`` on miss.

    Missing creds is a soft skip, not an error — agents on CI runners /
    fresh checkouts shouldn't crash because Cloudflare secrets aren't
    wired in. The caller logs a clear message in that case.
    """
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (acct and token and db):
        return None
    return D1Config(account_id=acct, database_id=db, api_token=token)


def _post(
    cfg: D1Config, sql: str, params: list[Any], *, client: httpx.Client
) -> dict[str, Any]:
    url = f"{API_ROOT}/accounts/{cfg.account_id}/d1/database/{cfg.database_id}/query"
    resp = client.post(
        url,
        headers={
            "Authorization": f"Bearer {cfg.api_token}",
            "Content-Type": "application/json",
        },
        json={"sql": sql, "params": params},
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"D1 query failed: {body}")
    return body


def _purge_urls_for(sym: str) -> list[str]:
    """The exact public Worker URLs a republish of ``sym`` invalidates.

    A ``surface_annotation`` write changes three cached surfaces:

    * the per-gene record (``/v1/genes/{SYMBOL}``),
    * the genome-wide catalog (``/v1/catalog`` — carries a slimmed
      ``ddf`` projection of every deep-dived gene's filters), and
    * the gene-list index (``/v1/genes``).

    Orthologs, triage, and benchmark endpoints are NOT touched by a
    record publish, so they're deliberately excluded — a tighter purge
    set means we never disturb the rest of the shared ``deliverome.org``
    zone cache.

    The catalog cache key is query-string-insensitive (the Cloudflare
    cache rule applied by ``scripts/apply_cf_edge_rules.py``), so purging
    the bare URL is sufficient — there are no ``?x=`` variants to chase.
    """
    base = PUBLIC_API_BASE
    return [
        f"{base}/v1/genes/{sym}",
        f"{base}/v1/catalog",
        f"{base}/v1/genes",
    ]


def _purge_cf_cache(
    urls: list[str], *, zone_id: str, token: str, client: httpx.Client
) -> bool:
    """Targeted Cloudflare ``purge_cache`` by URL. Returns success bool.

    Deliberately a *file* purge, never ``purge_everything`` — the Worker
    shares the ``deliverome.org`` zone with the main site, so a blanket
    purge would evict unrelated production assets. Cloudflare's by-URL
    purge is available on every plan.
    """
    resp = client.post(
        f"{API_ROOT}/zones/{zone_id}/purge_cache",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"files": list(urls)},
    )
    resp.raise_for_status()
    body = resp.json()
    return bool(body.get("success"))


def _maybe_purge(sym: str, *, token: str, client: httpx.Client) -> bool | None:
    """Best-effort edge-cache purge after a D1 write.

    Soft-skips (returns ``None``, warns) when ``CLOUDFLARE_ZONE_ID`` is
    unset — same posture as the D1 push itself, so CI / offline dev never
    breaks. Never raises: a purge failure just means the record goes live
    on the Worker's Cache-Control TTL (up to a day for per-gene records)
    instead of immediately.
    """
    zone = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if not zone:
        logger.warning(
            "CLOUDFLARE_ZONE_ID not set — skipping edge-cache purge for %s. "
            "The new record goes live on the Worker's Cache-Control TTL "
            "(up to 1 day for per-gene records) rather than immediately.",
            sym,
        )
        return None
    try:
        ok = _purge_cf_cache(
            _purge_urls_for(sym), zone_id=zone, token=token, client=client
        )
        if ok:
            logger.info("edge-cache purged for %s (per-gene + catalog + list)", sym)
        else:
            logger.warning(
                "edge-cache purge for %s returned success=false — stale until TTL",
                sym,
            )
        return ok
    except Exception as exc:  # noqa: BLE001 — purge is best-effort, never fatal
        logger.warning(
            "edge-cache purge failed for %s (%s) — record stale until TTL",
            sym,
            exc,
        )
        return False


def _existing_versions_for(
    cfg: D1Config, gene_symbol: str, *, client: httpx.Client
) -> list[str]:
    body = _post(
        cfg,
        "SELECT schema_version FROM surface_annotation WHERE gene_symbol = ?",
        [gene_symbol],
        client=client,
    )
    return [r["schema_version"] for r in body["result"][0].get("results", [])]


def _surface_bind_has_data(rec_dict: dict[str, Any]) -> bool | None:
    """``deterministic_features.surface_bind.has_data`` of a record dict.

    Returns ``None`` when the field is absent/malformed so the regression
    guard only fires on an explicit ``False``.
    """
    det = rec_dict.get("deterministic_features") or {}
    sb = det.get("surface_bind") or {}
    val = sb.get("has_data")
    return val if isinstance(val, bool) else None


def _family_populated(rec_dict: dict[str, Any]) -> bool:
    """True when the record carries any deterministic family tag —
    ``executive_summary.uniprot_family`` or ``hgnc_gene_groups``.

    These are curator-assigned ground truth injected from the resolved
    IdentifierBundle (NOT model output). A record with BOTH empty usually
    means a degraded resolution (HGNC/UniProt fetch failed at generation
    time), not a gene that genuinely has no family.
    """
    es = rec_dict.get("executive_summary") or {}
    return bool(es.get("uniprot_family")) or bool(es.get("hgnc_gene_groups"))


def _heal_family_in_place(
    rec_dict: dict[str, Any], hgnc_id: str | None, *, sym: str
) -> bool:
    """Fill ``executive_summary.{hgnc_gene_groups,uniprot_family}`` from the
    canonical resolver when the record arrives without them. Mutates
    ``rec_dict`` in place; returns ``True`` iff it injected real tags.

    The family is curator-assigned ground truth keyed on ``hgnc_id``, so
    resolving it at publish time is equivalent to what
    ``_attach_deterministic_families`` does at generation time — just applied
    to EVERY write, so already-published or degraded-at-generation records
    repair themselves on the next publish instead of needing a bespoke
    backfill. Idempotent (re-resolves the same ground truth each time).

    Resolver failure or a genuinely family-less gene leaves the record
    untouched — the publish-time regression guard still protects populated
    D1 rows, so this never *masks* a degraded resolver, it only *fills* when
    the resolver is healthy.
    """
    if not hgnc_id:
        return False
    # Lazy import keeps the resolver's HTTP stack out of this module's import
    # graph (and sidesteps any import cycle) for the common already-populated
    # path, which never calls this.
    try:
        from accessible_surfaceome.tools._shared.http import open_default_client
        from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

        with open_default_client() as http:
            bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    except Exception as exc:  # noqa: BLE001 — self-heal must never break a publish
        logger.warning(
            "family self-heal: resolver failed for %s (%s): %s; leaving "
            "family empty (regression guard still applies)",
            sym,
            hgnc_id,
            exc,
        )
        return False
    groups = list(bundle.hgnc_gene_groups or [])
    fam = bundle.uniprot_family
    if not groups and not fam:
        return False  # gene genuinely has no curated family — correct as-is
    es = rec_dict.setdefault("executive_summary", {})
    es["hgnc_gene_groups"] = groups
    es["uniprot_family"] = fam
    logger.info(
        "family self-heal: injected %d HGNC group(s) + uniprot_family for %s",
        len(groups),
        sym,
    )
    return True


def _fetch_existing_record(
    cfg: D1Config, gene_symbol: str, *, client: httpx.Client
) -> dict[str, Any] | None:
    """The latest stored record dict for ``gene_symbol`` in D1, or ``None``
    when there's no row / the blob can't be parsed — the guard treats
    "unknown existing state" as "don't block".
    """
    body = _post(
        cfg,
        "SELECT annotation_json FROM surface_annotation WHERE gene_symbol = ? "
        "ORDER BY schema_version DESC LIMIT 1",
        [gene_symbol],
        client=client,
    )
    results = body["result"][0].get("results", [])
    if not results:
        return None
    try:
        return json.loads(results[0]["annotation_json"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _record_regressions(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> list[str]:
    """Deterministic fields that would regress from populated → empty if
    ``incoming`` replaced ``existing`` in D1. Empty list = safe to publish.

    A record generated with unhydrated data / a degraded resolver silently
    comes back with empty deterministic blocks (every gene "not in
    SURFACE-Bind", no family tags). Publishing that over a good D1 row
    wipes real data — EGFR's 8 SURFACE-Bind sites collapse to "not in
    SURFACE-Bind", its ErbB / EGF-receptor family chips vanish. Each check
    below is a populated → empty transition the guard refuses to make.
    """
    out: list[str] = []
    if (
        _surface_bind_has_data(existing) is True
        and _surface_bind_has_data(incoming) is False
    ):
        out.append("surface_bind.has_data True→False")
    if _family_populated(existing) and not _family_populated(incoming):
        out.append(
            "deterministic family (uniprot_family / hgnc_gene_groups) "
            "populated→empty"
        )
    return out


def _record_generated_at(rec: dict[str, Any]) -> datetime | None:
    """Parse ``record_generated_at`` to a datetime, or None if absent/bad."""
    ts = rec.get("record_generated_at")
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _is_stale(incoming: dict[str, Any], existing: dict[str, Any]) -> bool:
    """True when the ``existing`` D1 record was generated more recently than
    ``incoming`` — i.e. publishing ``incoming`` would overwrite a newer run
    with an older snapshot.

    Conservative: returns False when either timestamp is missing/unparseable,
    so an ambiguous case never hard-blocks a legitimate publish (the
    regression guard still covers the populated→empty footgun separately).
    """
    inc = _record_generated_at(incoming)
    exi = _record_generated_at(existing)
    if inc is None or exi is None:
        return False
    return exi > inc


def _row_from_dict(
    rec_dict: dict[str, Any], *, annotated_at: str | None = None
) -> list[Any]:
    """Project a raw record dict to the column tuple D1 expects.

    Operates on a dict (not a validated ``SurfaceomeRecord``) so the
    bulk-sync maintenance path can push historical snapshots whose
    schema has drifted from the current in-tree Pydantic model. The
    canonical source of truth for "what the viewer renders" is the
    JSON blob on disk; validation belongs at agent-write time, not at
    publish time.
    """
    gene = rec_dict.get("gene") or {}
    sb = rec_dict.get("surface_biology") or {}
    return [
        gene.get("hgnc_symbol"),
        gene.get("uniprot_acc"),
        rec_dict.get("schema_version") or "1.0.0",
        # Re-encode without indentation — the D1 blob is read by JS only,
        # so we save bytes on the wire and at rest.
        json.dumps(rec_dict, separators=(",", ":")),
        rec_dict.get("confidence"),
        rec_dict.get("triage_signal"),
        sb.get("surface_status"),
        rec_dict.get("model_path"),
        rec_dict.get("evidence_count") or 0,
        rec_dict.get("primary_evidence_count") or 0,
        annotated_at or datetime.now(UTC).isoformat(),
    ]


def _heal_family_in_place(rec_dict: dict[str, Any]) -> bool:
    """Re-assert the deterministic, ``hgnc_id``-keyed family tags at publish time.

    ``hgnc_gene_groups`` / ``uniprot_family`` are curator-assigned ground truth
    resolved from the gene's stable identifier — not model output. A record
    generated under a degraded resolver, or an older snapshot pushed through the
    bulk-sync path, can carry empty family fields, which blanks the viewer's
    Family chip. Healing them on every publish surface (this runs inside the
    shared ``_publish_dict``, so both the agent path and the bulk-sync path hit
    it) closes the gap that lets a fix land in the JSON without reaching D1.

    Cheap by default: a record whose family fields are already populated is left
    untouched — no network. Only an empty field triggers a stable-ID re-resolve.
    The fill is guarded so a resolver miss never overwrites a populated value
    with an empty one, and any resolver failure is swallowed so publish never
    breaks. Returns ``True`` if a field was healed.
    """
    summary = rec_dict.get("executive_summary")
    if not isinstance(summary, dict):
        return False
    existing_groups = summary.get("hgnc_gene_groups") or []
    existing_family = summary.get("uniprot_family")
    if existing_groups and existing_family:
        return False  # healthy — skip the network re-resolve

    hgnc_id = (rec_dict.get("gene") or {}).get("hgnc_id")
    if not hgnc_id:
        return False

    try:
        from accessible_surfaceome.tools._shared.http import open_default_client
        from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id

        bundle = resolve_by_hgnc_id(hgnc_id, http=open_default_client())
    except Exception as exc:  # noqa: BLE001 — never break publish on a resolver miss
        logger.warning(
            "family self-heal: stable-ID resolve failed for %s (%s); "
            "leaving family fields as-is",
            hgnc_id,
            exc,
        )
        return False

    healed = False
    resolved_groups = list(bundle.hgnc_gene_groups)
    # Populated-to-empty guard: only fill an empty field with a non-empty
    # resolved value; never the reverse.
    if not existing_groups and resolved_groups:
        summary["hgnc_gene_groups"] = resolved_groups
        healed = True
    if existing_family is None and bundle.uniprot_family is not None:
        summary["uniprot_family"] = bundle.uniprot_family
        healed = True
    if healed:
        logger.info(
            "family self-heal: filled family tags for %s from %s",
            (rec_dict.get("gene") or {}).get("hgnc_symbol"),
            hgnc_id,
        )
    return healed


def _publish_dict(
    rec_dict: dict[str, Any],
    *,
    snapshot_dir: Path | None,
    write_snapshot: bool,
    push_to_d1: bool,
    pretty_snapshot: bool,
    force: bool = False,
) -> PublishResult:
    """Shared core: write the snapshot + push to D1 from a raw record dict."""
    gene = rec_dict.get("gene") or {}
    sym = gene.get("hgnc_symbol")
    if not sym:
        raise ValueError("record dict missing required gene.hgnc_symbol")

    # Self-heal deterministic, stable-ID-keyed tags before BOTH surfaces get
    # written, so the snapshot and D1 can never carry divergent family fields.
    _heal_family_in_place(rec_dict)

    snap_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    snap_path: Path | None = None
    if write_snapshot:
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{sym}.json"
        snap_path.write_text(
            json.dumps(rec_dict, indent=2 if pretty_snapshot else None)
        )
        logger.info("snapshot written: %s", snap_path)

    if not push_to_d1:
        return PublishResult(
            gene_symbol=sym,
            snapshot_path=snap_path,
            d1_written=False,
            d1_database_id=None,
            stale_versions_dropped=[],
            skipped_reason="push_to_d1=False",
        )

    cfg = _public_config_from_env()
    if cfg is None:
        logger.warning(
            "public D1 env vars missing (CLOUDFLARE_ACCOUNT_ID / "
            "CLOUDFLARE_API_TOKEN / CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID) — "
            "skipping D1 publish for %s. Snapshot was still written.",
            sym,
        )
        return PublishResult(
            gene_symbol=sym,
            snapshot_path=snap_path,
            d1_written=False,
            d1_database_id=None,
            stale_versions_dropped=[],
            skipped_reason="missing CLOUDFLARE_* env vars",
        )

    row = _row_from_dict(rec_dict)
    new_version = row[2]
    with httpx.Client(timeout=60) as client:
        # Regression guard — never let a publish blank out a populated
        # deterministic block. A record generated with unhydrated data / a
        # degraded resolver silently comes back empty (surface_bind
        # has_data=False for every gene; no family tags), and publishing it
        # over a good D1 row wipes real data. Fetch the existing row only
        # when the incoming record looks degraded — a cheap fast-path for
        # the common, fully-populated case.
        if not force:
            existing = _fetch_existing_record(cfg, sym, client=client)
            if existing is not None:
                # Staleness guard — never overwrite a NEWER D1 run with an
                # OLDER incoming record. This is the bulk-sync footgun: a
                # stale on-disk snapshot (e.g. from a worktree that missed
                # today's runs) would otherwise replace a freshly-published
                # record. The regression guard below only fires for degraded
                # (empty) incoming records, so a stale-but-populated snapshot
                # sails past it — this catches that case.
                if _is_stale(rec_dict, existing):
                    logger.error(
                        "REFUSING to publish %s: the D1 row was generated more "
                        "recently (%s) than this record (%s) — the incoming "
                        "snapshot is stale. Re-export it from a fresh run, or "
                        "pass force=True to overwrite.",
                        sym,
                        existing.get("record_generated_at"),
                        rec_dict.get("record_generated_at"),
                    )
                    return PublishResult(
                        gene_symbol=sym,
                        snapshot_path=snap_path,
                        d1_written=False,
                        d1_database_id=cfg.database_id,
                        stale_versions_dropped=[],
                        skipped_reason=(
                            "blocked by staleness guard: D1 row is newer than "
                            "the incoming record"
                        ),
                    )
                # Regression guard — never blank a populated deterministic
                # block (a degraded/empty incoming record over a good D1 row).
                if (
                    _surface_bind_has_data(rec_dict) is False
                    or not _family_populated(rec_dict)
                ):
                    regressions = _record_regressions(existing, rec_dict)
                    if regressions:
                        detail = "; ".join(regressions)
                        logger.error(
                            "REFUSING to publish %s: would regress %s. This "
                            "usually means deterministic data wasn't hydrated "
                            "/ resolved in the generating worktree (missing "
                            "SURFACE-Bind summary, or HGNC/UniProt family "
                            "fetch failed). Re-run generation with a healthy "
                            "resolver and re-publish, or pass force=True to "
                            "override.",
                            sym,
                            detail,
                        )
                        return PublishResult(
                            gene_symbol=sym,
                            snapshot_path=snap_path,
                            d1_written=False,
                            d1_database_id=cfg.database_id,
                            stale_versions_dropped=[],
                            skipped_reason=(
                                f"blocked by regression guard: {detail}"
                            ),
                        )

        # Drop any stale schema_versions for this gene before upserting. The
        # Worker tie-breaks on ``ORDER BY schema_version DESC LIMIT 1``, but
        # leaving stale rows in D1 means a future schema rollback or
        # `<` ordering could resurface the old field-incomplete record.
        existing = _existing_versions_for(cfg, sym, client=client)
        stale = [v for v in existing if v != new_version]
        for ver in stale:
            _post(
                cfg,
                "DELETE FROM surface_annotation WHERE gene_symbol = ? AND schema_version = ?",
                [sym, ver],
                client=client,
            )
            logger.info("dropped stale %s@%s from D1", sym, ver)

        # INSERT OR REPLACE on (gene_symbol, schema_version).
        cols_sql = ", ".join(_COLS)
        placeholders = "(" + ", ".join(["?"] * len(_COLS)) + ")"
        sql = (
            f"INSERT OR REPLACE INTO surface_annotation ({cols_sql}) "
            f"VALUES {placeholders}"
        )
        _post(cfg, sql, row, client=client)
        logger.info("D1 upserted: %s@%s -> %s", sym, new_version, cfg.database_id)

        # Purge the edge cache so the freshly-written record is live
        # immediately. Without this, the Worker keeps serving the old
        # cached response until its Cache-Control TTL expires (up to 1 day
        # for per-gene records) — the same staleness that previously let a
        # schema-incomplete D1 row keep rendering after a republish. The
        # purge reuses the D1 token (same Cloudflare account), so the only
        # extra requirement is CLOUDFLARE_ZONE_ID + a Cache Purge scope on
        # the token; missing either soft-skips with a warning.
        cache_purged = _maybe_purge(sym, token=cfg.api_token, client=client)

    return PublishResult(
        gene_symbol=sym,
        snapshot_path=snap_path,
        d1_written=True,
        d1_database_id=cfg.database_id,
        stale_versions_dropped=stale,
        skipped_reason=None,
        cache_purged=cache_purged,
    )


def publish_record(
    record: SurfaceomeRecord,
    *,
    snapshot_dir: Path | None = None,
    write_snapshot: bool = True,
    push_to_d1: bool = True,
    force: bool = False,
) -> PublishResult:
    """Write a freshly-validated ``SurfaceomeRecord`` to snapshot + D1.

    The standard agent-side entry point: takes a validated Pydantic model
    (so the record is known good), serializes it to disk and pushes to
    public D1. Returns a :class:`PublishResult` describing what landed.

    For pushing arbitrary on-disk JSON (the bulk-sync maintenance path)
    use :func:`publish_record_dict` — it skips validation so older
    snapshots whose schema has drifted can still be published.

    Args:
        record: The validated ``SurfaceomeRecord`` to publish.
        snapshot_dir: Override for the viewer-snapshot directory. Defaults
            to ``viewer/public/data/surfaceome``.
        write_snapshot: Skip the viewer-snapshot write when False.
        push_to_d1: Skip the D1 push when False (e.g. ``--no-publish``).
    """
    rec_dict = json.loads(record.model_dump_json())
    return _publish_dict(
        rec_dict,
        snapshot_dir=snapshot_dir,
        write_snapshot=write_snapshot,
        push_to_d1=push_to_d1,
        pretty_snapshot=True,
        force=force,
    )


def publish_record_dict(
    rec_dict: dict[str, Any],
    *,
    snapshot_dir: Path | None = None,
    write_snapshot: bool = False,
    push_to_d1: bool = True,
    pretty_snapshot: bool = True,
    force: bool = False,
) -> PublishResult:
    """Push a raw record dict — no Pydantic validation.

    Companion to :func:`publish_record` for the bulk-sync path
    (``scripts/upload_viewer_snapshots_to_d1.py``) where on-disk
    snapshots may predate field additions in the current Pydantic model.
    The validation contract is: "if it's on disk under
    ``viewer/public/data/surfaceome``, the viewer's allowed to render
    it, so D1 should mirror it". Validation happens at agent-write
    time, not republish time.

    Defaults to ``write_snapshot=False`` because the typical caller for
    this entry point is reading FROM the snapshot dir and just wants to
    push that content to D1.
    """
    return _publish_dict(
        rec_dict,
        snapshot_dir=snapshot_dir,
        write_snapshot=write_snapshot,
        push_to_d1=push_to_d1,
        pretty_snapshot=pretty_snapshot,
        force=force,
    )
