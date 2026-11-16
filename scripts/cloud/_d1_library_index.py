"""Shared pieces for the two library index loaders, and the staged swap they use.

``library_structure_public`` and ``library_topology_public`` are REPLACE-IN-PLACE tables:
the Worker's queries carry no ``release`` filter (``WHERE gene_symbol = ?`` and the
topology join), so every row in the table is live to the public viewer the moment it is
written. A loader that DELETEs the old release and then streams ~500-700 batched INSERTs
leaves the gene page with a missing or half-populated structure tab for the minutes that
takes. That is not acceptable for a public page, and it is the reason the load is staged.

``staged_replace`` builds the new content in a scratch table the Worker does not read,
checks its row count there, and only then issues ONE request holding

    DELETE FROM <table> WHERE release = ...;
    INSERT INTO <table> (<cols>) SELECT <cols> FROM <stage>;
    DROP TABLE <stage>;

D1 runs the statements of a request back to back server side, so the window in which the
table is short of its rows is the gap between two statements rather than the length of the
upload. It is not a transaction -- D1 rejects an explicit BEGIN on this endpoint -- so a
failure between them is possible; report the window you measured rather than claiming none.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

API_ROOT = "https://api.cloudflare.com/client/v4"
#: Rows per INSERT. D1 caps bound parameters per query at 100, and each row binds one per
#: column, so the batch is 100 // len(columns).
PARAM_CAP = 100


def query(
    account: str,
    db: str,
    token: str,
    sql: str,
    params: list | None = None,
    *,
    attempts: int = 6,
) -> dict:
    """POST one request to D1, retrying the overload error.

    7429 ("DB is overloaded. Too many resources consumed within a 10 second window") is
    not a failure of the statement -- it is back-pressure, and several sessions share this
    database. Raising on it would abort a load halfway, which for a replace-in-place table
    is the one outcome worth engineering against.
    """
    body = json.dumps({"sql": sql, "params": params or []}).encode()
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(
            f"{API_ROOT}/accounts/{account}/d1/database/{db}/query",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.load(resp)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode()[:600]
            if "7429" in text and attempt + 1 < attempts:
                time.sleep(5 * (attempt + 1))
                last = text
                continue
            raise SystemExit(f"D1 query failed: {exc.code} {text}") from exc
        codes = {e.get("code") for e in (out.get("errors") or [])}
        if 7429 in codes and attempt + 1 < attempts:
            time.sleep(5 * (attempt + 1))
            last = json.dumps(out.get("errors"))
            continue
        if not out.get("success"):
            raise SystemExit(f"D1 query failed: {json.dumps(out.get('errors'))[:600]}")
        return out
    raise SystemExit(f"D1 still overloaded after {attempts} attempts: {last}")


def rows_of(out: dict) -> list[dict]:
    return (out.get("result") or [{}])[0].get("results") or []


def ddl_from_schema(
    schema_text: str, table: str, last_statement_startswith: str
) -> str:
    """The CREATE statements for one table, read from the committed schema file.

    Taking them from the schema rather than restating them in the loader is what keeps the
    file and the database from drifting: the repo's rule is to fix the records and re-sync,
    never to let a loader carry its own private idea of the shape.
    """
    start = schema_text.index(f"CREATE TABLE IF NOT EXISTS {table}")
    tail = schema_text[start:]
    end = tail.rindex(last_statement_startswith)
    end = tail.index(";", end) + 1
    block = tail[:end]
    # Strip `--` comments before the caller splits on ";". The column comments contain
    # semicolons of their own ("-- denormalized; never a join key"), and splitting the raw
    # text chopped the CREATE TABLE into fragments D1 rejected as "incomplete input".
    return "\n".join(line.split("--")[0].rstrip() for line in block.splitlines())


def staged_replace(
    account: str,
    db: str,
    token: str,
    *,
    table: str,
    cols: list[str],
    rows: list[dict],
    releases: list[str],
    progress: bool = True,
) -> float:
    """Replace ``releases`` in ``table`` with ``rows``. Returns the swap duration, seconds.

    The stage table is created from the live one with ``WHERE 0``, so its column types
    follow the live table and cannot drift from it. ``synced_at`` is deliberately not
    among ``cols``: the final INSERT omits it so the live table's own default stamps the
    new rows with the time of the swap.
    """
    stage = f"{table}__stage"
    collist = ", ".join(cols)
    # The swap interpolates the release into SQL (a bound parameter cannot be mixed into a
    # multi-statement request here), so the release must be a plain identifier-ish string.
    for r in releases:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", r):
            raise SystemExit(f"refusing to interpolate release {r!r} into SQL")
    query(account, db, token, f"DROP TABLE IF EXISTS {stage}")
    query(
        account,
        db,
        token,
        f"CREATE TABLE {stage} AS SELECT {collist} FROM {table} WHERE 0",
    )

    batch = max(1, PARAM_CAP // len(cols))
    one = "(" + ", ".join("?" for _ in cols) + ")"
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        sql = f"INSERT INTO {stage} ({collist}) VALUES " + ", ".join(one for _ in chunk)
        params: list = []
        for r in chunk:
            params.extend((r[c] if r[c] != "" else None) for c in cols)
        query(account, db, token, sql, params)
        if progress:
            print(
                f"  staged {min(i + batch, len(rows))}/{len(rows)}",
                end="\r",
                flush=True,
            )
    staged = rows_of(query(account, db, token, f"SELECT COUNT(*) AS n FROM {stage}"))
    n = int(staged[0]["n"])
    if n != len(rows):
        raise SystemExit(
            f"refusing to swap: staged {n} rows in {stage} but the payload has {len(rows)}"
        )
    print(f"\n  staged {n} row(s) in {stage}; swapping")

    swap = ";\n".join(
        [
            *(f"DELETE FROM {table} WHERE release = '{r}'" for r in releases),
            f"INSERT INTO {table} ({collist}) SELECT {collist} FROM {stage}",
            f"DROP TABLE {stage}",
        ]
    )
    t0 = time.monotonic()
    query(account, db, token, swap)
    return time.monotonic() - t0
