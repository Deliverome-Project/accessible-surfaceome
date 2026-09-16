"""Populate public D1's ``paper_metadata`` table from NCBI E-utilities.

Why this exists
---------------
A ``surface_annotation`` record cites its papers by accession only. The
agent writes ``SourceRef.title`` as a *placeholder equal to the id*
("PMC:PMC6199259"), and the schema carries no author / journal / year
fields at all — so the viewer's evidence drawer could only ever show a
bare accession next to the verbatim quote. This table is the citation
metadata that turns that into a readable reference line.

It is the "Worker-enriches" half of the standard deterministic-feature
pattern (see CLAUDE.md): the annotator bakes the identifier into the
record, the Worker joins the metadata in at serve time. Refreshing
metadata therefore never requires re-annotating a gene.

What it does
------------
1. Sweeps every distinct ``SourceRef.source_id`` out of public D1's
   ``surface_annotation.annotation_json`` (chunked ``json_each`` over
   ``$.evidence[*].spans[*].source``) — ~53.6k papers across the 5,130
   published records, split ~40.7k PMC / ~12.9k PMID.
2. Fetches citation metadata in batches of 200 ids from E-utilities
   ``esummary`` — ``db=pmc`` for ``PMC:`` ids, ``db=pubmed`` for
   ``PMID:`` ids. Both return title, authors, journal, pubdate and the
   cross-reference id set, so one call per batch is enough.
3. UPSERTs into ``paper_metadata``, keyed on the verbatim ``source_id``
   so the Worker joins on the string it already holds.

Idempotent. Re-run it after any deep-dive sweep that adds papers;
``--only-missing`` (the default) skips ids already in the table, so a
refresh after a sweep costs only the new papers.

Usage::

    uv run python scripts/build/build_paper_metadata_table.py            # dry-run
    uv run python scripts/build/build_paper_metadata_table.py --execute  # write
    uv run python scripts/build/build_paper_metadata_table.py --limit 400 --execute
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.ncbi import add_ncbi_api_key_param

ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# E-utilities' documented ceiling for a GET id list. 200 × ~9 chars keeps
# the URL well inside any proxy's length limit while holding the whole
# cohort to ~270 requests.
BATCH_SIZE = 200

# Genes per D1 query during the source-id sweep. The `json_each` join
# expands one row into a few hundred spans, so this bounds the per-query
# working set well under D1's isolate cap (measured: 150 genes ≈ 0.3 s).
SWEEP_CHUNK = 150

# Rows per multi-VALUES INSERT. D1 caps a query at 100 bound parameters
# (SQLITE_ERROR "too many SQL variables" above that), so 12 columns × 8
# rows = 96 is the widest legal batch. Still 8× fewer round trips than a
# row-at-a-time UPSERT, which matters at ~53.6k papers.
UPSERT_CHUNK = 8

# NCBI caches hard and citation metadata is effectively immutable, so a
# long TTL keeps re-runs free on a warm cache.
CACHE_TTL_DAYS = 180

_SWEEP_SQL = """
SELECT DISTINCT json_extract(sp.value,'$.source.source_id') AS sid
  FROM (SELECT annotation_json aj FROM surface_annotation
         ORDER BY gene_symbol LIMIT ? OFFSET ?) r,
       json_each(r.aj,'$.evidence') ev,
       json_each(ev.value,'$.spans') sp
 WHERE sid IS NOT NULL;
"""

# A trailing token of bare initials ("Bock C", "van der Berg AB"). Used to
# recover the surname for the reader-facing byline without mangling
# compound surnames, which keep every token but the initials.
_INITIALS_RE = re.compile(r"\s+[A-Z][A-Za-z]{0,3}$")

# NCBI titles carry light inline markup (<i>, <sub>, <sup>) and a trailing
# period that reads wrong inside a citation line.
_TAG_RE = re.compile(r"<[^>]+>")


def _sweep_source_ids(d1: D1Client, *, total_rows: int) -> list[str]:
    """Every distinct ``SourceRef.source_id`` across published records."""

    seen: set[str] = set()
    offset = 0
    while offset < total_rows:
        for row in d1.query(_SWEEP_SQL, [SWEEP_CHUNK, offset]):
            sid = row.get("sid")
            if sid:
                seen.add(sid)
        offset += SWEEP_CHUNK
    return sorted(seen)


def _existing_source_ids(d1: D1Client) -> set[str]:
    """Source ids already carrying metadata, for ``--only-missing``.

    Paged rather than a single SELECT: the table grows past what one D1
    response comfortably returns once the whole cohort is loaded.
    """

    out: set[str] = set()
    offset = 0
    page = 5000
    while True:
        rows = d1.query(
            "SELECT source_id FROM paper_metadata ORDER BY source_id LIMIT ? OFFSET ?;",
            [page, offset],
        )
        if not rows:
            return out
        out.update(r["source_id"] for r in rows if r.get("source_id"))
        if len(rows) < page:
            return out
        offset += page


def _split_by_db(source_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Partition into (pmc ids, pmid ids, unrecognized), prefix intact."""

    pmc, pmid, other = [], [], []
    for sid in source_ids:
        if sid.startswith("PMC:"):
            pmc.append(sid)
        elif sid.startswith("PMID:"):
            pmid.append(sid)
        else:
            other.append(sid)
    return pmc, pmid, other


