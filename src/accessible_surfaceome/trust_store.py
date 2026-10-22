"""Remove the compromised eMudhra roots from every TLS trust store on a Linux machine or image.

On 2026-10-19 eight eMudhra intermediate CAs were found to have recoverable private keys, so
certificates for any site could be forged under them. They chain to two roots, which stores
that cannot block intermediates drop instead. Lockfiles pin a fixed certifi, but a running
machine or a cached container image also carries the OS bundle, pip's vendored copy of
certifi, Mono's store, and any virtualenv built before the fix. This module finds those
copies by the SHA-256 of each certificate's DER encoding (bundles have no reliable names) and,
with ``--fix``, removes them.

It is standard library only, so it runs inside any image or on any box with a Python 3:

    python3 trust_store.py /            # report; exit 1 while any store still trusts a root
    python3 trust_store.py --fix /      # distrust in the OS store, strip other copies, recheck

Modal images get it through :func:`harden`, which every image definition under ``modal/``
must call last (``tests/test_trust_store.py`` checks that). The same module, with the same
fingerprints, lives in Deliverome's analysis repository for its own Modal images and machines.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

COMPROMISED_ROOTS = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b": "emSign ECC Root CA - G3",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4": "AAA Certificate Services",
}

PEM = re.compile(
    rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----\r?\n?", re.S
)
SUFFIXES = {".pem", ".crt", ".cer", ".der"}
SKIP_DIRS = {"/proc", "/sys", "/dev", "/run"}
MAX_BYTES = 10_000_000
# Debian/Ubuntu build the OS bundle from these files; Fedora/RHEL/Amazon Linux read blocklists here.
DEBIAN_SOURCE = Path("/usr/share/ca-certificates")
DEBIAN_CONF = Path("/etc/ca-certificates.conf")
RHEL_BLOCKLIST = Path("/etc/pki/ca-trust/source/blocklist")
SOURCE_DIRS = (DEBIAN_SOURCE, RHEL_BLOCKLIST, Path("/usr/share/pki/ca-trust-source"))


def _sha256(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def _pem_blocks(data: bytes) -> list[tuple[re.Match[bytes], bytes]]:
    blocks = []
    for m in PEM.finditer(data):
        try:
            blocks.append((m, base64.b64decode(b"".join(m.group(1).split()))))
        except ValueError:
            continue
    return blocks


def compromised_in(data: bytes) -> set[str]:
    """Fingerprints of compromised roots in a PEM bundle or a single DER certificate."""
    blocks = _pem_blocks(data)
    ders = [der for _, der in blocks] if blocks else [data]
    return {_sha256(der) for der in ders} & COMPROMISED_ROOTS.keys()


def candidate_files(root: str | Path) -> list[Path]:
    """Real (non-symlink) certificate files under ``root``; symlinks point at files listed anyway."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if os.path.join(dirpath, d) not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath, name)
            if path.suffix.lower() not in SUFFIXES or path.is_symlink():
                continue
            try:
                if path.stat().st_size <= MAX_BYTES:
                    found.append(path)
            except OSError:
                continue
    return found


def scan(root: str | Path) -> dict[Path, set[str]]:
    hits = {}
    for path in candidate_files(root):
        try:
            found = compromised_in(path.read_bytes())
        except OSError:
            continue
        if found:
            hits[path] = found
    return hits


def strip(path: Path) -> None:
    """Remove the compromised roots from a bundle, or delete a file that holds only one of them."""
    data = path.read_bytes()
    blocks = _pem_blocks(data)
    keep = [m for m, der in blocks if _sha256(der) not in COMPROMISED_ROOTS]
    if not blocks or not keep:
        path.unlink()
        return
    bad = [m for m, der in blocks if _sha256(der) in COMPROMISED_ROOTS]
    out, pos = [], 0
    for m in bad:
        out.append(data[pos : m.start()])
        pos = m.end()
    out.append(data[pos:])
    path.write_bytes(b"".join(out))


