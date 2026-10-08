"""The batch driver must feed ortholog sequences into the canonical gate run.

``ortholog_conservation`` returns 0.0 at every residue when given no orthologs — neutral
by design, so it never blocks a site. That makes an empty ortholog list invisible: the
surface_loop ranking is ``(-own RSA, conservation, -gap_freq)``, and with conservation and
gap_freq both constant the rank silently degrades to RSA alone, producing a complete and
plausible-looking site list ranked on one signal instead of three.

The driver did exactly that — it fetched orthologs *after* ``run_gene`` and passed
``ortholog_seqs=[]`` — so this pins the wiring rather than the arithmetic.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "regenerate_tag_sites", REPO / "scripts/regenerate_tag_sites.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

ACC, SYM = "Q00000", "FAKE1"
SEQ = "ACDEFGHIKLMNPQRSTVWY" * 5
ORTHOLOGS = [(f"{ACC}-mouse", SEQ, "O" * len(SEQ)), (f"{ACC}-cyno", SEQ, "O" * len(SEQ))]


def _stub(monkeypatch, seen):
    monkeypatch.setattr(mod, "af_pdb", lambda acc: "/dev/null")
    monkeypatch.setattr(mod, "_hazard", lambda acc: set())
    monkeypatch.setattr(mod, "isoforms_for", lambda acc, iso_map: [])
    monkeypatch.setattr(mod, "run_ortholog_pins", lambda *a, **k: [])
    monkeypatch.setattr(mod, "_existing_non_deterministic", lambda p: [])
    monkeypatch.setattr(mod, "orthologs_for", lambda symbol: ORTHOLOGS)

    def fake_run_gene(symbol, acc, **kw):
        seen.update(kw)
        return {"sites": []}

    monkeypatch.setattr(mod, "run_gene", fake_run_gene)


def test_ortholog_sequences_reach_the_canonical_gate_run(monkeypatch, tmp_path):
    seen: dict = {}
    _stub(monkeypatch, seen)
    mod.regenerate_gene(
        SYM, ACC, canon={ACC: (SEQ, "O" * len(SEQ))}, iso_map={},
        out_dir=tmp_path, dry_run=False,
    )
    assert seen["ortholog_seqs"] == [SEQ, SEQ], (
        "run_gene was called without the ortholog sequences, so conservation and "
        "gap_freq are 0.0 everywhere and surface_loop ranks on RSA alone"
    )


def test_signals_dir_is_passed_through(monkeypatch, tmp_path):
    seen: dict = {}
    _stub(monkeypatch, seen)
    mod.regenerate_gene(
        SYM, ACC, canon={ACC: (SEQ, "O" * len(SEQ))}, iso_map={},
        out_dir=tmp_path, dry_run=False, signals_dir=str(tmp_path / "sig"),
    )
    assert seen["signals_dir"] == str(tmp_path / "sig")