def _numeric_uid(source_id: str) -> str:
    """The bare uid E-utilities wants: 'PMC:PMC6199259' → '6199259'."""

    raw = source_id.split(":", 1)[1] if ":" in source_id else source_id
    return raw[3:] if raw.upper().startswith("PMC") else raw


def _clean_title(raw: str | None) -> str | None:
    if not raw:
        return None
    title = _TAG_RE.sub("", raw).strip()
    # One trailing period only — "et al." style abbreviations don't end
    # titles, but "…in vivo." does, and "?" / "]" endings must survive.
    if title.endswith("."):
        title = title[:-1]
    return title or None


def _surname(author_name: str) -> str:
    """'Bock C' → 'Bock'. Collective names pass through unchanged."""

    return _INITIALS_RE.sub("", author_name.strip()).strip() or author_name.strip()


def _authors_short(names: list[str]) -> str | None:
    """Reader-facing byline. One author stands alone, two are joined, and
    three or more collapse to 'first et al.' — the shape a citation line
    wants inside a drawer that also has to fit a title and a quote."""

    if not names:
        return None
    if len(names) == 1:
        return _surname(names[0])
    if len(names) == 2:
        return f"{_surname(names[0])} & {_surname(names[1])}"
    return f"{_surname(names[0])} et al."


def _year(pubdate: str | None) -> int | None:
    if not pubdate:
        return None
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", pubdate)
    return int(m.group(1)) if m else None


