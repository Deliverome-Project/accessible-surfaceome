"""Pin every served ortholog and paralog row to Ensembl Compara release 115.

Why: BioMart (``www.ensembl.org/biomart``) always serves the *current*
Ensembl release and none of our pulls recorded which one. The 2026-05-12,
2026-05-16 and 2026-06-01 pulls fell in release 115 (2 Sep 2025 – 9 Jun
2026); the 2026-09-20 intracellular-rescue and 2026-09-21 gap-fill pulls
got release 116. The manuscript cites release 115, so this consolidates
everything onto one release under one label, ``ensembl_compara_115``.

Release 115's archived BioMart (sep2025.archive.ensembl.org) returns 502,
so the 203 genes added on 2026-09-20/21 are re-sourced from Ensembl's
release-115 FTP homology dumps instead. Those dumps list each species pair
once: human–cynomolgus (and human–human paralogs) in the human file,
human–mouse in the mouse file. Their human-side ``identity`` matches what
BioMart reported as ``perc_id`` exactly (checked against all 92 ortholog
and 549 paralog rows we already held from release 115).

What it does, on private and public D1 alike:

1. ``compara_ortholog``: copy the release-115 rows (``ensembl_compara_2026_05_12``
   and ``ensembl_compara_2026_06_01_v2bf``) to ``ensembl_compara_115`` for every
   gene except the 203 new ones, then insert the new genes' one-to-one,
   high-confidence pairs from the dumps; delete the release-116 rows.
2. ``compara_ortholog_ecd``: point every row at ``ensembl_compara_115``, and drop
   rows whose pair is not a one-to-one high-confidence ortholog in 115.
3. ``compara_paralog``: rewrite the new genes' release-116 paralog identity and
   type to their release-115 values, drop pairs absent from 115, and relabel
   every row ``ensembl_compara_115`` (paralog ECD identity depends only on
   topology and sequence, so it is unchanged).
4. Registry rows: add ``ensembl_compara_115``; the dated labels become
   superseded.

Ortholog pairs that are new in 115 have no ECD row yet (their ortholog
topology would need a DeepTMHMM prediction); they are reported, not invented.

Records are not touched here: republish the affected genes afterwards so the
baked ``deterministic_features`` pick this up, then sweep record history.

    uv run python scripts/cloud/consolidate_compara_release_115.py            # dry-run
    uv run python scripts/cloud/consolidate_compara_release_115.py --execute
"""

from __future__ import annotations

import argparse
import csv
import gzip
from datetime import UTC, datetime

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

LABEL = "ensembl_compara_115"
RELEASE_115_LABELS = ("ensembl_compara_2026_05_12", "ensembl_compara_2026_06_01_v2bf")
RELEASE_116_LABELS = (
    "ensembl_compara_2026_09_20_rescue",
    "ensembl_compara_2026_09_21_gapfill",
)
NEW_COHORTS = ("intracellular_rescue_v1_sonnet_2026_09", "universe_gapfill_2026_09")
FTP = "https://ftp.ensembl.org/pub/release-115/tsv/ensembl-compara/homologies"
DUMP_DIR = REPO_ROOT / "data/external/blob_cache/ensembl_compara_115"
HUMAN_DUMP = DUMP_DIR / "Compara.115.protein_default.homologies.tsv.gz"
MOUSE_DUMP = DUMP_DIR / "mus_musculus.Compara.115.protein_default.homologies.tsv.gz"
SCRATCH = "_scratch_paralog_r115"


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _new_genes(pub: D1Client) -> list[dict]:
    """The 203 genes whose orthologs and paralogs came from release 116."""
    rows = pub.query(
        "SELECT a.gene_symbol AS symbol, gi.hgnc_id, gi.ensembl_gene, gi.uniprot_acc "
        "FROM surface_annotation a JOIN gene_identifier_public gi "
        "  ON gi.hgnc_id = json_extract(a.annotation_json, '$.gene.hgnc_id') "
        f"WHERE a.cohort_run_id IN ({','.join('?' * len(NEW_COHORTS))});",
        list(NEW_COHORTS),
    )
    missing = [r["symbol"] for r in rows if not r["ensembl_gene"]]
    if missing:
        raise SystemExit(f"no Ensembl gene for {missing}; fix gene_identifier first")
    return rows


