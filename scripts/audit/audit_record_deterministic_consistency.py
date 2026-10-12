"""Check every published record's deterministic block against its D1 sources.

Records bake the deterministic features in at annotate time, and the Worker
only back-fills a block that is missing or empty-and-unchecked. So when a
source table changes after a record was built — a Compara relabel, a Schweke
payload append, a late ortholog pull — the record silently goes stale. This
compares, gene by gene, what each record carries for the seven deterministic
features against what the currently served source tables say it should:

=================  ===================================================  =========================================
feature            record                                               source (served version)
=================  ===================================================  =========================================
topology           canonical_topology is a real row, not the stub       topology_public human_canonical
isoforms           len(isoform_topologies)                              topology_public human_isoforms rows
paralogs           len(paralogs)                                        compara_paralog rows (top 50, as loaded)
orthologs          len(orthologs.mouse / .cynomolgus), no null %id      compara_ortholog_ecd rows joined to Compara
structure          structure.source is not a placeholder                AlphaFold DB (reported, not a D1 table)
surface_bind       surface_bind.has_data                                surface_bind_protein
                   each site's anchor_topology                          side of the anchor in the served topology
homomer            homo_oligomerization.is_homo_oligomer                schweke_homomer_public
=================  ===================================================  =========================================

It also checks the source tables against each other (``source_integrity``),
because a record can match its sources while the sources themselves are
incomplete — e.g. ortholog ECD rows that point at an ortholog protein with no
topology row (649 pairs were missing this way until 2026-10-12):

* every served ortholog-ECD row's ortholog protein has served ortholog topology;
* every served ortholog-ECD row joins its Compara release (full-length %id);
* every served paralog protein has served canonical topology;
* no ortholog pair is missing an ECD identity when both proteins have an ECD.

It reads public D1 in small chunks (90 genes per query, paced) — never a
cohort-wide join, which exceeds D1's CPU limit and resets the live database.
Mismatched genes are written for ``refresh_deterministic_features_d1.py``.

    uv run python scripts/audit/audit_record_deterministic_consistency.py
"""

from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1 import d1_deterministic as dd
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

OUT = REPO_ROOT / "data/analysis/deterministic_consistency"
CHUNK = 90
PAUSE_S = 0.3
_DF = "$.deterministic_features"


def surface_bind_sides(
    d1: D1Client, genes: list[str], topo_v: str, pause: float
) -> set[str]:
    """Genes whose stored SURFACE-Bind site sides disagree with the served topology.

    A site without an ``anchor_topology`` key is fine: the Worker fills it at
    serve time from the same pinned release. A stored value, including a stored
    null, is served as is, so it must equal the side of the anchor residue in
    the served canonical topology. 110 genes kept a null baked in before
    their topology row existed, until 2026-10-12.
    """
    from accessible_surfaceome.tools.surface_bind import anchor_topology

    sites: dict[str, list[tuple[str, int, object]]] = collections.defaultdict(list)
    for ch in _chunks(genes):
        for r in d1.query(
            "SELECT s.gene_symbol g, json_extract(s.annotation_json,'$.gene.uniprot_acc') u, "
            "json_extract(j.value,'$.anchor_residue') a, "
            "json_type(j.value,'$.anchor_topology') t, json_extract(j.value,'$.anchor_topology') v "
            f"FROM surface_annotation s, json_each(s.annotation_json,'{_DF}.surface_bind.sites') j "
            f"WHERE s.gene_symbol IN ({_marks(ch)});",
            ch,
        ):
            if r["t"] is not None:  # key present: served as stored
                sites[r["u"]].append((r["g"], int(r["a"]), r["v"]))
        time.sleep(pause)
    topo: dict[str, str] = {}
    for ch in _chunks(sorted(sites)):
        for r in d1.query(
            "SELECT uniprot_acc u, per_residue_topology t FROM topology_public "
            "WHERE cohort='human_canonical' AND topology_version=? "
            f"AND uniprot_acc IN ({_marks(ch)});",
            [topo_v, *ch],
        ):
            topo[r["u"]] = r["t"]
        time.sleep(pause)
    return {
        g
        for u, rows in sites.items()
        for g, a, v in rows
        if anchor_topology(topo.get(u), a) != v
    }


def _chunks(seq: list, n: int = CHUNK):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _marks(xs: list) -> str:
    return ",".join("?" * len(xs))


