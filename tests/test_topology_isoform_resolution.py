"""Tests for the UniProt-driven human-isoform resolution helpers in
``scripts/run_topology_sweep.py``.

Covers ``_resolve_isoforms_for_candidates`` (happy path, no-isoforms,
error, cache hit) and ``_write_isoform_fastas_to_cache`` (write +
no-overwrite). ``fetch_text_with_retries`` is monkeypatched on the
script module's local binding because ``run_topology_sweep`` does
``from accessible_surfaceome.sources.deeptmhmm import fetch_text_with_retries``
— the import binding lives on the script module.

The script is imported via ``importlib.util.spec_from_file_location``
(same pattern as ``tests/test_triage_runner_schema_enforcement.py``)
so the orchestrator's ``main()`` doesn't execute on test collection.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "build" / "run_topology_sweep.py"


@pytest.fixture(scope="module")
def sweep():
    """Import scripts/run_topology_sweep.py as a module."""
    spec = importlib.util.spec_from_file_location("run_topology_sweep", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_topology_sweep"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_candidate(sweep, *, hgnc_id: str, symbol: str, uniprot_acc: str):
    """Build a Candidate with placeholder ensembl/ncbi fields."""
    return sweep.Candidate(
        hgnc_id=hgnc_id,
        cohort_symbol=symbol,
        uniprot_acc=uniprot_acc,
        ensembl_gene="ENSG00000197122",
        ncbi_gene_id=6714,
        selection_reason="db_only",
        triage_verdict=None,
    )


# ---------------------------------------------------------------------------
# _resolve_isoforms_for_candidates
# ---------------------------------------------------------------------------


def test_happy_path_returns_specs_for_alt_isoforms(sweep, tmp_path, monkeypatch):
    """Single SRC candidate, UniProt returns 3 records → 2 IsoformSpec rows."""
    cache = tmp_path / "isoform_resolution.jsonl"
    candidate = _make_candidate(
        sweep, hgnc_id="HGNC:11283", symbol="SRC", uniprot_acc="P12931",
    )

    fasta_text = (
        ">sp|P12931|SRC_HUMAN canonical\n"
        "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE\n"
        ">sp|P12931-2|SRC_HUMAN isoform 2\n"
        "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE\n"
        "PKLFGGFNSSDTVTSPQRAGPLAGG\n"
        ">sp|P12931-3|SRC_HUMAN isoform 3\n"
        "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFP\n"
    )

    calls: list[str] = []

    def fake_fetch(url, *, timeout, retry_max_attempts, min_request_interval_ms):
        calls.append(url)
        return fasta_text, {}

    monkeypatch.setattr(sweep, "fetch_text_with_retries", fake_fetch)

    specs = sweep._resolve_isoforms_for_candidates(
        [candidate], cache_path=cache, max_workers=1,
    )

    # 2 alt isoforms expected (the canonical -1 form isn't in the payload —
    # P12931 has no -1 suffix so it's filtered by the "-" containment check).
    assert len(specs) == 2
    acc_fulls = sorted(s.isoform_acc_full for s in specs)
    assert acc_fulls == ["P12931-2", "P12931-3"]

    by_acc = {s.isoform_acc_full: s for s in specs}
    iso2 = by_acc["P12931-2"]
    assert iso2.canonical_acc == "P12931"
    assert iso2.gene_symbol == "SRC"
    assert iso2.hgnc_id == "HGNC:11283"
    # Sequence should be the concatenation of all non-header lines for that
    # record, uppercased.
    assert iso2.sequence.startswith("MGSNKSKPKDASQRRRSLEPAENVHGAGGG")
    assert iso2.sequence.endswith("PKLFGGFNSSDTVTSPQRAGPLAGG")

    iso3 = by_acc["P12931-3"]
    assert iso3.sequence == "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFP"

    # One fetch per unique canonical.
    assert len(calls) == 1
    assert "accession:P12931" in calls[0]

    # Cache file has one entry, status=ok, isoform_ids includes canonical.
    lines = cache.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["canonical_acc"] == "P12931"
    assert entry["status"] == "ok"
    assert entry["isoform_ids"] == ["P12931", "P12931-2", "P12931-3"]
    assert set(entry["sequences"]) == {"P12931-2", "P12931-3"}


def test_no_isoforms_emits_empty_and_marks_cache(sweep, tmp_path, monkeypatch):
    """UniProt returns only the canonical → no specs, cache status=no_isoforms."""
    cache = tmp_path / "isoform_resolution.jsonl"
    candidate = _make_candidate(
        sweep, hgnc_id="HGNC:99999", symbol="LONE", uniprot_acc="Q99999",
    )

    fasta_text = (
        ">sp|Q99999|LONE_HUMAN sole record\n"
        "MAAAAAAAAAA\n"
    )

    def fake_fetch(url, *, timeout, retry_max_attempts, min_request_interval_ms):
        return fasta_text, {}

    monkeypatch.setattr(sweep, "fetch_text_with_retries", fake_fetch)

    specs = sweep._resolve_isoforms_for_candidates(
        [candidate], cache_path=cache, max_workers=1,
    )
    assert specs == []

    entry = json.loads(cache.read_text(encoding="utf-8").strip())
    assert entry["canonical_acc"] == "Q99999"
    assert entry["status"] == "no_isoforms"
    assert entry["sequences"] == {}


def test_error_path_writes_cache_marker(sweep, tmp_path, monkeypatch):
    """UniProt raises RuntimeError → empty specs, status=error in cache so
    re-runs skip the candidate."""
    cache = tmp_path / "isoform_resolution.jsonl"
    candidate = _make_candidate(
        sweep, hgnc_id="HGNC:1234", symbol="BOOM", uniprot_acc="P00000",
    )

    def fake_fetch(url, *, timeout, retry_max_attempts, min_request_interval_ms):
        raise RuntimeError("simulated 503 from UniProt")

    monkeypatch.setattr(sweep, "fetch_text_with_retries", fake_fetch)

    specs = sweep._resolve_isoforms_for_candidates(
        [candidate], cache_path=cache, max_workers=1,
    )
    assert specs == []
    entry = json.loads(cache.read_text(encoding="utf-8").strip())
    assert entry["canonical_acc"] == "P00000"
    assert entry["status"] == "error"
    assert "simulated 503" in entry["error"]

    # Second call must skip the network entirely.
    def boom(*args, **kwargs):
        raise AssertionError(
            "fetch_text_with_retries should not be called on cache hit"
        )

    monkeypatch.setattr(sweep, "fetch_text_with_retries", boom)
    specs2 = sweep._resolve_isoforms_for_candidates(
        [candidate], cache_path=cache, max_workers=1,
    )
    assert specs2 == []


def test_cache_hit_short_circuits_fetch(sweep, tmp_path, monkeypatch):
    """Pre-populated cache entry → fetch never runs; specs come from cache."""
    cache = tmp_path / "isoform_resolution.jsonl"
    cache.write_text(
        json.dumps(
            {
                "canonical_acc": "P12931",
                "isoform_ids": ["P12931", "P12931-2"],
                "sequences": {"P12931-2": "MGSNKMGSNK"},
                "status": "ok",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    candidate = _make_candidate(
        sweep, hgnc_id="HGNC:11283", symbol="SRC", uniprot_acc="P12931",
    )

    def boom(*args, **kwargs):
        raise AssertionError("cache hit should bypass UniProt")

    monkeypatch.setattr(sweep, "fetch_text_with_retries", boom)

    specs = sweep._resolve_isoforms_for_candidates(
        [candidate], cache_path=cache, max_workers=1,
    )
    assert len(specs) == 1
    spec = specs[0]
    assert spec.canonical_acc == "P12931"
    assert spec.isoform_acc_full == "P12931-2"
    assert spec.sequence == "MGSNKMGSNK"
    assert spec.gene_symbol == "SRC"
    assert spec.hgnc_id == "HGNC:11283"


# ---------------------------------------------------------------------------
# Durability — per-entry flush of the JSONL cache
# ---------------------------------------------------------------------------


def test_cache_writes_are_flushed_per_entry(sweep, tmp_path, monkeypatch):
    """The cache file handle must be flushed (or auto-flush via line
    buffering) after EVERY write, not in batches.

    Regression for the bug observed on 2026-05-26: the resolver flushed
    every 200 entries, so a machine reboot before the next flush lost
    everything since the last flush boundary (we observed only 400
    entries persisted out of ~6,406 that the in-memory cache thought
    were written).

    This test wraps the file handle in a recorder that counts write +
    flush calls. The fix can either:
      * call ``flush()`` after every write (one flush per write), OR
      * open the file with ``buffering=1`` (line-buffered → auto-flush
        on newline, which our writes always end with)

    EITHER satisfies the assertion: ``n_flushes >= n_writes`` (with
    line buffering, the TextIOWrapper internally flushes per newline so
    we'd see at least as many flushes as writes; with explicit flush()
    calls it's 1:1). Both protect against SIGKILL between writes.
    """
    cache = tmp_path / "isoform_resolution.jsonl"
    candidates = [
        _make_candidate(
            sweep, hgnc_id=f"HGNC:{3000 + i}",
            symbol=f"DURABL{i}", uniprot_acc=f"Q2000{i}",
        )
        for i in range(5)
    ]

    # Wrap Path.open so we can inspect the cache handle that the
    # resolver opens: the test asserts EITHER (a) ``buffering=1`` /
    # ``line_buffering=True`` on the handle (so each newline auto-
    # flushes to the kernel) OR (b) explicit ``.flush()`` after every
    # write. Both satisfy the durability requirement.
    cache_handles_opened: list[dict] = []
    original_open = Path.open

    def open_recorder(self, *args, **kwargs):
        f = original_open(self, *args, **kwargs)
        if str(self) != str(cache):
            return f
        # Snapshot the handle's buffering policy at open time. CPython's
        # auto-flush-on-newline (when line_buffering=True) goes through
        # a C-level fast path and does NOT trigger a Python-level
        # `.flush()` call — so we have to detect the buffering mode
        # separately from counting `.flush()` calls.
        info = {
            "line_buffering": getattr(f, "line_buffering", False),
            "write_count": 0,
            "flush_count": 0,
        }
        cache_handles_opened.append(info)
        orig_write = f.write
        orig_flush = f.flush

        def recorded_write(data):  # type: ignore[no-untyped-def]
            info["write_count"] += 1
            return orig_write(data)

        def recorded_flush():  # type: ignore[no-untyped-def]
            info["flush_count"] += 1
            return orig_flush()

        f.write = recorded_write  # type: ignore[method-assign]
        f.flush = recorded_flush  # type: ignore[method-assign]
        return f

    monkeypatch.setattr(Path, "open", open_recorder)

    def fake_fetch(url, *, timeout, retry_max_attempts, min_request_interval_ms):
        return ">sp|Q20000|DURABL_HUMAN canonical only\nMDDD\n", {}

    monkeypatch.setattr(sweep, "fetch_text_with_retries", fake_fetch)

    sweep._resolve_isoforms_for_candidates(
        candidates, cache_path=cache, max_workers=1,
    )

    # Find the append-mode handle the resolver opened (skips the
    # initial read-mode open used to load existing cache entries).
    # In our 5-candidate scenario, the resolver writes 5 entries.
    write_handle = next(
        (h for h in cache_handles_opened if h["write_count"] > 0),
        None,
    )
    assert write_handle is not None, (
        f"no append-mode cache handle observed; opens={cache_handles_opened}"
    )
    msg = (
        f"writes={write_handle['write_count']} "
        f"flushes={write_handle['flush_count']} "
        f"line_buffering={write_handle['line_buffering']}; "
        "expected EITHER `buffering=1` on the cache open (auto-flush "
        "per newline) OR explicit flush() after every write."
    )
    # Either condition satisfies durability — line buffering OR
    # per-write explicit flush.
    assert (
        write_handle["line_buffering"]
        or write_handle["flush_count"] >= write_handle["write_count"]
    ), msg

    # And independently: all 5 entries actually landed on disk.
    assert _count_complete_entries(cache) == 5


def test_partial_cache_after_crash_is_recoverable(sweep, tmp_path, monkeypatch):
    """If the resolver is interrupted mid-loop (simulated via
    KeyboardInterrupt), the on-disk cache must still be a valid
    JSONL file containing only complete entries — and the next run
    must skip the recovered ones and only fetch the missing ones.
    """
    cache = tmp_path / "isoform_resolution.jsonl"
    candidates = [
        _make_candidate(
            sweep, hgnc_id=f"HGNC:{2000 + i}",
            symbol=f"INTR{i}", uniprot_acc=f"Q1000{i}",
        )
        for i in range(5)
    ]

    n_fetches = 0
    CRASH_AT = 3  # raise mid-loop after the 3rd successful fetch

    def fake_fetch(url, *, timeout, retry_max_attempts, min_request_interval_ms):
        nonlocal n_fetches
        n_fetches += 1
        if n_fetches > CRASH_AT:
            raise KeyboardInterrupt("simulated SIGINT mid-resolve")
        import re
        m = re.search(r"accession:([A-Z0-9-]+)", url)
        assert m
        acc = m.group(1)
        return f">sp|{acc}|INTR_HUMAN canonical only\nMBBB\n", {}

    monkeypatch.setattr(sweep, "fetch_text_with_retries", fake_fetch)

    with pytest.raises(KeyboardInterrupt):
        sweep._resolve_isoforms_for_candidates(
            candidates, cache_path=cache, max_workers=1,
        )

    # Every line in the cache must be a complete, parseable JSON entry.
    # No partial / truncated lines (which would indicate a write-during-
    # flush race or a half-flushed buffer).
    lines = cache.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1, "cache should have at least one entry on disk"
    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"line {i} of cache is not valid JSON — partial flush: {line!r}"
            ) from exc
        assert "canonical_acc" in entry
        assert "status" in entry

    # Second run: the cache hits must skip the already-resolved candidates;
    # only the remaining ones get re-fetched.
    n_fetches_in_recovery = 0

    def recovery_fetch(url, **kwargs):
        nonlocal n_fetches_in_recovery
        n_fetches_in_recovery += 1
        import re
        m = re.search(r"accession:([A-Z0-9-]+)", url)
        assert m
        acc = m.group(1)
        return f">sp|{acc}|REC_HUMAN canonical only\nMCCC\n", {}

    monkeypatch.setattr(sweep, "fetch_text_with_retries", recovery_fetch)
    sweep._resolve_isoforms_for_candidates(
        candidates, cache_path=cache, max_workers=1,
    )

    # Recovery should refetch only the candidates not in the cache.
    n_recovered = len(lines)
    n_remaining = 5 - n_recovered
    assert n_fetches_in_recovery == n_remaining, (
        f"recovery refetched {n_fetches_in_recovery}; expected exactly "
        f"{n_remaining} (the ones missing from the partial cache)"
    )
    # After recovery, total = 5.
    final = _count_complete_entries(cache)
    assert final == 5, (
        f"after crash + recovery, expected 5 unique cache entries, "
        f"got {final}"
    )


def _count_complete_entries(cache_path: Path) -> int:
    """Open the cache file in a fresh handle, count complete JSON lines.

    'Complete' = parses cleanly with ``json.loads``. Partial / truncated
    lines (which would indicate a write-during-flush race) are not
    counted.
    """
    if not cache_path.exists():
        return 0
    text = cache_path.read_text(encoding="utf-8")
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
    return n


# ---------------------------------------------------------------------------
# _write_isoform_fastas_to_cache
# ---------------------------------------------------------------------------


def test_write_fastas_writes_files_and_skips_existing(sweep, tmp_path):
    """3 specs → 3 files with correct headers + wrapped sequences. Re-call is a no-op."""
    cache_dir = tmp_path / "isoforms"
    long_seq = "M" * 130  # 130 aa → 60 + 60 + 10 across 3 wrapped lines.
    specs = [
        sweep.IsoformSpec(
            canonical_acc="P12931",
            isoform_acc_full="P12931-2",
            gene_symbol="SRC",
            hgnc_id="HGNC:11283",
            sequence="MGSNKSKPKDASQRRRSLEPAENVHGAGGG",
        ),
        sweep.IsoformSpec(
            canonical_acc="P12931",
            isoform_acc_full="P12931-3",
            gene_symbol="SRC",
            hgnc_id="HGNC:11283",
            sequence=long_seq,
        ),
        sweep.IsoformSpec(
            canonical_acc="Q9Y6Q9",
            isoform_acc_full="Q9Y6Q9-2",
            gene_symbol="NCOA3",
            hgnc_id="HGNC:7670",
            sequence="MAEDR",
        ),
    ]

    paths = sweep._write_isoform_fastas_to_cache(specs, cache_dir=cache_dir)
    assert set(paths) == {"P12931-2", "P12931-3", "Q9Y6Q9-2"}
    for acc, path in paths.items():
        assert path.exists()
        assert path.name == f"{acc}.fasta"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        # Header is the UniProt-style sp|ACC|ENTRY_NAME ... layout.
        assert lines[0].startswith(f">sp|{acc}|")
        assert "_HUMAN" in lines[0]
        # Sequence wrapped at 60 chars per FASTA convention.
        for body in lines[1:]:
            assert len(body) <= 60

    # P12931-3 has 130 chars → expect 3 sequence lines (60 + 60 + 10).
    p3_lines = paths["P12931-3"].read_text(encoding="utf-8").splitlines()
    assert len(p3_lines) == 4  # header + 3 wrapped sequence lines
    assert "".join(p3_lines[1:]) == long_seq

    # Re-call must not overwrite: capture mtimes, run again, mtimes equal.
    mtimes = {acc: path.stat().st_mtime_ns for acc, path in paths.items()}
    paths2 = sweep._write_isoform_fastas_to_cache(specs, cache_dir=cache_dir)
    for acc, path in paths2.items():
        assert path.stat().st_mtime_ns == mtimes[acc]
