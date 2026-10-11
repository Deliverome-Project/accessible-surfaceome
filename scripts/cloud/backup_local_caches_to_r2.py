"""Back the big local caches up to PRIVATE R2, in parts.

What this protects: `data/external/tool_cache.sqlite` is ~3.8 GB of fetched
article bodies (49k rows: 12.6k PMC full texts, 30k EuropePMC). It is the
substrate that makes a rescue analysis free — `build_pool` is deterministic
over it, so the exact clip pool a run saw can be rebuilt with no network and no
model calls. It cost a day of wall-clock and real money to fill, it is
gitignored, and it exists on exactly one laptop. Losing it means re-paying for
every answer it could have given.

PRIVATE, not public, and not negotiable: it holds publisher full text mixed
indiscriminately with open-access text, and nothing in the schema separates
them. The OA half is already public per-gene in `surfaceome-litcache`; this is
the backup, not a distribution channel.

Parts, because Cloudflare's object API refuses a single body over ~300 MB — the
same reason `d1_export_to_r2.sh` splits its dumps. Each part is uploaded
separately and a manifest records the order, the sizes and the sha256 of the
whole, so a restore can verify it reassembled the right bytes.

    uv run python scripts/cloud/backup_local_caches_to_r2.py            # dry run
    uv run python scripts/cloud/backup_local_caches_to_r2.py --execute
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import logging
import time
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.r2_client import R2Config, put_object  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUCKET = "surfaceome-litcache-private"
#: Far under Cloudflare's per-object ceiling, and deliberately so. At 200 MB a
#: part takes long enough that an intermittent TLS fault
#: (SSLV3_ALERT_BAD_RECORD_MAC) lands inside it more often than not: parts 0 and
#: 1 failed six attempts each while a 172 MB part succeeded first try. Shrinking
#: the part shrinks the window — more objects, each far likelier to land.
PART_BYTES = 48 * 1024 * 1024
_ATTEMPTS = 6
_BACKOFF_S = 3.0

log = logging.getLogger("cache_backup")


def _put(cfg: R2Config, key: str, body: bytes) -> bool:
    """Upload with retries — a transient SSL fault must not leave a hole in a
    backup that reports success, which is how 1,450 objects were lost once."""
    for attempt in range(_ATTEMPTS):
        if put_object(key=key, body=body, content_type="application/octet-stream", cfg=cfg):
            return True
        if attempt + 1 < _ATTEMPTS:
            time.sleep(_BACKOFF_S * (2**attempt))
    log.error("  FAILED after %d attempts: %s", _ATTEMPTS, key)
    return False


def _verify_parts(cfg: R2Config, parts: list[dict]) -> list[str]:
    """Which part keys cannot be read back at the right size."""
    import httpx

    from accessible_surfaceome.cloud.r2_client import _object_url

    missing = []
    for part in parts:
        try:
            r = httpx.get(_object_url(cfg, part["key"]),
                          headers={"Authorization": f"Bearer {cfg.api_token}"},
                          timeout=120)
            if r.status_code != 200 or len(r.content) != part["bytes"]:
                missing.append(part["key"])
        except Exception:  # noqa: BLE001 - unreadable counts as missing
            missing.append(part["key"])
    return missing


def backup_file(path: Path, *, prefix: str, execute: bool,
                part_bytes: int = PART_BYTES) -> dict:
    raw = path.stat().st_size
    log.info("%s: %.2f GB raw", path.name, raw / 1e9)
    if not execute:
        return {"name": path.name, "raw_bytes": raw, "dry_run": True}

    cfg = R2Config.from_env(bucket=BUCKET)
    sha = hashlib.sha256()
    parts: list[dict] = []
    buf = bytearray()
    idx = 0
    t0 = time.monotonic()

    def flush(final: bool = False) -> bool:
        nonlocal buf, idx
        if not buf and not final:
            return True
        if not buf:
            return True
        key = f"{prefix}/part-{idx:04d}.gz"
        ok = _put(cfg, key, bytes(buf))
        parts.append({"key": key, "bytes": len(buf),
                      "sha256": hashlib.sha256(bytes(buf)).hexdigest(),
                      "uploaded": ok})
        log.info("  %s (%.0f MB) %s  [%.0f s elapsed]", key, len(buf) / 1e6,
                 "ok" if ok else "FAILED", time.monotonic() - t0)
        buf = bytearray()
        idx += 1
        return ok

    all_ok = True
    # Stream: read raw, hash it, gzip into a buffer, cut parts at PART_BYTES of
    # COMPRESSED output. Never holds the whole file in memory.
    with path.open("rb") as fh:
        sink = io.BytesIO()
        gz = gzip.GzipFile(fileobj=sink, mode="wb", mtime=0)
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
            gz.write(chunk)
            if sink.tell() >= part_bytes:
                buf.extend(sink.getvalue())
                sink.seek(0)
                sink.truncate(0)
                all_ok &= flush()
        gz.close()
        buf.extend(sink.getvalue())
        all_ok &= flush(final=True)

    # Verify every part is actually RETRIEVABLE before writing a manifest that
    # claims it. The first run of this script lost part-0003 to a transient SSL
    # fault and still wrote a manifest listing four parts — a backup that
    # reports success with a hole in it is worse than one that reports failure,
    # because nobody goes looking.
    missing = _verify_parts(cfg, parts)
    if missing:
        log.warning("  %d part(s) not retrievable after upload: %s",
                    len(missing), ", ".join(missing))
        for part in parts:
            if part["key"] in missing:
                part["uploaded"] = False

    manifest = {
        "source": str(path.relative_to(ROOT)),
        "complete": not missing,
        "missing_parts": missing,
        "raw_bytes": raw,
        "raw_sha256": sha.hexdigest(),
        "compressed_bytes": sum(p["bytes"] for p in parts),
        "parts": parts,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "restore": (
            f"download {prefix}/part-*.gz in order, `cat part-*.gz | gunzip > "
            f"{path.name}`, then verify sha256 against raw_sha256"
        ),
    }
    all_ok &= _put(cfg, f"{prefix}/manifest.json",
                   json.dumps(manifest, indent=2).encode())
    log.info("  %d part(s), %.2f GB compressed (%.0f%% of raw) — %s",
             len(parts), manifest["compressed_bytes"] / 1e9,
             100 * manifest["compressed_bytes"] / raw,
             "COMPLETE" if not missing else f"INCOMPLETE, missing {len(missing)}")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", help="back up just this file name")
    ap.add_argument("--part-bytes", type=int, default=PART_BYTES,
                    help="compressed bytes per part (smaller = more reliable)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")

    targets = [(ROOT / "data/external/tool_cache.sqlite", "tool_cache")]
    for path, prefix in targets:
        if args.only and path.name != args.only:
            continue
        if not path.exists():
            log.warning("missing: %s", path)
            continue
        backup_file(path, prefix=prefix, execute=args.execute,
                    part_bytes=args.part_bytes)
    if not args.execute:
        log.info("dry run — nothing uploaded (pass --execute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
