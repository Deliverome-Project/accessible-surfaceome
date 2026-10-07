"""Parse a disorder sweep on Modal and bring back only the rows.

The sweeps live on the ``disorder-runs`` volume and are large: NetSurfP writes a CSV per
protein *and* an aggregated CSV per shard, so the human run alone is well over 10 GB.
Downloading that to publish ~20k rows is the wrong shape, and on a laptop near a full
disk it is not possible at all.

So the parse runs where the data already is. This mounts the volume, applies the same
``sources.disorder`` parser the local uploader would have applied, and writes one
gzipped JSON of parsed rows back to the volume under ``parsed/``. That file is a few
tens of MB, so `modal volume get` on it is cheap, and the local step becomes
``upload_disorder_to_d1.py --rows-json`` with the identical row objects.

Nothing is published from here. Writing to the public database stays a local, reviewed
step with its own dry run, exactly as it was.

    modal run modal/disorder_parse_app.py --run nsp3_2026_09_28 --predictor netsurfp-3.0
"""

from __future__ import annotations

from pathlib import Path

import modal

REPO = Path(__file__).parent.parent
SRC = REPO / "src/accessible_surfaceome/sources/disorder.py"

# The parsers are stdlib-only (csv, json, re, dataclasses, pathlib), so the image needs
# nothing but the one module. Copying the file rather than the package keeps the image
# from depending on the rest of accessible_surfaceome, which it does not use.
parse_image = modal.Image.debian_slim(python_version="3.11").add_local_file(
    SRC, "/opt/disorder.py", copy=True
)

app = modal.App("surfaceome-disorder-parse")
volume = modal.Volume.from_name("disorder-runs", create_if_missing=False)
OUT = "/runs"


@app.function(image=parse_image, volumes={OUT: volume}, timeout=60 * 60, cpu=2.0)
def parse_shard(args: tuple[str, str, str]) -> dict:
    """Parse one shard. Mapped over shards because the alternative is not viable.

    NetSurfP writes a CSV per protein as well as an aggregated one per shard, so the
    human run is ~42,000 files across 21 shards. Read sequentially from one container
    over a network mount that takes hours; one container per shard takes minutes, and
    the parser is per-directory anyway so nothing about its behaviour changes.
    """
    import importlib.util
    import sys
    from dataclasses import asdict

    run, predictor, shard = args
    spec = importlib.util.spec_from_file_location("disorder", "/opt/disorder.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("disorder.py did not load in the image")
    d = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves sys.modules[cls.__module__] while
    # processing Row, and an unregistered module makes that None.
    sys.modules["disorder"] = d
    spec.loader.exec_module(d)

    shard_dir = Path(OUT) / run / shard
    if not shard_dir.is_dir():
        raise RuntimeError(f"{run}/{shard} is not on the volume")
    rows = d.PARSERS[predictor](shard_dir)
    return {acc: asdict(row) for acc, row in rows.items()}


@app.function(image=parse_image, volumes={OUT: volume}, timeout=10 * 60)
def list_shards(run: str) -> list[str]:
    d = Path(OUT) / run
    if not d.is_dir():
        raise RuntimeError(f"{run} is not on the volume")
    return sorted(p.name for p in d.iterdir() if p.is_dir())


@app.local_entrypoint()
def main(run: str, predictor: str, out: str = "data/parsed") -> None:
    import gzip
    import json as _json

    shards = list_shards.remote(run)
    print(f"{run}: {len(shards)} shard(s); parsing {predictor} in parallel")

    merged: dict = {}
    collisions = 0
    for part in parse_shard.map([(run, predictor, s) for s in shards]):
        for acc, row in part.items():
            if acc in merged:
                collisions += 1
            merged[acc] = row
        print(f"  {len(merged):,} rows so far")

    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{run}.{predictor}.json.gz"
    with gzip.open(path, "wt") as fh:
        _json.dump(merged, fh)

    print(f"\n{len(merged):,} rows -> {path} ({path.stat().st_size / 1e6:.1f} MB)")
    if collisions:
        print(f"  {collisions:,} accession(s) appeared in more than one shard")
    print(
        f"\npublish with:\n"
        f"  uv run python scripts/cloud/upload_disorder_to_d1.py \\\n"
        f"      --rows-json {path} --predictor {predictor} "
        f"--disorder-version <v> --dry-run"
    )