def _read_dumps(ens: set[str]) -> tuple[dict, dict]:
    """Release-115 orthologs (1:1, high confidence) and paralogs for ``ens``.

    Identities are always the human gene's side, matching BioMart's perc_id.
    """
    for p in (HUMAN_DUMP, MOUSE_DUMP):
        if not p.exists():
            raise SystemExit(f"missing {p}; download from {FTP}/")
    orth: dict[tuple, dict] = {}
    para: dict[tuple, dict] = {}
    with gzip.open(HUMAN_DUMP, "rt") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            a, b, sp = (
                r["gene_stable_id"],
                r["homology_gene_stable_id"],
                r["homology_species"],
            )
            if sp == "macaca_fascicularis" and a in ens:
                if (
                    r["homology_type"] == "ortholog_one2one"
                    and r["is_high_confidence"] == "1"
                ):
                    orth[(a, "cynomolgus", b)] = {
                        "pct": float(r["identity"]),
                        "type": r["homology_type"],
                    }
            elif sp == "homo_sapiens":
                if a in ens:
                    para[(a, b)] = {
                        "pct": float(r["identity"]),
                        "type": r["homology_type"],
                    }
                if b in ens:
                    para[(b, a)] = {
                        "pct": float(r["homology_identity"]),
                        "type": r["homology_type"],
                    }
    with gzip.open(MOUSE_DUMP, "rt") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            h = r["homology_gene_stable_id"]
            if r["homology_species"] == "homo_sapiens" and h in ens:
                if (
                    r["homology_type"] == "ortholog_one2one"
                    and r["is_high_confidence"] == "1"
                ):
                    orth[(h, "mouse", r["gene_stable_id"])] = {
                        "pct": float(r["homology_identity"]),
                        "type": r["homology_type"],
                    }
    return orth, para


