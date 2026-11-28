"""Tests for tag-site R2 intermediates, retries, seeding, and bioRxiv rescue tracking."""

from __future__ import annotations

from accessible_surfaceome.agents.tag_site import intermediates as ti


def _sample_payload(*, missed_preprint: bool = False) -> dict:
    return ti.build_intermediates_payload(
        member_key="l1-p1038",
        gene_symbol="KCNN3",
        candidate_id="l1-p1038",
        uniprot_acc="Q9UGI6",
        run_id="run_test_1",
        run_series="literature_enriched_v2",
        prompt_version="1.5.0",
        prompt_sha="abc123",
        runner_intermediates={
            "model": "claude-sonnet-5-5",
            "triage_model": "claude-haiku-5-5",
            "web_scout_model": "claude-haiku-5-5",
            "web_search_mode": "adaptive",
            "web_search_used": True,
            "n_papers": 2,
            "n_papers_fetched": 1,
            "n_clips": 12,
            "n_boosted": 2,
            "discovered_papers": {
                "DOI:10.1101/2025.06.08.658482": {
                    "pmid": None,
                    "pmc_id": None,
                    "doi": "10.1101/2025.06.08.658482",
                    "title": "Preprint",
                    "abstract": "abs",
                    "year": 2025,
                    "is_preprint": True,
                }
            },
            "triage_verdicts": {
                "DOI:10.1101/2025.06.08.658482": {
                    "decision": "worth_fetching",
                    "reason": "loop tag",
                    "prompt_sha": "tsha",
                    "input_sha": "isha",
                    "model": "claude-haiku-5-5",
                    "error": None,
                },
                "PMID:999": {
                    "decision": None,
                    "reason": None,
                    "error": "timeout",
                },
            },
            "fetch_actions": [
                {
                    "paper_id": "DOI:10.1101/2025.06.08.658482",
                    "decision": "worth_fetching",
                    "fetched_body": not missed_preprint,
                }
            ],
            "outcome": "synthesized",
        },
        viewer_sites=[],
        usage=[],
        result_dump={"gene_symbol": "KCNN3", "sites": []},
    )


def test_gzip_local_roundtrip_and_seed_from_intermediates(tmp_path) -> None:
    payload = _sample_payload(missed_preprint=True)
    out = ti.save_intermediates_local(tmp_path / "l1-p1038.json.gz", payload)
    loaded = ti.decompress_intermediates(out.read_bytes())
    assert loaded["candidate_id"] == "l1-p1038"
    assert loaded["result"]["gene_symbol"] == "KCNN3"
    assert ti.has_missed_preprint_body(loaded) is True

    papers, triage, ws_ran = ti.seed_from_intermediates(loaded)
    assert "DOI:10.1101/2025.06.08.658482" in papers
    assert "DOI:10.1101/2025.06.08.658482" in triage
    assert "PMID:999" not in triage  # errored triage never seeded
    assert ws_ran is True


def test_r2_upload_retries_transient_failure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_put(*, key: str, body: bytes, content_type: str, cfg=None) -> bool:
        calls.append(key)
        # First attempt fails, subsequent attempts succeed.
        return len(calls) > 1

    monkeypatch.setattr(ti, "put_object", fake_put)
    monkeypatch.setattr(ti.time, "sleep", lambda _: None)
    ok, latest = ti.upload_intermediates_r2(
        _sample_payload(), member_key="l1-p1038", run_id="r1", max_retries=3
    )
    assert ok is True
    assert latest == "tag_site_lit_intermediates/l1-p1038/latest.json.gz"
    assert len(calls) == 3  # 2 tries for latest + 1 try for run_id