def source_integrity(
    d1: D1Client, topo_v: str, par_v: str, ecd_v: str
) -> dict[str, list]:
    """Cross-table completeness of the served deterministic sources.

    Fetches key lists only and compares them locally: a correlated join over
    these tables is heavy enough to time out public D1.
    """
    q = d1.query
    ecd = q(
        "SELECT human_gene_symbol g, species s, ortholog_uniprot_acc u, human_uniprot_acc hu, "
        "human_ensembl_gene he, ortholog_ensembl_gene oe, compara_release c, ecd_pct_identity e "
        "FROM compara_ortholog_ecd WHERE ortholog_ecd_version = ?;",
        [ecd_v],
    )
    ortho_topo = {
        (r["c"], r["u"]): r["e"]
        for r in q(
            "SELECT cohort c, uniprot_acc u, ecd_length_residues e FROM topology_public "
            "WHERE topology_version = ? AND cohort IN ('mouse_ortholog','cyno_ortholog');",
            [topo_v],
        )
    }
    human_topo = {
        r["u"]: r["e"]
        for r in q(
            "SELECT uniprot_acc u, ecd_length_residues e FROM topology_public "
            "WHERE topology_version = ? AND cohort = 'human_canonical';",
            [topo_v],
        )
    }
    compara = {
        (r["c"], r["he"], r["s"], r["oe"])
        for r in q(
            "SELECT release_version c, human_ensembl_gene he, species s, ortholog_ensembl_gene oe "
            "FROM compara_ortholog WHERE release_version IN "
            "(SELECT DISTINCT compara_release FROM compara_ortholog_ecd WHERE ortholog_ecd_version = ?);",
            [ecd_v],
        )
    }
    paralog_accs = {
        r["u"]
        for r in q(
            "SELECT DISTINCT paralog_uniprot_acc u FROM compara_paralog "
            "WHERE paralog_version = ? AND paralog_uniprot_acc IS NOT NULL;",
            [par_v],
        )
    }
    cohort = {"mouse": "mouse_ortholog", "cynomolgus": "cyno_ortholog"}
    out: dict[str, list] = {
        "ortholog_without_topology": [],
        "ortholog_without_compara_row": [],
        "ortholog_ecd_identity_missing": [],
        "paralog_without_topology": sorted(
            a for a in paralog_accs if a not in human_topo
        ),
    }
    for r in ecd:
        key = (cohort.get(r["s"], r["s"]), r["u"])
        if key not in ortho_topo:
            out["ortholog_without_topology"].append([r["g"], r["s"], r["u"]])
        if (r["c"], r["he"], r["s"], r["oe"]) not in compara:
            out["ortholog_without_compara_row"].append([r["g"], r["s"], r["oe"]])
        if (
            r["e"] is None
            and (human_topo.get(r["hu"]) or 0) > 0
            and (ortho_topo.get(key) or 0) > 0
        ):
            out["ortholog_ecd_identity_missing"].append([r["g"], r["s"], r["u"]])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--pause",
        type=float,
        default=PAUSE_S,
        help="seconds between chunk queries (0 when nothing else is using D1)",
    )
    args = ap.parse_args()
    load_env()
    topo_v = dd._latest_topology_version_for_cohort("human_canonical")
    iso_v = dd._latest_topology_version_for_cohort("human_isoforms")
    par_v = dd._latest_paralog_version()
    ecd_v = dd._latest_ortholog_ecd_version()
    print(
        f"served: topology={topo_v} isoforms={iso_v} paralogs={par_v} ortholog_ecd={ecd_v}"
    )

    recs: dict[str, dict] = {}
    with D1Client(D1Config.from_env_public()) as d1:
        syms = [
            r["g"]
            for r in d1.query("SELECT gene_symbol g FROM surface_annotation;", [])
        ]
        for ch in _chunks(syms):
            for r in d1.query(
                "SELECT gene_symbol g, "
                "json_extract(annotation_json,'$.gene.uniprot_acc') u, "
                f"json_extract(annotation_json,'{_DF}.canonical_topology.tool_version') topo, "
                f"json_array_length(annotation_json,'{_DF}.isoform_topologies') iso, "
                f"json_array_length(annotation_json,'{_DF}.paralogs') par, "
                f"json_array_length(annotation_json,'{_DF}.orthologs.mouse') om, "
                f"json_array_length(annotation_json,'{_DF}.orthologs.cynomolgus') oc, "
                f"(SELECT COUNT(*) FROM json_each(annotation_json,'{_DF}.orthologs.mouse') m "
                "  WHERE json_extract(m.value,'$.full_length_pct_identity_to_human_canonical') IS NULL) "
                f"+ (SELECT COUNT(*) FROM json_each(annotation_json,'{_DF}.orthologs.cynomolgus') c "
                "  WHERE json_extract(c.value,'$.full_length_pct_identity_to_human_canonical') IS NULL) fl_null, "
                f"(SELECT COUNT(*) FROM json_each(annotation_json,'{_DF}.orthologs.mouse') m "
                "  WHERE json_extract(m.value,'$.per_residue_topology') IS NULL) "
                f"+ (SELECT COUNT(*) FROM json_each(annotation_json,'{_DF}.orthologs.cynomolgus') c "
                "  WHERE json_extract(c.value,'$.per_residue_topology') IS NULL) topo_null, "
                f"json_extract(annotation_json,'{_DF}.structure.source') struct, "
                f"json_extract(annotation_json,'{_DF}.surface_bind.has_data') sb, "
                f"json_extract(annotation_json,'{_DF}.homo_oligomerization.is_homo_oligomer') homo "
                f"FROM surface_annotation WHERE gene_symbol IN ({_marks(ch)});",
                ch,
            ):
                recs[r["g"]] = r
            time.sleep(args.pause)

        accs = sorted({r["u"] for r in recs.values() if r["u"]})
        src: dict[str, collections.Counter] = collections.defaultdict(
            collections.Counter
        )

        def count(sql: str, params: list, key: str, field: str = "n") -> None:
            for ch in _chunks(accs):
                for r in d1.query(sql.format(m=_marks(ch)), [*params, *ch]):
                    src[r["u"]][key] = r[field]
                time.sleep(args.pause)

        count(
            "SELECT uniprot_acc u, COUNT(*) n FROM topology_public WHERE cohort='human_canonical' "
            "AND topology_version=? AND uniprot_acc IN ({m}) GROUP BY uniprot_acc;",
            [topo_v],
            "topo",
        )
        count(
            "SELECT uniprot_acc u, COUNT(*) n FROM topology_public WHERE cohort='human_isoforms' "
            "AND topology_version=? AND uniprot_acc IN ({m}) GROUP BY uniprot_acc;",
            [iso_v],
            "iso",
        )
        count(
            "SELECT human_uniprot_acc u, COUNT(*) n FROM compara_paralog WHERE paralog_version=? "
            "AND paralog_gene_symbol IS NOT NULL AND paralog_uniprot_acc IS NOT NULL "
            "AND human_uniprot_acc IN ({m}) GROUP BY human_uniprot_acc;",
            [par_v],
            "par",
        )
        for sp, key in (("mouse", "om"), ("cynomolgus", "oc")):
            count(
                "SELECT human_uniprot_acc u, COUNT(*) n FROM compara_ortholog_ecd WHERE ortholog_ecd_version=? "
                "AND species=? AND human_uniprot_acc IN ({m}) GROUP BY human_uniprot_acc;",
                [ecd_v, sp],
                key,
            )
        count(
            "SELECT uniprot_acc u, 1 n FROM surface_bind_protein WHERE uniprot_acc IN ({m});",
            [],
            "sb",
        )
        side_wrong = surface_bind_sides(
            d1,
            [g for g, r in recs.items() if r["sb"] in (1, True, "true")],
            topo_v,
            args.pause,
        )
        integrity = source_integrity(d1, topo_v, par_v, ecd_v)
        count(
            "SELECT uniprot_acc u, 1 n FROM schweke_homomer_public WHERE uniprot_acc IN ({m});",
            [],
            "homo",
        )

    truthy = (1, True, "true")
    problems: dict[str, list[str]] = collections.defaultdict(list)
    for g, r in recs.items():
        s = src[r["u"]]
        checks = {
            "topology": (r["topo"] != "placeholder-no-d1-row") == bool(s["topo"]),
            "isoforms": (r["iso"] or 0) == s["iso"],
            "paralogs": (r["par"] or 0) == min(s["par"], dd.PARALOG_TOP_N),
            "orthologs_mouse": (r["om"] or 0) == s["om"],
            "orthologs_cyno": (r["oc"] or 0) == s["oc"],
            "ortholog_full_length_identity": (r["fl_null"] or 0) == 0,
            # Every served ortholog protein has topology (source_integrity), so
            # an entry without per-residue topology predates it.
            "ortholog_topology": (r["topo_null"] or 0) == 0,
            "surface_bind": (r["sb"] in truthy) == bool(s["sb"]),
            "surface_bind_sides": g not in side_wrong,
            "homomer": (r["homo"] in truthy) == bool(s["homo"]),
        }
        for k, ok in checks.items():
            if not ok:
                problems[k].append(g)
    no_afdb = sorted(
        g for g, r in recs.items() if "placeholder" in (r["struct"] or "").lower()
    )

    args.out.mkdir(parents=True, exist_ok=True)
    report = {
        "n_records": len(recs),
        "served_versions": {
            "topology": topo_v,
            "isoforms": iso_v,
            "paralogs": par_v,
            "ortholog_ecd": ecd_v,
        },
        "mismatches": {k: sorted(v) for k, v in sorted(problems.items())},
        "structure_placeholder_no_afdb_model": no_afdb,
        "source_integrity": integrity,
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    stale = sorted({g for v in problems.values() for g in v})
    (args.out / "stale_genes.json").write_text(json.dumps(stale) + "\n")
    print(f"records: {len(recs)}")
    for k in (
        "topology",
        "isoforms",
        "paralogs",
        "orthologs_mouse",
        "orthologs_cyno",
        "ortholog_full_length_identity",
        "ortholog_topology",
        "surface_bind",
        "surface_bind_sides",
        "homomer",
    ):
        v = problems.get(k, [])
        print(f"  {k:31s} mismatched: {len(v):4d}  {sorted(v)[:8]}")
    print(f"  structure (no AlphaFold model): {len(no_afdb)}")
    print("source integrity:")
    for k, v in integrity.items():
        print(f"  {k:31s} {len(v):4d}  {v[:5]}")
    print(f"stale genes to refresh: {len(stale)} -> {args.out / 'stale_genes.json'}")
    failed = bool(stale) or any(integrity.values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
