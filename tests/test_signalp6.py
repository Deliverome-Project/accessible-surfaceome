"""Parsing SignalP 6 output onto the signalp_public schema."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from accessible_surfaceome.sources import signalp6 as s6

HEADER = "# SignalP-6.0\tOrganism: Eukarya\tTimestamp: 20260928153801\n"


def _shard(tmp_path: Path, results: str, regions: str = "") -> Path:
    d = tmp_path / "s0000"
    d.mkdir()
    (d / "prediction_results.txt").write_text(
        HEADER + textwrap.dedent(results).lstrip("\n")
    )
    (d / "region_output.gff3").write_text(
        "## gff-version 3\n" + textwrap.dedent(regions).lstrip("\n")
    )
    return d


def _regions(acc="A1", n=(1, 4), h=(5, 17), c=(18, 24)):
    return "".join(
        f"{acc}\tSignalP-6.0\t{name}\t{a}\t{b}\t.\t.\t.\t.\n"
        for name, (a, b) in (("n-region", n), ("h-region", h), ("c-region", c))
    )


def test_parses_a_positive_call(tmp_path):
    d = _shard(
        tmp_path, "A1\tSP\t0.000149\t0.999863\tCS pos: 24-25. Pr: 0.9823\n", _regions()
    )
    (call,) = s6.parse_shard(d)
    assert call.prediction == "SP"
    assert call.sp_probability == 0.999863
    # "CS pos: 24-25" means cleavage between 24 and 25, so 24 is the last residue OF the
    # signal peptide -- the same convention as topology_public.signal_peptide_length.
    assert call.cleavage_site == 24
    assert call.cleavage_probability == 0.9823
    assert call.regions["h-region"] == (5, 17)


def test_parses_a_negative_call(tmp_path):
    d = _shard(tmp_path, "A1\tOTHER\t1.000000\t0.000000\t\n")
    (call,) = s6.parse_shard(d)
    assert call.prediction == "OTHER"
    assert call.cleavage_site is None
    assert call.columns()["h_region_start"] is None


def test_c_region_end_must_equal_the_cleavage_site(tmp_path):
    """The two come from different output files; disagreement means corrupt input.

    This check passed for all 5,238 SP calls in the sp6_2026_09_28 run, which is the only
    independent cross-check the tool's own output affords.
    """
    d = _shard(
        tmp_path, "A1\tSP\t0.0\t1.0\tCS pos: 24-25. Pr: 0.98\n", _regions(c=(18, 22))
    )
    with pytest.raises(s6.SignalP6Error, match="c-region ends at 22"):
        s6.parse_shard(d)


def test_sp_call_without_a_cleavage_site_is_refused(tmp_path):
    d = _shard(tmp_path, "A1\tSP\t0.0\t1.0\t\n", _regions())
    with pytest.raises(s6.SignalP6Error, match="called SP with no cleavage site"):
        s6.parse_shard(d)


def test_negative_call_carrying_a_cleavage_site_is_refused(tmp_path):
    d = _shard(tmp_path, "A1\tOTHER\t1.0\t0.0\tCS pos: 24-25. Pr: 0.98\n")
    with pytest.raises(s6.SignalP6Error, match="called OTHER but carries"):
        s6.parse_shard(d)


def test_sp_call_missing_its_region_decomposition_is_refused(tmp_path):
    d = _shard(tmp_path, "A1\tSP\t0.0\t1.0\tCS pos: 24-25. Pr: 0.98\n")
    with pytest.raises(s6.SignalP6Error, match="missing region decomposition"):
        s6.parse_shard(d)


def test_non_adjacent_cleavage_bounds_are_refused(tmp_path):
    d = _shard(tmp_path, "A1\tSP\t0.0\t1.0\tCS pos: 24-27. Pr: 0.98\n", _regions())
    with pytest.raises(s6.SignalP6Error, match="non-adjacent"):
        s6.parse_shard(d)


def test_unparsable_cleavage_field_is_refused_not_ignored(tmp_path):
    d = _shard(tmp_path, "A1\tSP\t0.0\t1.0\tCS somewhere around 24\n", _regions())
    with pytest.raises(s6.SignalP6Error, match="unparsable cleavage field"):
        s6.parse_shard(d)


def test_duplicate_accession_across_shards_is_refused(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    for name in ("s0000", "s0001"):
        d = run / name
        d.mkdir()
        (d / "prediction_results.txt").write_text(HEADER + "A1\tOTHER\t1.0\t0.0\t\n")
        (d / "region_output.gff3").write_text("## gff-version 3\n")
    with pytest.raises(s6.SignalP6Error, match="predicted twice"):
        s6.parse_run(run)


def test_empty_run_directory_is_refused(tmp_path):
    with pytest.raises(s6.SignalP6Error, match="no prediction_results.txt"):
        s6.parse_run(tmp_path)


def test_columns_cover_every_non_identity_column_in_the_schema(tmp_path):
    """The parser and the migration must not drift apart."""
    import re

    sql = (
        Path(__file__).resolve().parents[1] / "cloudflare/migrations/signalp_public.sql"
    ).read_text()
    body = sql[sql.index("CREATE TABLE IF NOT EXISTS signalp_public") :]
    body = body[: body.index("PRIMARY KEY")]
    declared = set(re.findall(r"^\s{4}(\w+)\s", body, re.M))
    d = _shard(
        tmp_path, "A1\tSP\t0.000149\t0.999863\tCS pos: 24-25. Pr: 0.9823\n", _regions()
    )
    produced = set(s6.parse_shard(d)[0].columns())
    assert produced <= declared, sorted(produced - declared)
    # everything the parser is responsible for, i.e. not identity or provenance
    identity = {
        "signalp_version",
        "uniprot_acc_full",
        "uniprot_acc",
        "hgnc_id",
        "gene_symbol",
        "is_canonical",
        "protein_length",
        "organism",
        "mode",
        "tool_version",
        "retrieved_at",
        "synced_at",
    }
    assert declared - identity == produced