def _article_ids(docsum: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in docsum.get("articleids") or []:
        idtype = entry.get("idtype")
        value = entry.get("value")
        if idtype and value:
            out[idtype] = str(value)
    return out


def _row_from_docsum(source_id: str, docsum: dict[str, Any], db: str) -> dict[str, Any]:
    ids = _article_ids(docsum)
    names = [
        str(a.get("name"))
        for a in (docsum.get("authors") or [])
        if a.get("name")
    ]
    pubdate = docsum.get("sortpubdate") or docsum.get("pubdate") or docsum.get("epubdate")
    return {
        "source_id": source_id,
        # db=pubmed reports its own uid under 'pubmed'; db=pmc under 'pmid'.
        "pmid": ids.get("pmid") or ids.get("pubmed"),
        "pmc_id": ids.get("pmcid"),
        "doi": ids.get("doi"),
        "title": _clean_title(docsum.get("title")),
        "authors_short": _authors_short(names),
        "authors_json": json.dumps(names, ensure_ascii=False) if names else None,
        "n_authors": len(names) or None,
        # 'source' is NCBI's NLM abbreviation ('Sci Rep'), which is what a
        # compact citation line wants; 'fulljournalname' is the long form.
        "journal": docsum.get("source") or docsum.get("fulljournalname") or None,
        "year": _year(pubdate),
        "pub_date": docsum.get("pubdate") or None,
        "source_db": db,
    }


def _fetch_batch(http: Any, source_ids: list[str], db: str) -> list[dict[str, Any]]:
    """One esummary call for up to ``BATCH_SIZE`` ids of a single db."""

    by_uid = {_numeric_uid(sid): sid for sid in source_ids}
    params: dict[str, Any] = {
        "db": db,
        "id": ",".join(by_uid),
        "retmode": "json",
    }
    add_ncbi_api_key_param(params)
    payload = http.get_json(
        ESUMMARY, source=f"ncbi_esummary_{db}", ttl_days=CACHE_TTL_DAYS, params=params
    )
    result = (payload or {}).get("result") or {}
    rows = []
    for uid in result.get("uids") or []:
        docsum = result.get(uid)
        source_id = by_uid.get(str(uid))
        if not isinstance(docsum, dict) or not source_id:
            continue
        # NCBI reports a bad uid as a docsum carrying only an error string.
        if docsum.get("error"):
            continue
        rows.append(_row_from_docsum(source_id, docsum, db))
    return rows


_COLUMNS = (
    "source_id", "pmid", "pmc_id", "doi", "title", "authors_short",
    "authors_json", "n_authors", "journal", "year", "pub_date", "source_db",
)

_UPDATE_CLAUSE = ",\n            ".join(
    f"{c} = excluded.{c}" for c in _COLUMNS if c != "source_id"
)


def _upsert_chunk(d1: D1Client, chunk: list[dict[str, Any]]) -> int:
    tuples = ",".join(["(" + ",".join(["?"] * len(_COLUMNS)) + ")"] * len(chunk))
    sql = (
        f"INSERT INTO paper_metadata ({', '.join(_COLUMNS)}) VALUES {tuples}\n"
        f"ON CONFLICT(source_id) DO UPDATE SET\n            {_UPDATE_CLAUSE},\n"
        f"            fetched_at = datetime('now');"
    )
    params: list[Any] = []
    for r in chunk:
        params.extend(r[c] for c in _COLUMNS)
    d1.query(sql, params)
    return len(chunk)


def _upsert(d1: D1Client, rows: list[dict[str, Any]], *, workers: int) -> int:
    """Chunked multi-VALUES UPSERT keyed on ``source_id``.

    Two layers of batching, both forced by D1's HTTP API. It takes one
    statement per call, so rows are packed into the widest legal
    multi-VALUES INSERT (see ``UPSERT_CHUNK``); even so a full cohort load
    is ~6.7k calls, which is an hour serial. The calls are independent
    UPSERTs on distinct keys, so they're issued from a small thread pool.
    ``httpx.Client`` is thread-safe and the retrying D1 client is
    idempotent here (ON CONFLICT DO UPDATE), so a retried call can't
    double-apply.
    """

    chunks = [rows[i : i + UPSERT_CHUNK] for i in range(0, len(rows), UPSERT_CHUNK)]
    written = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_upsert_chunk, d1, c) for c in chunks]
        for fut in as_completed(futures):
            written += fut.result()
            print(f"  UPSERT {written}/{len(rows)}", end="\r", flush=True)
    print()
    return written


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--execute", action="store_true",
                    help="Actually UPSERT into public D1. Without this, fetches "
                         "metadata and reports coverage but doesn't write.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only process N source ids (smoke-test).")
    ap.add_argument("--workers", type=int, default=8,
                    help="Concurrent D1 UPSERT calls (default 8).")
    ap.add_argument("--all", dest="only_missing", action="store_false",
                    help="Refetch every source id, not just the ones missing "
                         "from paper_metadata (use after a formatting change).")
    args = ap.parse_args()

    load_env()

    with D1Client.public() as d1:
        total = d1.query("SELECT COUNT(*) AS c FROM surface_annotation;", [])[0]["c"]
        print(f"surface_annotation rows: {total}")

        t0 = time.time()
        source_ids = _sweep_source_ids(d1, total_rows=int(total))
        print(f"distinct cited papers: {len(source_ids)}  ({time.time() - t0:.1f}s)")

        if args.only_missing:
            have = _existing_source_ids(d1)
            source_ids = [s for s in source_ids if s not in have]
            print(f"already in paper_metadata: {len(have)} → {len(source_ids)} to fetch")

        if args.limit:
            source_ids = source_ids[: args.limit]
            print(f"--limit {args.limit} → {len(source_ids)} source ids")

        pmc, pmid, other = _split_by_db(source_ids)
        print(f"  PMC: {len(pmc)}   PMID: {len(pmid)}   unrecognized: {len(other)}")
        if other:
            print(f"  (skipping unrecognized prefixes, e.g. {other[:3]})")

        fetched: list[dict[str, Any]] = []
        with open_default_client() as http:
            for db, ids in (("pmc", pmc), ("pubmed", pmid)):
                for start in range(0, len(ids), BATCH_SIZE):
                    batch = ids[start : start + BATCH_SIZE]
                    try:
                        fetched.extend(_fetch_batch(http, batch, db))
                    except Exception as exc:  # noqa: BLE001 — one bad batch
                        # must not sink a 270-request run; the ids stay
                        # missing and the next run retries them.
                        print(f"  !! {db} batch at {start} failed: {exc}")
                    done = start + len(batch)
                    print(f"  {db}: {done}/{len(ids)} ids → {len(fetched)} rows",
                          end="\r", flush=True)
                if ids:
                    print()

        with_title = sum(1 for r in fetched if r["title"])
        with_authors = sum(1 for r in fetched if r["authors_short"])
        print(f"fetched {len(fetched)} rows "
              f"({with_title} with title, {with_authors} with authors)")
        if source_ids:
            print(f"coverage: {len(fetched)}/{len(source_ids)} "
                  f"({100 * len(fetched) / len(source_ids):.1f}%)")
        for r in fetched[:3]:
            print(f"  e.g. {r['source_id']}: {r['authors_short']}, "
                  f"{r['journal']} {r['year']} — {r['title']}")

        if not args.execute:
            print(f"(dry-run) would UPSERT {len(fetched)} rows — pass --execute")
            return 0

    # Writes go to the public mirror, which `D1Client.public()` opens
    # read-only by convention; reopen with an explicit public config.
    from accessible_surfaceome.cloud.d1_client import D1Config

    with D1Client(D1Config.from_env_public()) as d1w:
        written = _upsert(d1w, fetched, workers=args.workers)
    print(f"UPSERTed {written} rows into paper_metadata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
