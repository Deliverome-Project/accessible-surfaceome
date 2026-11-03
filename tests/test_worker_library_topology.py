"""The Worker must serve library members their OWN topology, never the canonical.

A library member's protein is its designed CDS translated -- an Ensembl-transcript
product. For a substantial minority of members that is a different protein from the
gene's canonical UniProt sequence (816 of 5,896 resolved members sit in
``human_isoforms``; 119 of the 121 whose AlphaFold model was the wrong protein did).
Colouring such a member's structure with ``canonical_topology`` offsets the overlay
silently, with a plausible length and a plausible helix count -- so the regressions worth
guarding are all "looks fine, is wrong":

* resolving the member's topology by accession instead of through the pointer table;
* a column rename in the schema quietly breaking the Worker's SELECT;
* ``libtopo`` emitted as 0, which the UI cannot tell from "not a library gene";
* indexing a v2 string as if it were the v1 one the viewer colours by.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"
SCHEMA = ROOT / "cloudflare/d1_public_schema.sql"
UPLOADER = ROOT / "scripts/cloud/upload_library_topology_to_d1.py"
TABLE = "library_topology_public"


def _worker() -> str:
    return WORKER.read_text()


def _library_topology_query() -> str:
    """The Worker's single SELECT against the pointer table."""
    src = _worker()
    start = src.index(f"FROM {TABLE} lt")
    # Walk back to the SELECT that opens the statement, forward to its closing backtick.
    open_q = src.rindex("`SELECT", 0, start)
    close_q = src.index("`", start)
    return src[open_q:close_q]


def _schema_columns(table: str) -> set[str]:
    text = SCHEMA.read_text()
    block = text[text.index(f"CREATE TABLE IF NOT EXISTS {table}") :]
    block = block[: block.index(");")]
    cols = set()
    for line in block.splitlines()[1:]:
        line = line.split("--")[0].strip().rstrip(",")
        if not line or line.upper().startswith(
            ("PRIMARY KEY", "UNIQUE", "FOREIGN KEY")
        ):
            continue
        cols.add(line.split()[0])
    return cols


def test_the_pointer_table_exists_in_the_committed_schema():
    assert f"CREATE TABLE IF NOT EXISTS {TABLE}" in SCHEMA.read_text()


def test_every_pointer_column_the_worker_selects_exists_in_the_schema():
    """A rename in the schema must fail here, not at serve time as a null overlay."""
    q = _library_topology_query()
    selected = set(re.findall(r"\blt\.(\w+)", q))
    assert selected, "found no lt.* columns -- the query shape changed"
    missing = selected - _schema_columns(TABLE)
    assert not missing, (
        f"Worker selects columns absent from the schema: {sorted(missing)}"
    )


def test_every_topology_column_the_worker_selects_exists_in_topology_public():
    q = _library_topology_query()
    selected = set(re.findall(r"\btp\.(\w+)", q))
    assert selected
    missing = selected - _schema_columns("topology_public")
    assert not missing, (
        f"Worker selects topology columns that do not exist: {sorted(missing)}"
    )


def test_the_join_goes_through_the_pointer_not_the_accession():
    """The whole point: match on the stored pointer, never on the gene's accession.

    Joining ``topology_public`` on ``uniprot_acc`` here would re-introduce exactly the
    canonical-vs-ordered mismatch the pointer table exists to remove.
    """
    q = _library_topology_query()
    for part in (
        "tp.cohort = lt.topology_cohort",
        "tp.topology_version = lt.topology_version",
        "tp.uniprot_acc_full = lt.topology_acc",
    ):
        assert part in q, f"join lost its pointer condition: {part!r}"
    assert "human_canonical" not in q, (
        "the library-topology query must not pin a cohort -- the matching row can be in "
        "any cohort, which is why the pointer is stored"
    )
    assert "tp.uniprot_acc =" not in q, (
        "joined topology by accession instead of the pointer"
    )


def test_the_gene_record_field_is_additive_and_separate_from_canonical_topology():
    src = _worker()
    assert "library_designed_topology" in src
    # canonical_topology must still be populated: the current production viewer reads it.
    assert "record.deterministic_features.canonical_topology" in src


def test_row_schema_is_11_and_documents_v11():
    src = _worker()
    assert "row_schema: 11," in src
    assert re.search(r"//\s+v11 =", src), "bumped row_schema without a changelog entry"
    assert "libtopo" in src


def test_libtopo_is_omitted_rather_than_zero():
    """A 0 would be indistinguishable from "not a library gene" in the filter UI."""
    src = _worker()
    for guard in (
        "if (nLibTopo) row.libtopo = nLibTopo;",
        "if (nOrphanLibTopo) row.libtopo = nOrphanLibTopo;",
    ):
        assert guard in src, f"missing truthy guard: {guard!r}"
    assert "row.libtopo = 0" not in src


def test_both_catalog_row_builders_set_libtopo():
    """Otherwise the field depends on which builder a gene happened to come through."""
    assert _worker().count("row.libtopo =") == 2


def test_the_uploader_refuses_anything_but_v1():
    """v1 is the topology of record; the v2 back-projection is lossy."""
    src = UPLOADER.read_text()
    assert "deeptmhmm_v1" in src
    assert "raise SystemExit(" in src
    assert "topology of record" in src


def test_the_pointer_table_is_keyed_on_the_sequence_hash():
    """The hash is the evidence the match was by sequence and not by name."""
    assert "sequence_sha256" in _schema_columns(TABLE)
    assert "lt.sequence_sha256" in _library_topology_query()