def distrust_os_store(hits: dict[Path, set[str]]) -> None:
    """Distrust through the distribution's own mechanism, so a later rebuild of the bundle keeps it."""
    debian = sorted(p for p in hits if DEBIAN_SOURCE in p.parents)
    if debian and DEBIAN_CONF.exists() and shutil.which("update-ca-certificates"):
        lines = DEBIAN_CONF.read_text().splitlines()
        for path in debian:
            rel = str(path.relative_to(DEBIAN_SOURCE))
            lines = [f"!{rel}" if line == rel else line for line in lines]
            if f"!{rel}" not in lines:
                lines.append(f"!{rel}")
        DEBIAN_CONF.write_text("\n".join(lines) + "\n")
        subprocess.run(
            ["update-ca-certificates", "--fresh"], check=True, stdout=subprocess.DEVNULL
        )
    if hits and RHEL_BLOCKLIST.parent.exists() and shutil.which("update-ca-trust"):
        RHEL_BLOCKLIST.mkdir(exist_ok=True)
        for path in hits:
            data = path.read_bytes()
            ders = [der for _, der in _pem_blocks(data)] or [data]
            for der in ders:
                if _sha256(der) in COMPROMISED_ROOTS:
                    pem = base64.encodebytes(der).replace(b"\n", b"")
                    lines = [pem[i : i + 64] for i in range(0, len(pem), 64)]
                    (RHEL_BLOCKLIST / f"emudhra-{_sha256(der)[:16]}.pem").write_bytes(
                        b"-----BEGIN CERTIFICATE-----\n"
                        + b"\n".join(lines)
                        + b"\n-----END CERTIFICATE-----\n"
                    )
        subprocess.run(["update-ca-trust", "extract"], check=True)


def _confers_trust(path: Path) -> bool:
    """Source copies and blocklist entries hold a root without trusting it; the built bundles do."""
    return not any(d in path.parents for d in SOURCE_DIRS)


def fix(root: str | Path) -> None:
    distrust_os_store(scan(root))
    for path in scan(root):
        if _confers_trust(path):
            try:
                strip(path)
            except OSError:
                # A read-only copy (a snap's squashfs image, a mounted volume) cannot be
                # edited here; it stays in the report so it is updated at its source.
                continue


def remaining(root: str | Path) -> dict[Path, set[str]]:
    return {p: f for p, f in scan(root).items() if _confers_trust(p)}


def harden(image):
    """Append a layer to a ``modal.Image`` that removes the compromised roots, or fails the build.

    Call it after the image's last ``apt_install``/``pip_install``/``run_commands`` and before
    any non-copy ``add_local_*``. The new layer changes the image definition, so Modal rebuilds
    from here on instead of reusing a cached layer from before the fix.

    The package upgrade is best effort (an end-of-life base image has no reachable apt
    mirror); ``--fix`` is what guarantees the result, and it fails the build on any leftover.
    """
    return image.add_local_file(
        __file__, "/opt/surfaceome/trust_store.py", copy=True
    ).run_commands(
        "if command -v apt-get >/dev/null; then (apt-get update -qq"
        " && apt-get install -y -qq --only-upgrade ca-certificates)"
        " || echo 'ca-certificates upgrade unavailable; relying on trust_store.py --fix'; fi",
        '"$(command -v python3 || command -v python)" /opt/surfaceome/trust_store.py --fix /',
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove the compromised eMudhra roots from TLS trust stores."
    )
    parser.add_argument(
        "root", nargs="?", default="/", help="directory tree to search (default /)"
    )
    parser.add_argument(
        "--fix", action="store_true", help="distrust and strip, then recheck"
    )
    args = parser.parse_args(argv)
    if args.fix:
        fix(args.root)
    left = remaining(args.root)
    for path, found in sorted(left.items()):
        print(
            f"TRUSTED  {path}: {', '.join(sorted(COMPROMISED_ROOTS[f] for f in found))}"
        )
    if left:
        return 1
    print("Trust stores OK: no compromised eMudhra roots trusted under", args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
