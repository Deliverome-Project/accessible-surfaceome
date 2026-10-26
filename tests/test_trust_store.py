"""trust_store: find and remove the compromised eMudhra roots; every Modal image calls harden()."""

from __future__ import annotations

import base64
import hashlib
import re
import subprocess
from pathlib import Path

import pytest

from accessible_surfaceome import trust_store as ts

REPO = Path(__file__).resolve().parents[1]

BAD_DER = b"pretend compromised root"
GOOD_DER = b"pretend good root"


def pem(der: bytes) -> bytes:
    body = base64.encodebytes(der)
    return b"-----BEGIN CERTIFICATE-----\n" + body + b"-----END CERTIFICATE-----\n"


@pytest.fixture(autouse=True)
def fake_roots(monkeypatch):
    fp = hashlib.sha256(BAD_DER).hexdigest()
    monkeypatch.setattr(ts, "COMPROMISED_ROOTS", {fp: "Fake Root"})
    monkeypatch.setattr(
        ts.shutil, "which", lambda _: None
    )  # never run the OS tools in tests


def test_scan_finds_bundles_and_single_der_files(tmp_path):
    (tmp_path / "site-packages" / "certifi").mkdir(parents=True)
    bundle = tmp_path / "site-packages" / "certifi" / "cacert.pem"
    bundle.write_bytes(pem(GOOD_DER) + pem(BAD_DER))
    (tmp_path / "mono").mkdir()
    der = tmp_path / "mono" / "root.cer"
    der.write_bytes(BAD_DER)
    (tmp_path / "clean.pem").write_bytes(pem(GOOD_DER))
    (tmp_path / "model.npz").write_bytes(BAD_DER)  # not a certificate file: ignored

    assert set(ts.scan(tmp_path)) == {bundle, der}


def test_fix_strips_only_the_bad_root_and_rechecks_clean(tmp_path):
    bundle = tmp_path / "cacert.pem"
    bundle.write_bytes(b"# header\n" + pem(GOOD_DER) + pem(BAD_DER) + pem(GOOD_DER))
    der = tmp_path / "root.cer"
    der.write_bytes(BAD_DER)

    assert ts.main([str(tmp_path)]) == 1
    assert ts.main(["--fix", str(tmp_path)]) == 0

    kept = ts._pem_blocks(bundle.read_bytes())
    assert [d for _, d in kept] == [GOOD_DER, GOOD_DER]
    assert bundle.read_bytes().startswith(b"# header\n")
    assert not der.exists()


def test_fix_skips_read_only_copies_and_still_reports_them(tmp_path):
    # A snap's squashfs image is read-only. --fix must carry on past it, not crash, and the
    # copy must still be reported so it gets updated at its source.
    ro = tmp_path / "snap" / "core22" / "etc"
    ro.mkdir(parents=True)
    bundle = ro / "ca-certificates.crt"
    bundle.write_bytes(pem(GOOD_DER) + pem(BAD_DER))
    writable = tmp_path / "cacert.pem"
    writable.write_bytes(pem(BAD_DER) + pem(GOOD_DER))
    bundle.chmod(0o444)
    ro.chmod(0o555)
    try:
        assert ts.main(["--fix", str(tmp_path)]) == 1
        assert set(ts.remaining(tmp_path)) == {bundle}
        assert ts.compromised_in(writable.read_bytes()) == set()
    finally:
        ro.chmod(0o755)
        bundle.chmod(0o644)


def test_source_copies_do_not_count_as_trusted(tmp_path, monkeypatch):
    source = tmp_path / "usr" / "share" / "ca-certificates"
    (source / "mozilla").mkdir(parents=True)
    (source / "mozilla" / "Fake_Root.crt").write_bytes(pem(BAD_DER))
    monkeypatch.setattr(ts, "SOURCE_DIRS", (source,))

    assert ts.remaining(tmp_path) == {}


def test_distrust_writes_debian_conf_entry(tmp_path, monkeypatch):
    source = tmp_path / "share"
    (source / "mozilla").mkdir(parents=True)
    crt = source / "mozilla" / "Fake_Root.crt"
    crt.write_bytes(pem(BAD_DER))
    conf = tmp_path / "ca-certificates.conf"
    conf.write_text("mozilla/Good.crt\nmozilla/Fake_Root.crt\n")
    calls = []
    monkeypatch.setattr(ts, "DEBIAN_SOURCE", source)
    monkeypatch.setattr(ts, "DEBIAN_CONF", conf)
    monkeypatch.setattr(ts, "RHEL_BLOCKLIST", tmp_path / "absent" / "blocklist")
    monkeypatch.setattr(ts.shutil, "which", lambda name: name)
    monkeypatch.setattr(ts.subprocess, "run", lambda cmd, **_: calls.append(cmd))

    ts.distrust_os_store({crt: set(ts.COMPROMISED_ROOTS)})

    assert conf.read_text() == "mozilla/Good.crt\n!mozilla/Fake_Root.crt\n"
    assert calls == [["update-ca-certificates", "--fresh"]]


def test_harden_appends_the_check_as_the_last_layer():
    steps = []

    class FakeImage:
        def add_local_file(self, src, dst, copy=False):
            steps.append(("add", Path(src).name, dst, copy))
            return self

        def run_commands(self, *cmds):
            steps.append(("run", cmds))
            return self

    ts.harden(FakeImage())
    assert steps[0] == ("add", "trust_store.py", "/opt/surfaceome/trust_store.py", True)
    assert "--only-upgrade ca-certificates" in steps[1][1][0]
    assert steps[1][1][-1].endswith("/opt/surfaceome/trust_store.py --fix /")


def test_every_modal_image_in_the_repo_is_hardened():
    # A Modal image is cached by its definition, so one built before 2026-10-19 keeps the
    # compromised roots until its definition changes. harden() is that change; an image that
    # skips it would silently keep trusting them. Count constructors against calls per file,
    # since one app file can define several images.
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    counts = {}
    for f in tracked:
        if f == "src/accessible_surfaceome/trust_store.py":
            continue
        text = (REPO / f).read_text(errors="ignore")
        built = len(
            re.findall(
                r"modal\.Image\.(?:debian_slim|from_registry|from_dockerfile|micromamba)\(",
                text,
            )
        )
        if built:
            counts[f] = (built, len(re.findall(r"= harden\(", text)))
    assert counts, "expected at least one Modal image definition"
    assert {f: c for f, c in counts.items() if c[0] != c[1]} == {}


def test_modal_tooling_mount_is_not_scanned():
    """Modal mounts its debug shell read-only at /__modal in every build; it is not ours."""
    assert "/__modal" in ts.SKIP_DIRS
