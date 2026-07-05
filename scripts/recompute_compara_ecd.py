"""Recompute ECD %identity/%similarity for EVERY row in the ``compara_ortholog_ecd``
and ``compara_paralog`` cohort tables, with the homology-aligned
``compute_ecd_identity`` that fixes the extracellular-loop index-mispairing bug.

Why this exists alongside ``backfill_ecd_identity.py``: that script fixes the
values baked into the ~890 published deep-dive RECORDS (from each record's own
stored sequences). This one fixes the SOURCE cohort tables — the ~10.8k ortholog
+ ~91k paralog rows a FUTURE deep-dive reads (``d1_deterministic._fetch_orthologs``
/ ``_fetch_paralogs`` read the stored ``ecd_pct_identity``; they do NOT recompute
from topology at annotate time). Without this, every not-yet-deep-dived gene would
inherit the buggy value the moment it's annotated.

Method: load the human-canonical + mouse/cyno-ortholog ``topology_public`` rows
(per-residue topology + sequence, at the version the deep-dive resolves) into an
in-memory dict keyed by UniProt acc — ONCE per DB — then stream the compara rows
JOIN-free (keyset pagination) and join in Python. A server-side double JOIN over
91k rows blows D1's per-query CPU budget; this keeps every query a cheap indexed
scan. ``compute_ecd_identity`` is re-run per row and only rows whose value
actually changes are UPDATE-d (idempotent). The bug only moves a value when the
variant's extracellular-loop count/order differs from the canonical, so most rows
are unchanged. Writes are batched via ``UPDATE ... FROM (VALUES ...)`` (up to
``--chunk`` rows per statement) to avoid one-round-trip-per-row over D1's HTTP API.

Runs against BOTH the private ``surfaceome_agents`` DB (source of truth) and the
``surfaceome_public`` mirror, so a later private→public re-mirror can't clobber
the fix.

``ecd_pct_similarity`` (compara_paralog only) is written back ONLY where a value
already exists — preserving the table's "similarity populated for close pairs
(>=80% full-length) only" convention.

    uv run python scripts/recompute_compara_ecd.py --dry-run
    uv run python scripts/recompute_compara_ecd.py --dry-run --only paralog --limit 3000
    uv run python scripts/recompute_compara_ecd.py --execute
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import httpx

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_ortholog_ecd_version,
    _latest_paralog_version,
    _latest_topology_version_for_cohort,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

logger = logging.getLogger(__name__)
_EPS = 1e-6
PAGE = 8000


def _differs(a, b) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(float(a) - float(b)) > _EPS


def _q(d1: D1Client, sql: str, params: list, *, attempts: int = 6):
    """Query with backoff on transient transport errors."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return d1.query(sql, params)
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last = exc
            time.sleep(0.75 * (i + 1))
    assert last is not None
    raise last


def _load_topology(d1: D1Client, cohort: str, topo_v: str) -> dict[str, tuple[str, str]]:
    """{uniprot_acc: (per_residue_topology, sequence)} for one cohort, keyset-paged."""
    out: dict[str, tuple[str, str]] = {}
    last = ""
    while True:
        rows = _q(d1,
            "SELECT uniprot_acc, per_residue_topology, sequence FROM topology_public "
            "WHERE cohort=? AND topology_version=? AND uniprot_acc>? "
            "ORDER BY uniprot_acc LIMIT ?",
            [cohort, topo_v, last, PAGE])
        if not rows:
            break
        for r in rows:
            out[r["uniprot_acc"]] = (r["per_residue_topology"], r["sequence"])
        last = rows[-1]["uniprot_acc"]
        if len(rows) < PAGE:
            break
    return out


