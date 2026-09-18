"""Refresh category metadata from cached catalogues and explicitly reviewed roles.

Run before build_contact_site_assets.py. No category is inferred from absence
of a therapeutic match. Source hashes and review references accompany outputs.
"""

from pathlib import Path
import csv
import json
import hashlib

root = Path(__file__).resolve().parents[2]
raw = root / "data/external/binder_coverage"
out = root / "data/analysis/deep_dive_binding_sites/ligand_categories.json"
with (raw / "gtop_ligands.txt").open() as f:
    next(f)
    ligands = {r["Ligand ID"]: r for r in csv.DictReader(f)}
endogenous = {}
with (raw / "gtop_interactions.txt").open() as f:
    next(f)
    for r in csv.DictReader(f):
        if r["Endogenous"] != "true" or not r["Target UniProt ID"]:
            continue
        cat = (
            "endogenous_large"
            if r["Ligand Type"] in ["Peptide", "Protein", "Antibody"]
            else "endogenous_small"
            if r["Ligand Type"]
            in ["Metabolite", "Inorganic", "Synthetic organic", "Natural product"]
            else None
        )
        if not cat:
            continue
        ligand = ligands.get(r["Ligand ID"], {})
        for partner in ["GTOPDB:" + r["Ligand ID"], ligand.get("UniProt ID", "")]:
            if partner:
                endogenous[r["Target UniProt ID"] + "|" + partner] = cat
with (raw / "thera.csv").open(encoding="utf-8-sig") as f:
    names = sorted(
        {
            r["Therapeutic"].strip().lower()
            for r in csv.DictReader(f)
            if r["Therapeutic"].strip()
        }
    )
reviewed = {}
for name in ["7d12", "9g8", "ega1"]:
    reviewed["P00533|" + name] = {
        "category": "tool",
        "reference": "https://pubmed.ncbi.nlm.nih.gov/23791944/",
        "reason": "Experimentally characterized research VHH; category describes this reagent, not possible therapeutic applications.",
    }
reviewed["P00533|egb4"] = {
    "category": "tool",
    "reference": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8887186/",
    "reason": "Described as a non-inhibitory EGFR research tool.",
}
reviewed["P00533|gc1118"] = {
    "category": "therapeutic",
    "reference": "https://pubmed.ncbi.nlm.nih.gov/31164456/",
    "reason": "Clinical phase I antibody; therapeutic includes investigational and discontinued programs.",
}
reviewed["P00533|059-152"] = {
    "category": "tool",
    "reference": "https://doi.org/10.1371/journal.pone.0193158",
    "reason": "Research antibody fragment used in cell-free synthesis, structural analysis and antibody engineering; not labeled as a clinical therapeutic here.",
}
reviewed["P00533|dl11"] = {
    "category": "tool",
    "reference": "https://www.rcsb.org/structure/3P0Y",
    "reason": "Research structural Fab from the dual EGFR/HER3 therapeutic-development program. This construct is not asserted to be identical to the clinical molecule.",
}
reviewed["P00533|erbb2"] = {
    "category": "receptor_partner",
    "reference": "https://www.rcsb.org/structure/8HGO",
    "reason": "Endogenous HER2/ERBB2 receptor heterodimer partner, distinguished from a soluble activating ligand.",
}
for name in ["gc1118", "gc1118a"]:
    reviewed["P00533|" + name] = {
        "category": "therapeutic",
        "canonical_name": "GC1118",
        "reference": "https://db.antibodysociety.org/db0/2065/",
        "reason": "GC1118 and GC1118A are drug-code aliases in the same Antibody Society therapeutic record; source names and observations are retained.",
    }
out.write_text(
    json.dumps(
        {
            "sources": {
                f: hashlib.sha256((raw / f).read_bytes()).hexdigest()
                for f in ["gtop_interactions.txt", "gtop_ligands.txt", "thera.csv"]
            },
            "source_urls": [
                "https://www.guidetopharmacology.org/download.jsp",
                "https://opig.stats.ox.ac.uk/webapps/therasabdab/",
            ],
            "endogenous_pairs": endogenous,
            "therapeutic_names": names,
            "reviewed": reviewed,
        },
        indent=2,
    )
    + "\n"
)
