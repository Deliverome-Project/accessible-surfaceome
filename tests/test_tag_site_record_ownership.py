"""One record, two writers — neither may erase the other's fields.

The deterministic pipeline and the literature agent both write
`viewer/public/tag-sites/{SYMBOL}.json`, and each used to rebuild its top level
from scratch. Running the deterministic lanes over the control panel therefore
took every gene from "stamped with the prompt that produced it" back to "no
provenance", silently: the literature SITES survived and their provenance did
not, so the sites looked current and could not be dated.

A hardcoded list of keys to carry across fixes today's instance and fails the
next time a field is added. These tests fail instead.
"""
from __future__ import annotations

import json
import pathlib

from accessible_surfaceome.agents.tag_site.record import (
    DETERMINISTIC_KEYS,
    LITERATURE_KEYS,
    SHARED_KEYS,
    merge,
    unclassified,
)

#: A record carrying something from every owner.
FULL = {
    "gene_symbol": "KCNH2", "uniprot_acc": "Q12809", "has_data": True,
    "sites": [{"site_id": "s1", "provenance": "literature_retrieved"},
              {"site_id": "s2", "provenance": "deterministic_computed"}],
    "isoform_pins": [{"site_id": "p1"}], "ortholog_pins": [{"site_id": "o1"}],
    "schema_version": "1.0.0", "prompt_sha": "deadbeef", "prompt_version": "1.0.0",
    "model": "claude-sonnet-4-6", "generated_at": "2026-10-09T00:00:00Z",
    "literature_notes": "what it did not propose", "literature_rejected": [{"gate": "entailment"}],
}


def test_a_deterministic_write_keeps_the_literature_provenance() -> None:
    """The exact regression: the deterministic lanes erased prompt_sha."""
    updates = {
        "gene_symbol": "KCNH2", "uniprot_acc": "Q12809", "has_data": True,
        "sites": [{"site_id": "s2"}], "isoform_pins": [], "ortholog_pins": [],
    }
    out = merge(FULL, updates, owner="deterministic")
    for k in LITERATURE_KEYS:
        assert out[k] == FULL[k], f"deterministic write erased {k!r}"
    assert out["isoform_pins"] == []  # its OWN fields are replaced


def test_a_literature_write_keeps_the_deterministic_pins() -> None:
    updates = {
        "gene_symbol": "KCNH2", "uniprot_acc": "Q12809", "has_data": True,
        "sites": [{"site_id": "s1"}], "prompt_sha": "new", "model": "m",
    }
    out = merge(FULL, updates, owner="literature")
    for k in DETERMINISTIC_KEYS:
        assert out[k] == FULL[k], f"literature write erased {k!r}"
    assert out["prompt_sha"] == "new"  # its OWN fields are replaced


def test_alternating_writes_are_lossless() -> None:
    """Run both pipelines repeatedly; nothing may drift away."""
    rec = dict(FULL)
    for _ in range(3):
        rec = merge(rec, {"sites": [], "isoform_pins": [], "ortholog_pins": []},
                    owner="deterministic")
        rec = merge(rec, {"sites": [], "prompt_sha": "x"}, owner="literature")
    for k in (*SHARED_KEYS, *DETERMINISTIC_KEYS, *LITERATURE_KEYS):
        assert k in rec, f"{k!r} was lost after alternating writes"


def test_every_field_of_a_real_record_has_an_owner() -> None:
    """A new top-level field must be given an owner, or the other pipeline
    drops it without a word. This is the guard that outlives today's fix."""
    assert not unclassified(FULL)
    committed = sorted(pathlib.Path("viewer/public/tag-sites").glob("*.json"))[:40]
    orphans: dict[str, set[str]] = {}
    for p in committed:
        for key in unclassified(json.loads(p.read_text())):
            orphans.setdefault(key, set()).add(p.stem)
    assert not orphans, (
        f"top-level fields with no declared owner: "
        f"{ {k: sorted(v)[:3] for k, v in orphans.items()} } — add them to "
        f"agents/tag_site/record.py or the next write by the other pipeline "
        f"will erase them"
    )


def test_an_unclassified_key_is_carried_rather_than_dropped() -> None:
    """Until a field is declared, losing it is still worse than keeping it."""
    out = merge({**FULL, "something_new": 1}, {"sites": []}, owner="deterministic")
    assert out["something_new"] == 1