def _write_json(d1: D1Client, table: str, set_assign: str, key_where: str,
                const_params: list, objs: list[dict], chunk: int) -> None:
    """Batch-UPDATE via ``FROM json_each(?)``: the whole batch rides in one JSON
    param, so param count is ~2/statement regardless of batch size (D1 caps bound
    params at 100/query, which an ``UPDATE...FROM(VALUES)`` blows past at ~19 rows).
    ``set_assign``/``key_where`` reference each row via ``json_extract(j.value,'$.k')``.
    """
    total = len(objs)
    for i in range(0, total, chunk):
        batch = objs[i:i + chunk]
        sql = f"UPDATE {table} SET {set_assign} FROM json_each(?) AS j WHERE {key_where}"
        _q(d1, sql, [json.dumps(batch), *const_params])
        if (i // chunk) % 25 == 0:
            logger.info("      ...wrote %d/%d", min(i + chunk, total), total)


def recompute_ortholog(d1: D1Client, topo: dict[str, dict[str, tuple[str, str]]], *,
                       oecd_v: str, dry_run: bool, limit: int | None,
                       chunk: int) -> tuple[int, int]:
    human = topo["human_canonical"]
    by_species = {"mouse": topo["mouse_ortholog"], "cynomolgus": topo["cyno_ortholog"],
                  "cyno": topo["cyno_ortholog"]}
    matched = missing = 0
    changed: list[dict] = []
    last = ("", "", "")
    while True:
        rows = _q(d1,
            "SELECT human_hgnc_id AS hgnc, species AS sp, ortholog_uniprot_acc AS oacc, "
            "  human_uniprot_acc AS huacc, ecd_pct_identity AS old_ecd, "
            "  n_ecd_loops_compared AS old_n "
            "FROM compara_ortholog_ecd "
            "WHERE ortholog_ecd_version=? "
            "  AND (human_hgnc_id, species, ortholog_uniprot_acc) > (?, ?, ?) "
            "ORDER BY human_hgnc_id, species, ortholog_uniprot_acc LIMIT ?",
            [oecd_v, last[0], last[1], last[2], PAGE])
        if not rows:
            break
        for r in rows:
            matched += 1
            h = human.get(r["huacc"])
            o = by_species.get((r["sp"] or "").lower(), {}).get(r["oacc"])
            if not h or not o:
                missing += 1
                continue
            res = compute_ecd_identity(human_topology=h[0], human_sequence=h[1],
                                       paralog_topology=o[0], paralog_sequence=o[1])
            new_ecd, new_n = res.ecd_pct_identity, res.n_ecd_loops_compared
            if _differs(r["old_ecd"], new_ecd) or (r["old_n"] or 0) != (new_n or 0):
                changed.append({"hgnc": r["hgnc"], "sp": r["sp"], "oacc": r["oacc"],
                                "eid": new_ecd, "nl": new_n})
        last = (rows[-1]["hgnc"], rows[-1]["sp"], rows[-1]["oacc"])
        if limit and matched >= limit:
            break
        if len(rows) < PAGE:
            break
    logger.info("  ortholog: matched=%d changed=%d (no-topology=%d)", matched, len(changed), missing)
    if not dry_run and changed:
        _write_json(d1, "compara_ortholog_ecd",
            "ecd_pct_identity=json_extract(j.value,'$.eid'), "
            "n_ecd_loops_compared=json_extract(j.value,'$.nl')",
            "compara_ortholog_ecd.ortholog_ecd_version=? "
            "AND compara_ortholog_ecd.human_hgnc_id=json_extract(j.value,'$.hgnc') "
            "AND compara_ortholog_ecd.species=json_extract(j.value,'$.sp') "
            "AND compara_ortholog_ecd.ortholog_uniprot_acc=json_extract(j.value,'$.oacc')",
            [oecd_v], changed, chunk=chunk)
        logger.info("  ortholog: wrote %d rows", len(changed))
    return matched, len(changed)


def recompute_paralog(d1: D1Client, topo: dict[str, dict[str, tuple[str, str]]], *,
                      para_v: str, has_sim: bool, dry_run: bool, limit: int | None,
                      chunk: int) -> tuple[int, int]:
    """``has_sim``: the private ``compara_paralog`` has no ``ecd_pct_similarity``
    column (only the public mirror does), so it's selected/updated conditionally."""
    human = topo["human_canonical"]
    matched = missing = 0
    changed: list[dict] = []
    last = ("", "")
    sim_sel = "ecd_pct_similarity AS old_sim, " if has_sim else "NULL AS old_sim, "
    while True:
        rows = _q(d1,
            "SELECT human_ensembl_gene AS heg, paralog_ensembl_gene AS peg, "
            "  human_uniprot_acc AS huacc, paralog_uniprot_acc AS puacc, "
            "  ecd_pct_identity AS old_ecd, " + sim_sel +
            "  n_ecd_loops_compared AS old_n "
            "FROM compara_paralog "
            "WHERE paralog_version=? "
            "  AND (human_ensembl_gene, paralog_ensembl_gene) > (?, ?) "
            "ORDER BY human_ensembl_gene, paralog_ensembl_gene LIMIT ?",
            [para_v, last[0], last[1], PAGE])
        if not rows:
            break
        for r in rows:
            matched += 1
            h = human.get(r["huacc"])
            p = human.get(r["puacc"])
            if not h or not p:
                missing += 1
                continue
            res = compute_ecd_identity(human_topology=h[0], human_sequence=h[1],
                                       paralog_topology=p[0], paralog_sequence=p[1])
            new_ecd, new_n = res.ecd_pct_identity, res.n_ecd_loops_compared
            # similarity only where the table has the column AND already carries a
            # value (close pairs); private has no column so it's always skipped.
            new_sim = res.ecd_pct_similarity if (has_sim and r["old_sim"] is not None) else None
            sim_changed = has_sim and _differs(r["old_sim"], new_sim)
            if (_differs(r["old_ecd"], new_ecd) or sim_changed
                    or (r["old_n"] or 0) != (new_n or 0)):
                obj = {"heg": r["heg"], "peg": r["peg"], "eid": new_ecd, "nl": new_n}
                if has_sim:
                    obj["esim"] = new_sim
                changed.append(obj)
        last = (rows[-1]["heg"], rows[-1]["peg"])
        if limit and matched >= limit:
            break
        if len(rows) < PAGE:
            break
    logger.info("  paralog: matched=%d changed=%d (no-topology=%d)", matched, len(changed), missing)
    if not dry_run and changed:
        set_assign = ("ecd_pct_identity=json_extract(j.value,'$.eid'), "
                      "n_ecd_loops_compared=json_extract(j.value,'$.nl')")
        if has_sim:
            set_assign += ", ecd_pct_similarity=json_extract(j.value,'$.esim')"
        _write_json(d1, "compara_paralog", set_assign,
            "compara_paralog.paralog_version=? "
            "AND compara_paralog.human_ensembl_gene=json_extract(j.value,'$.heg') "
            "AND compara_paralog.paralog_ensembl_gene=json_extract(j.value,'$.peg')",
            [para_v], changed, chunk=chunk)
        logger.info("  paralog: wrote %d rows", len(changed))
    return matched, len(changed)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true")
    grp.add_argument("--execute", action="store_true")
    ap.add_argument("--only", choices=["ortholog", "paralog"], default=None)
    ap.add_argument("--db", choices=["private", "public", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None, help="Sample cap per table (for timing).")
    ap.add_argument("--chunk", type=int, default=200, help="Rows per json_each() UPDATE statement.")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()
    topo_v = _latest_topology_version_for_cohort("human_canonical")
    oecd_v = _latest_ortholog_ecd_version()
    para_v = _latest_paralog_version()
    logger.info("versions: topo=%s ortholog_ecd=%s paralog=%s", topo_v, oecd_v, para_v)
    logger.info("mode=%s db=%s only=%s limit=%s\n", "EXECUTE" if args.execute else "DRY-RUN",
                args.db, args.only, args.limit)

    dbs = [("private", D1Config.from_env())] if args.db == "private" else \
          [("public", D1Config.from_env_public())] if args.db == "public" else \
          [("private", D1Config.from_env()), ("public", D1Config.from_env_public())]

    grand = 0
    for label, cfg in dbs:
        logger.info("=== %s D1 ===", label)
        with D1Client(cfg) as d1:
            cohorts = ["human_canonical"]
            if args.only != "paralog":
                cohorts += ["mouse_ortholog", "cyno_ortholog"]
            topo = {c: _load_topology(d1, c, topo_v) for c in cohorts}
            logger.info("  loaded topology: %s", {c: len(v) for c, v in topo.items()})
            if args.only != "paralog":
                _, c = recompute_ortholog(d1, topo, oecd_v=oecd_v,
                                          dry_run=args.dry_run, limit=args.limit, chunk=args.chunk)
                grand += c
            if args.only != "ortholog":
                has_sim = any(r["name"] == "ecd_pct_similarity"
                              for r in _q(d1, "PRAGMA table_info(compara_paralog);", []))
                _, c = recompute_paralog(d1, topo, para_v=para_v, has_sim=has_sim,
                                         dry_run=args.dry_run, limit=args.limit, chunk=args.chunk)
                grand += c
    logger.info("\n%s %d row(s) across selected tables/DBs",
                "wrote" if args.execute else "would change", grand)
    if args.dry_run:
        logger.info("(dry-run — re-run with --execute)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