def _apply(
    d1: D1Client, name: str, genes: list[dict], orth: dict, para: dict, execute: bool
) -> None:
    ens = [g["ensembl_gene"] for g in genes]
    by_ens = {g["ensembl_gene"]: g for g in genes}
    q = (
        (lambda sql, params=(): d1.query(sql, list(params)))
        if execute
        else (lambda sql, params=(): None)
    )
    marks = lambda xs: ",".join("?" * len(xs))  # noqa: E731

    # Symbols / UniProt for the new genes' ortholog rows, reused where the
    # release-116 row already carried them.
    known: dict[tuple, dict] = {}
    for ch in _chunks(ens, 90):
        for r in d1.query(
            "SELECT human_ensembl_gene, species, ortholog_ensembl_gene, ortholog_uniprot_acc, "
            f"ortholog_gene_symbol FROM compara_ortholog WHERE human_ensembl_gene IN ({marks(ch)});",
            ch,
        ):
            known[
                (r["human_ensembl_gene"], r["species"], r["ortholog_ensembl_gene"])
            ] = r

    print(f"[{name}] new genes: {len(genes)}; 115 ortholog pairs for them: {len(orth)}")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    q(
        "INSERT OR REPLACE INTO compara_release (release_version, fetched_at, n_pairs, source_url, notes) "
        "VALUES (?, ?, 0, ?, ?);",
        [
            LABEL,
            now,
            f"{FTP}/",
            "Ensembl release 115 for every gene. Rows from the 2026-05-12 and 2026-06-01 BioMart pulls "
            "(release 115 at the time) plus release-115 FTP homology dumps for the 203 genes added "
            "2026-09-20/21, whose original pulls got release 116.",
        ],
    )
    # 1. Orthologs.
    q(
        "INSERT OR IGNORE INTO compara_ortholog SELECT ?, human_ensembl_gene, human_uniprot_acc, "
        "human_gene_symbol, species, ortholog_ensembl_gene, ortholog_uniprot_acc, ortholog_gene_symbol, "
        "orthology_type, percent_identity, is_high_confidence FROM compara_ortholog "
        f"WHERE release_version IN ({marks(RELEASE_115_LABELS)});",
        [LABEL, *RELEASE_115_LABELS],
    )
    # The new genes take their values from the dump, not from any earlier row.
    for ch in _chunks(ens, 90):
        q(
            f"DELETE FROM compara_ortholog WHERE release_version = ? AND human_ensembl_gene IN ({marks(ch)});",
            [LABEL, *ch],
        )
    rows = []
    for (h, sp, o), v in sorted(orth.items()):
        g, k = by_ens[h], known.get((h, sp, o), {})
        rows.append(
            [
                LABEL,
                h,
                g["uniprot_acc"],
                g["symbol"],
                sp,
                o,
                k.get("ortholog_uniprot_acc"),
                k.get("ortholog_gene_symbol"),
                v["type"],
                v["pct"],
                1,
            ]
        )
    for ch in _chunks(rows, 9):  # 11 columns; D1 binds at most 100 parameters
        q(
            "INSERT INTO compara_ortholog VALUES "
            + ",".join(["(" + marks(r) + ")" for r in ch])
            + ";",
            [x for r in ch for x in r],
        )
    q(
        f"DELETE FROM compara_ortholog WHERE release_version IN ({marks(RELEASE_116_LABELS)});",
        list(RELEASE_116_LABELS),
    )
    q(
        "UPDATE compara_release SET n_pairs = (SELECT COUNT(*) FROM compara_ortholog WHERE release_version = ?) "
        "WHERE release_version = ?;",
        [LABEL, LABEL],
    )

    # 2. Ortholog ECD rows: drop pairs that are not 1:1 high-confidence in 115,
    #    then point the rest at the consolidated release.
    # Every ECD row whose pair is not a release-115 1:1 high-confidence ortholog
    # is dropped. For the established genes that set is their existing 115
    # rows; for the new genes it is the dump.
    ecd = d1.query(
        "SELECT human_ensembl_gene h, human_gene_symbol g, species s, ortholog_ensembl_gene o "
        "FROM compara_ortholog_ecd;",
        [],
    )
    base = {
        (r["human_ensembl_gene"], r["species"], r["ortholog_ensembl_gene"])
        for r in d1.query(
            "SELECT DISTINCT human_ensembl_gene, species, ortholog_ensembl_gene FROM compara_ortholog "
            f"WHERE release_version IN ({marks(RELEASE_115_LABELS)});",
            list(RELEASE_115_LABELS),
        )
    }
    new_set = set(ens)

    def keep(r: dict) -> bool:
        pair = (r["h"], r["s"], r["o"])
        return pair in orth if r["h"] in new_set else pair in base

    gone = [r for r in ecd if not keep(r)]
    print(
        f"[{name}] ortholog ECD rows: {len(ecd)}; dropped (not 1:1 high-confidence in 115): "
        f"{len(gone)} {sorted({(r['g'], r['s']) for r in gone})}"
    )
    exists_115 = (
        "EXISTS (SELECT 1 FROM compara_ortholog co WHERE co.release_version = ? "
        "AND co.human_ensembl_gene = compara_ortholog_ecd.human_ensembl_gene "
        "AND co.species = compara_ortholog_ecd.species "
        "AND co.ortholog_ensembl_gene = compara_ortholog_ecd.ortholog_ensembl_gene)"
    )
    q(f"DELETE FROM compara_ortholog_ecd WHERE NOT {exists_115};", [LABEL])
    q("UPDATE compara_ortholog_ecd SET compara_release = ?;", [LABEL])

    # 3. Paralogs: rewrite the new genes' rows to release-115 values via a
    #    scratch table (one bulk load + one correlated UPDATE, not ~1k calls).
    cur = []
    for ch in _chunks(ens, 90):
        cur += d1.query(
            "SELECT human_ensembl_gene, paralog_ensembl_gene FROM compara_paralog "
            f"WHERE compara_version IN ({marks(RELEASE_116_LABELS)}) AND human_ensembl_gene IN ({marks(ch)});",
            [*RELEASE_116_LABELS, *ch],
        )
    # The rescue genes' paralogs sit under more than one paralog_version, so
    # the same pair can appear twice; the scratch table needs one row per pair.
    upd = [
        [h, p, para[(h, p)]["pct"], para[(h, p)]["type"]]
        for h, p in sorted(
            {(r["human_ensembl_gene"], r["paralog_ensembl_gene"]) for r in cur}
        )
        if (h, p) in para
    ]
    dropped = [
        r
        for r in cur
        if (r["human_ensembl_gene"], r["paralog_ensembl_gene"]) not in para
    ]
    print(
        f"[{name}] release-116 paralog rows for new genes: {len(cur)}; "
        f"rewritten to 115: {len(upd)}; absent from 115 (dropped): {len(dropped)}"
    )
    q(f"DROP TABLE IF EXISTS {SCRATCH};")
    q(
        f"CREATE TABLE {SCRATCH} (h TEXT, p TEXT, pct REAL, typ TEXT, PRIMARY KEY (h, p));"
    )
    for ch in _chunks(upd, 25):
        q(
            f"INSERT INTO {SCRATCH} VALUES " + ",".join(["(?,?,?,?)"] * len(ch)) + ";",
            [x for r in ch for x in r],
        )
    match = "s.h = compara_paralog.human_ensembl_gene AND s.p = compara_paralog.paralog_ensembl_gene"
    q(
        f"UPDATE compara_paralog SET "
        f"biomart_percent_identity = (SELECT s.pct FROM {SCRATCH} s WHERE {match}), "
        f"paralogy_type = (SELECT s.typ FROM {SCRATCH} s WHERE {match}), "
        f"is_high_confidence = (SELECT CASE s.typ WHEN 'within_species_paralog' THEN 1 ELSE 0 END "
        f"  FROM {SCRATCH} s WHERE {match}) "
        f"WHERE EXISTS (SELECT 1 FROM {SCRATCH} s WHERE {match});"
    )
    q(f"DROP TABLE IF EXISTS {SCRATCH};")
    for r in dropped:
        q(
            f"DELETE FROM compara_paralog WHERE compara_version IN ({marks(RELEASE_116_LABELS)}) "
            "AND human_ensembl_gene = ? AND paralog_ensembl_gene = ?;",
            [*RELEASE_116_LABELS, r["human_ensembl_gene"], r["paralog_ensembl_gene"]],
        )
    q("UPDATE compara_paralog SET compara_version = ?;", [LABEL])
    q("UPDATE compara_paralog_release SET compara_release = ?;", [LABEL])

    # 4. Older labels are superseded; their ortholog rows stay for history
    #    except the release-116 ones deleted above.
    q(
        "UPDATE compara_release SET notes = COALESCE(notes, '') || ' Superseded by ensembl_compara_115.' "
        "WHERE release_version != ? AND COALESCE(notes, '') NOT LIKE '%Superseded%';",
        [LABEL],
    )

    have_ecd = {(r["h"], r["s"], r["o"]) for r in ecd}
    no_ecd = sorted(
        (by_ens[h]["symbol"], sp) for h, sp, o in orth if (h, sp, o) not in have_ecd
    )
    print(
        f"[{name}] 115 ortholog pairs with no ECD row yet (need ortholog topology): {no_ecd}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--execute", action="store_true", help="write to D1 (default: dry-run)"
    )
    args = ap.parse_args()
    load_env()
    with D1Client(D1Config.from_env_public()) as pub:
        genes = _new_genes(pub)
    orth, para = _read_dumps({g["ensembl_gene"] for g in genes})
    for name, cfg in (
        ("private", D1Config.from_env()),
        ("public", D1Config.from_env_public()),
    ):
        with D1Client(cfg) as d1:
            _apply(d1, name, genes, orth, para, args.execute)
    if not args.execute:
        print("dry-run — pass --execute to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
