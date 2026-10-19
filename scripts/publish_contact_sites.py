"""Publish an immutable contact release; dry-run by default, atomic pointer activation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[1]


def encode(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def release_rows(bundle):
    rid = bundle["release_id"]
    rows = {
        name: []
        for name in (
            "contact_gene",
            "contact_ligand",
            "contact_gene_ligand",
            "contact_observation",
        )
    }
    rows["contact_ligand"] = [
        [rid, x["ligand_id"], encode(x)] for x in bundle["ligands"]
    ]
    for gene in bundle["genes"]:
        acc = gene["uniprot_acc"]
        summary = encode({k: v for k, v in gene.items() if k != "observations"})
        if len(summary.encode()) > 1_000_000:
            raise ValueError(f"Summary exceeds budget: {acc}")
        rows["contact_gene"].append(
            [rid, acc, gene["hgnc_id"], summary, digest(summary)]
        )
        groups = {}
        for observation in gene["observations"]:
            lid = observation["ligand_id"]
            groups.setdefault(lid, []).append(observation["observation_id"])
            payload = encode(observation)
            rows["contact_observation"].append(
                [
                    rid,
                    observation["observation_id"],
                    acc,
                    lid,
                    observation["source"],
                    observation["context"],
                    payload,
                    digest(payload),
                ]
            )
        for lid, ids in groups.items():
            rows["contact_gene_ligand"].append(
                [rid, acc, lid, encode({"observation_ids": ids})]
            )
    return rows


def activate(db, release_id):
    if not db.query(
        "SELECT release_id FROM contact_release WHERE release_id=? AND state='validated'",
        [release_id],
    ):
        raise ValueError("Only a validated release can be activated")
    db.query(
        "INSERT INTO contact_active_release(singleton,release_id) VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET release_id=excluded.release_id",
        [release_id],
    )


def publish(db, bundle, *, make_active=False):
    rows = release_rows(bundle)
    rid = bundle["release_id"]
    manifest = encode(bundle["manifest"])
    for statement in (
        (ROOT / "cloudflare/migrations/contact_sites.sql").read_text().split(";")
    ):
        if statement.strip():
            db.query(statement, [])
    existing = db.query(
        "SELECT manifest_json FROM contact_release WHERE release_id=?", [rid]
    )
    if existing and existing[0]["manifest_json"] != manifest:
        raise ValueError("Immutable release manifest mismatch")
    db.query(
        "INSERT INTO contact_release(release_id,manifest_json,state) VALUES(?,?,'loading') ON CONFLICT DO NOTHING",
        [rid, manifest],
    )
    # One JSON parameter per batch; avoids D1's bound-parameter limit.
    columns = {
        "contact_gene": "release_id,uniprot_acc,hgnc_id,summary_json,payload_sha256",
        "contact_ligand": "release_id,ligand_id,identity_json",
        "contact_gene_ligand": "release_id,uniprot_acc,ligand_id,association_json",
        "contact_observation": "release_id,observation_id,uniprot_acc,ligand_id,source,context,observation_json,payload_sha256",
    }
    for table in (
        "contact_gene",
        "contact_ligand",
        "contact_gene_ligand",
        "contact_observation",
    ):
        data = rows[table]
        width = len(columns[table].split(","))
        fields = ",".join(f"json_extract(value,'$[{i}]')" for i in range(width))
        for offset in range(0, len(data), 100):
            db.query(
                f"INSERT OR IGNORE INTO {table}({columns[table]}) SELECT {fields} FROM json_each(?)",
                [encode(data[offset : offset + 100])],
            )
        # Read every stored row back, compare actual payloads (not just stored hashes).
        actual = []
        for offset in range(0, len(data) + 1, 500):
            result = db.query(
                f"SELECT {columns[table]} FROM {table} WHERE release_id=? ORDER BY 1,2,3 LIMIT 500 OFFSET ?",
                [rid, offset],
            )
            actual.extend([[r[c] for c in columns[table].split(",")] for r in result])
            if len(result) < 500:
                break
        if sorted(map(encode, actual)) != sorted(map(encode, data)):
            raise ValueError(f"Readback mismatch: {table}; active release unchanged")
        print(f"Verified {table}: {len(data)} rows", flush=True)
    db.query("UPDATE contact_release SET state='validated' WHERE release_id=?", [rid])
    if make_active:
        activate(db, rid)
    return rid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, nargs="?")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--rollback", help="Previously validated release ID")
    args = parser.parse_args()
    if args.rollback:
        if not args.execute:
            print(f"Dry run: activate previous release {args.rollback}")
            return
        load_env()
        with D1Client(D1Config.from_env_public()) as db:
            activate(db, args.rollback)
        return
    if not args.bundle:
        parser.error("bundle is required unless --rollback is supplied")
    bundle = json.loads(args.bundle.read_text())
    print(
        encode(
            {
                "release_id": bundle["release_id"],
                "rows": {k: len(v) for k, v in release_rows(bundle).items()},
                "execute": args.execute,
            }
        )
    )
    if args.execute:
        load_env()
        with D1Client(D1Config.from_env_public()) as db:
            publish(db, bundle, make_active=args.activate)


if __name__ == "__main__":
    main()
