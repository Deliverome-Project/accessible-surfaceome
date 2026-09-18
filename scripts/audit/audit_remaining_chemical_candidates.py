"""Deterministic, manually adjudicated screen of the remaining chemical candidates.

Run with the pinned pre-expansion release and the previously reviewed EC observations.
No network, coordinates, publishing, or changes to acceptance rules occur here.
RCSB cache files are primary metadata fetched via the rcsb-pdb skill.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

# Stable accession keys; comments describe the actual source chemicals, not all
# ligands discussed in the associated paper. Holds are deliberately conservative.
NOTES = {
    "Q6P4Q7": "MgATP is a specific regulatory nucleotide; 9Y9D is WT whereas 9Y9F/9Y9G/11GQ are mutants. Hold outside the bounded drug/substrate priority set.",
    "Q9UBW5": "HEPES buffer contact; no specific endogenous ligand claim.",
    "Q16572": "Acetylcholine-bound VAChT entries explicitly model neurotransmitter substrate.",
    "P17213": "BPI primary paper explicitly describes two bound phospholipids. PC1 is a generic diacylphosphocholine model; hold molecular-species identity rather than call it an unspecified physiological ligand.",
    "O75751": "7ZH6 explicitly models corticosterone as OCT3 inhibitor. Endogenous steroid with an experimental inhibitory role.",
    "O76082": "9PFB ipratropium and 9PDQ carnitine are explicitly modeled OCTN2 inhibitor/substrate complexes.",
    "Q4U2R8": "OAT1 entries explicitly name adefovir, cidofovir, glibenclamide and olmesartan. Transporter binding does not establish the drugs therapeutic mechanism at this target.",
    "P50443": "Oxalate source CCD and substrate-binding primary study support a transported anion; verify canonical footprint before acceptance.",
    "Q9Y6M5": "AV0 is LMNG detergent. Zinc transport paper does not make this organic detergent a substrate.",
    "Q9Y289": "26VA and 26VC explicitly distinguish biotin and alpha-lipoic acid substrates. CCD LPA here is lipoic acid, not lysophosphatidic acid.",
    "P48065": "Betaine and GABA are explicit substrate complexes. Cholesterol records are separate and remain held.",
    "Q9Y345": "Only cholesterol is in the input. GlyT2 inhibitor names in the paper/title must not be assigned to CLR.",
    "Q99884": "Cholesterol modulation is explicitly studied, including cholesterol-bound 9WMP; plausible regulatory lipid but held from bounded substrate/drug promotion.",
    "P48029": "CRN is creatine, not carnitine; substrate identity supported by the creatine-transporter structural study.",
    "Q92581": "PCF/PC1/3PE membrane phospholipids are not the PIP2 named in the NHE6 titles; no identity substitution.",
    "O60906": "Tetradecane and heptane hydrocarbon fragments do not independently identify intact sphingomyelin substrate.",
    "Q9BZW5": "Cholesterol in TM6SF1 deposit; specific regulatory role unresolved.",
    "P98066": "Nonaethylene glycol additive, not hyaluronan.",
    "O75888": "Tris buffer in engineered APRIL-BAFF heterotrimer; not receptor/ligand evidence.",
    "Q8IZK6": "EUJ is a short-chain PI(3,5)P2 model in ML2-SA1/PIP2-bound TRPML2. Regulatory lipid analogue; do not relabel as ML2-SA1 or native long-chain phosphoinositide.",
    "Q6U841": "Only cholesterol source contacts; carbonate and compound 38J in titles are different chemicals.",
    "Q9H2X9": "ATP bound to KCC2b T906A/T1007A phospho-knockout mutant. Regulatory nucleotide and construct caveat; held.",
    "Q9NYB5": "WT thyroxine 9DXP prioritized. Estrone sulfate/glucuronide 9DXO/9MR5 are F240A complexes and remain construct-qualified held candidates.",
    "Q9UPX8": "BisTris buffer in L1800W Shank2 SAM mutant; no specific ligand promotion.",
    "Q9BY76": "ANGPTL4 C-terminal structures explicitly model myristic and palmitic acid; binding-pocket evidence, not proof of systemic physiological ligand function. PEG remains additive.",
    "Q9NQ40": "Exact RBF riboflavin source identity supported, but generic entry/paper title provides insufficient ligand-purpose detail for this bounded recommendation set.",
    "P19397": "Monoolein in CD53 structure; membrane/crystallization lipid role unresolved.",
    "Q14728": "Monoolein in TETRAN structure; not sufficient substrate assignment.",
    "Q8TF71": "9GSZ explicitly names L-thyroxine bound to MCT10.",
    "Q8N8Q9": "ATP-bound NIPA2; specific nucleotide interaction, role and unusual source TM annotation require separate validation.",
    "Q9UM22": "Nonaethylene glycol additive in EPDR1; not native lipoprotein cargo.",
    "Q7Z2W7": "Apo TRPM8 contains undecane and POPC; no pharmacological ligand in these input rows.",
    "Q9Y5S1": "2-APB specifically modeled in S651H/T654D/D655N TRPV2, not WT. Hold canonical applicability; cholesterol/PE separate.",
    "Q7Z2H8": "9V3V explicitly models D-cycloserine; CCD 4AX is the R stereoisomer. Drug bound to transporter, not an efficacy claim.",
    "Q8WWI5": "CHT is choline in CTL1 deposit. Functional substrate purpose needs more than the fold-atlas title; retained as bounded unresolved substrate candidate.",
    "Q9P1Z3": "cAMP-specific HCN3 regulation is supported by entry and study. Regulatory nucleotide held outside drug/substrate priorities.",
    "Q8NBQ7": "Decane in LMNG-solubilized AQP11; not an independently established substrate.",
    "Q96QZ0": "Generic phosphatidylethanolamine membrane lipid in PANX3; no specific ligand-purpose inference.",
    "Q9BV23": "ABHD6 explicitly bound oleic acid and detergent; fatty-acid product/substrate distinction unresolved, held.",
    "Q8N5C1": "Short-chain phosphatidic acid in CALHM5; titles concern ruthenium red, not this lipid. Do not exchange chemical identity.",
    "Q6NT16": "SPD and SPM are explicitly spermidine/spermine-bound vesicular polyamine transporter states.",
    "Q7Z3C6": "POPC in nanodiscs and LMNG detergent; lipid-scrambling biology alone does not identify a unique named ligand.",
    "Q96KN9": "Cholesterol and generic PE membrane contacts in connexin40.1; specificity unresolved.",
    "Q8IU99": "POPC membrane contacts; 8GMP I109W engineered channel. No ruthenium-red identity transfer.",
    "Q8NBN3": "PE-bound TMEM87A is explicit, but structural lipid versus specific regulation unresolved. Cholesterol distinct.",
    "Q8NAN2": "Dipalmitoyl-PE bound lipid-targeting domain in lipid-transport study; plausible cargo but held species/physiological specificity.",
    "Q9NWC5": "Generic phosphocholine membrane model in TMEM45A; no independently supported ligand assignment.",
    "Q5VYX0": "FAD-binding renalase is a defined enzyme cofactor; not prioritized as a drug/substrate or accessible extracellular binder.",
    "Q5U3C3": "Myristoyl-LPC exact molecular species in substrate-bound phospholipid-remodeling TMEM164 study; cholesterol distinct. Native physiological chain distribution not inferred.",
    "Q01524": "Inositol hexakisphosphate explicitly drives HD6 filament assembly; dietary ligand, not established endogenous human ligand. Held for assembly-specific category review.",
    "Q8N323": "Acetyl-CoA contact in NXPE1 sialic-acid O-acetyltransferase supports catalytic donor role; coordinate acceptance still required.",
    "O94886": "Cholesterol modulation explicitly studied, whereas POPC is separate membrane lipid. Regulatory lipid plausible but outside bounded promotions.",
    "Q5BKX6": "Only cholesterol/PE input contacts; polyamine transport paper does not convert these to polyamine observations.",
    "Q9HAB3": "RBF exact riboflavin source identity, but generic entry title leaves modeled substrate-purpose corroboration bounded/unresolved.",
    "Q8TCT8": "Generic phosphocholine in intramembrane protease; no substrate inference.",
    "P15924": "Reduced/oxidized DTT laboratory reducing-agent contacts in desmoplakin fragment.",
    "Q99758": "ATP-bound ABCA3 and phosphatidylcholines are mechanistic cofactor/lipid contacts. ATP model may have catalytic construct modifications; held outside prioritized set.",
    "Q9NZM1": "Short-chain PSF model in explicitly formulated lipid nanodiscs; preserve membrane-binding context and truncated myoferlin, no unique soluble endogenous ligand.",
    "P09769": "7UY0 explicitly names A-419259 inhibitor of Fgr kinase; research inhibitor, not a marketed therapeutic. Citrate in HAL2 regulatory domains is distinct additive.",
    "P29033": "Repeated generic PE contacts across WT and K125E connexin26 structures; no 14 distinct ligands or drug inference.",
    "Q9UKP6": "Glycochenodeoxycholic acid is distinct from [Pen5]-urotensin peptide named by structure; possible preparation component, physiological receptor-ligand claim unresolved.",
    "P08236": "MPD crystallization additive.",
    "O60928": "PIO is short-chain PIP2 model in Kir7.1; supported regulation but distinguish synthetic acyl chains from native PIP2 and from steroid named in 9PR7.",
    "O00180": "Undecane hydrocarbon membrane model, not independently supported pharmacological ligand.",
    "Q9Y257": "Heptane/decane contacts only; pimozide discussed in study is not these source chemicals.",
    "Q9NZG7": "Cholesterol in NINJ2 filament; no independently resolved specific ligand role.",
    "P37288": "Only cholesterol contacts in input; atosiban, SRX246 and balovaptan named in titles must not be assigned to CLR.",
    "Q13393": "6OHR explicitly models compound 5 in PLD1 catalytic domain; retain exact paper-local name and CCD MKG, no speculative clinical alias.",
    "O14494": "9L0O specifically LPA-bound PLPP1: NKO is palmitoyl lysophosphatidic acid. LPP is different dipalmitoyl phosphatidic acid; AV0 detergent. Prioritize NKO substrate only.",
    "O14495": "Dilauroyl PA is a short-chain/model phosphatase substrate candidate; generic title insufficient to establish exact biological versus preparation role.",
    "O43688": "Palmitoyl-linoleoyl-PC is not phosphatidic acid substrate; membrane lipid held.",
    "O00400": "Separate oxidized glutathione 9MUN and acetyl-CoA 9M0S transport complexes explicitly supported by primary studies; ER transporter topology must not imply cell-surface exposure.",
    "P23469": "Pentaethylene glycol in engineered PTP epsilon D2 domain; additive.",
    "O14522": "BisTris propane buffer in PTPRT catalytic-domain structure.",
}
# Exact primary-supported proposals, not accepted observations. One PDB per CCD;
# alternate repeats stay in the full ledger, not duplicate recommendations.
CANDIDATES = [
    ("Q16572", "ACH", "8XTW", "Acetylcholine", "endogenous_small"),
    ("O75751", "C0R", "7ZH6", "Corticosterone", "endogenous_small"),
    ("O76082", "X8M", "9PFB", "Ipratropium", "therapeutic"),
    ("O76082", "152", "9PDQ", "Carnitine", "endogenous_small"),
    ("Q4U2R8", "5HG", "9M9V", "Adefovir", "therapeutic"),
    ("Q4U2R8", "L8P", "9J04", "Cidofovir", "therapeutic"),
    ("Q4U2R8", "GBM", "9J06", "Glibenclamide", "therapeutic"),
    ("Q4U2R8", "OLM", "9KLZ", "Olmesartan", "therapeutic"),
    ("P50443", "OXL", "8TNX", "Oxalate", "endogenous_small"),
    ("Q9Y289", "BTN", "26VA", "Biotin", "endogenous_small"),
    ("Q9Y289", "LPA", "26VC", "Alpha-lipoic acid", "endogenous_small"),
    ("P48065", "BET", "9W99", "Betaine", "endogenous_small"),
    ("P48065", "ABU", "9W9A", "GABA", "endogenous_small"),
    ("P48029", "CRN", "9V8X", "Creatine", "endogenous_small"),
    ("Q9NYB5", "T44", "9DXP", "L-thyroxine", "endogenous_small"),
    ("Q8TF71", "T44", "9GSZ", "L-thyroxine", "endogenous_small"),
    ("Q7Z2H8", "4AX", "9V3V", "D-cycloserine", "therapeutic"),
    ("Q6NT16", "SPD", "9D7V", "Spermidine", "endogenous_small"),
    ("Q6NT16", "SPM", "9D7X", "Spermine", "endogenous_small"),
    ("P09769", "VSE", "7UY0", "A-419259", "tool"),
    ("Q13393", "MKG", "6OHR", "PLD1 inhibitor compound 5 (CCD MKG)", "tool"),
    ("O00400", "ACO", "9M0S", "Acetyl-CoA", "endogenous_small"),
    ("O00400", "GDS", "9MUN", "Oxidized glutathione", "endogenous_small"),
    ("Q8N323", "ACO", "9PJA", "Acetyl-CoA", "endogenous_small"),
    (
        "Q5U3C3",
        "LPC",
        "9LW1",
        "1-myristoyl lysophosphatidylcholine",
        "endogenous_small",
    ),
    ("O14494", "NKO", "9L0O", "1-palmitoyl lysophosphatidic acid", "endogenous_small"),
    ("Q9BY76", "PLM", "6U1U", "Palmitic acid", "endogenous_small"),
    ("Q9BY76", "MYR", "6U73", "Myristic acid", "endogenous_small"),
]
ADDITIVES = {
    "EPE",
    "AV0",
    "LMN",
    "2PE",
    "1PE",
    "144",
    "BTB",
    "D1D",
    "DTT",
    "MRD",
    "B3P",
    "FLC",
}
HYDROCARBONS = {"C14", "HP6", "UND", "D10"}
COFACTORS = {"ATP", "CMP", "FAD"}
SPECIFIC_HOLDS = {
    ("Q8IZK6", "EUJ"),
    ("Q9Y5S1", "FZ4"),
    ("Q9NYB5", "FY5"),
    ("Q9NYB5", "E3G"),
    ("Q9NQ40", "RBF"),
    ("Q9HAB3", "RBF"),
    ("Q8WWI5", "CHT"),
    ("Q01524", "IHP"),
    ("O60928", "PIO"),
    ("O14495", "PX2"),
    ("Q9BV23", "OLA"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-release", type=Path, required=True)
    p.add_argument("--excluded-observations", type=Path, required=True)
    p.add_argument(
        "--metadata-cache",
        type=Path,
        default=root / "data/external/remaining_chemical_candidates",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root
        / "data/analysis/deep_dive_binding_sites/remaining_chemical_candidates.json",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=root / "docs/reports/2026-09-18-remaining-chemical-candidates.md",
    )
    a = p.parse_args()
    cohort = root / "data/analysis/deep_dive_binding_sites/structural_intact_genes.tsv"
    source = root / "data/analysis/deep_dive_binding_sites/observations.tsv.gz"
    baseline = json.loads(a.baseline_release.read_text())
    covered = {g["uniprot_acc"] for g in baseline["genes"] if g.get("observations")}
    excluded = {
        g["uniprot_acc"] for g in json.loads(a.excluded_observations.read_text())
    }
    with cohort.open() as f:
        original = [
            g
            for g in csv.DictReader(f, delimiter="\t")
            if g["pdbe_chemical_contacts"] == "1"
            and g["identifier_status"] == "unique"
            and g["uniprot_acc"] not in covered
        ]
    genes = sorted(
        [g for g in original if g["uniprot_acc"] not in excluded],
        key=lambda g: g["uniprot_acc"],
    )
    accs = {g["uniprot_acc"] for g in genes}
    assert (
        len(original) == 89
        and len(accs) == 74
        and len({g["uniprot_acc"] for g in original} & excluded) == 15
    )
    assert accs == set(NOTES), (
        "Manual adjudications must cover exactly the pinned cohort."
    )
    with gzip.open(source, "rt") as f:
        rows = [
            r
            for r in csv.DictReader(f, delimiter="\t")
            if r["uniprot_acc"] in accs
            and r["source"] == "PDBe"
            and r["evidence"] == "experimental_chemical_contacts"
        ]
    rows.sort(key=lambda r: (r["uniprot_acc"], r["binder_id"], r["pdb_id"]))
    keys = {(r["uniprot_acc"], r["binder_id"][4:], r["pdb_id"].upper()) for r in rows}
    candidates = []
    for acc, ccd, pdb, name, category in CANDIDATES:
        assert (acc, ccd, pdb) in keys
        candidates.append(
            dict(
                uniprot_acc=acc,
                ccd=ccd,
                pdb=pdb,
                name=name,
                category=category,
                primary_url=f"https://www.rcsb.org/structure/{pdb}",
                reason=NOTES[acc],
                status="proposed_pending_coordinate_and_canonical_sequence_validation",
            )
        )
    candidate_keys = {(c["uniprot_acc"], c["ccd"], c["pdb"]) for c in candidates}
    candidate_chemicals = {(c["uniprot_acc"], c["ccd"]) for c in candidates}
    ledger = []
    for g in genes:
        acc = g["uniprot_acc"]
        observations = []
        for r in [r for r in rows if r["uniprot_acc"] == acc]:
            ccd = r["binder_id"][4:]
            pdb = r["pdb_id"].upper()
            entry_path = a.metadata_cache / f"entry-{pdb}.json"
            ccd_path = a.metadata_cache / f"chemcomp-{ccd}.json"
            entry = json.loads(entry_path.read_text()) if entry_path.exists() else {}
            chem = json.loads(ccd_path.read_text()) if ccd_path.exists() else {}
            if not entry or not chem:
                raise ValueError(
                    f"Missing pinned primary metadata for {acc}/{ccd}/{pdb}"
                )
            deposited = entry.get("rcsb_entry_container_identifiers", {}).get(
                "non_polymer_entity_ids", []
            )
            if (acc, ccd, pdb) in candidate_keys:
                disposition = "promotion_candidate"
            elif (acc, ccd) in candidate_chemicals:
                disposition = "supported_alternate_structure_not_promoted"
            elif ccd in ADDITIVES:
                disposition = "hold_preparation_additive"
            elif ccd in HYDROCARBONS:
                disposition = "hold_hydrocarbon_or_partial_lipid_model"
            elif ccd in COFACTORS:
                disposition = "hold_regulatory_nucleotide_or_cofactor"
            elif (acc, ccd) in SPECIFIC_HOLDS:
                disposition = "hold_specific_ligand_needs_context_or_construct_review"
            else:
                disposition = "hold_lipid_or_chemical_specificity_unresolved"
            citation = entry.get("rcsb_primary_citation", {})
            observations.append(
                dict(
                    source_record=r,
                    disposition=disposition,
                    review_reason=NOTES[acc],
                    primary_url=f"https://www.rcsb.org/structure/{pdb}",
                    ccd_url=f"https://www.rcsb.org/ligand/{ccd}",
                    entry_title=entry.get("struct", {}).get("title"),
                    primary_citation_title=citation.get("title"),
                    primary_doi=citation.get("pdbx_database_id_DOI"),
                    ccd_name=chem.get("chem_comp", {}).get("name"),
                    metadata_complete=bool(entry and chem),
                    nonpolymer_entity_count=len(deposited),
                )
            )
        ledger.append(
            dict(
                uniprot_acc=acc,
                hgnc_id=g["hgnc_id"],
                hgnc_symbol=g["hgnc_symbol"],
                source_candidate_count=len(observations),
                distinct_ccd_count=len(
                    {r["source_record"]["binder_id"] for r in observations}
                ),
                reviewed=True,
                review_note=NOTES[acc],
                observations=observations,
            )
        )
    counts = Counter(o["disposition"] for g in ledger for o in g["observations"])
    result: dict[str, Any] = dict(
        schema_version=1,
        review_date="2026-09-18",
        baseline_release_id=baseline["release_id"],
        input_sha256={
            str(p): sha(p)
            for p in [cohort, source, a.baseline_release, a.excluded_observations]
        },
        primary_metadata_sha256={
            p.name: sha(p) for p in sorted(a.metadata_cache.glob("*.json"))
        },
        original_uncovered_targets=len(original),
        previously_reviewed_ec_targets=15,
        reviewed_targets=len(ledger),
        source_candidate_count=len(rows),
        unique_pdb_count=len({r["pdb_id"].upper() for r in rows}),
        distinct_ccd_count=len({r["binder_id"] for r in rows}),
        promotion_candidate_count=len(candidates),
        promotion_target_count=len({c["uniprot_acc"] for c in candidates}),
        disposition_counts=dict(sorted(counts.items())),
        limitations=[
            "Screening recommendations only: no coordinates, SIFTS chain identity, canonical sequence/mutation checks, or contact footprints validated here.",
            "Source topology is preserved, not converted into extracellular accessibility. Several targets are organellar transporters or intracellular domains.",
            "RCSB entry/CCD metadata corroborates identity and experimental purpose; a CCD in a paper title is never substituted for another source CCD.",
            "A native chemical name/category does not assert physiological exposure, efficacy, affinity, or that the exact lipid acyl species is the principal in vivo ligand.",
            "All nonrecommended rows remain explicit holds; no source observation is deleted.",
        ],
        promotion_candidates=candidates,
        targets=ledger,
    )
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    lines = (
        [
            "# Remaining chemical-contact candidates: bounded manual review",
            "",
            f"Pinned baseline `{baseline['release_id']}`: **89** unique uncovered chemical-contact targets minus **15** previously reviewed EC targets = **74** targets, **{len(rows)}** source records. All 74 receive an individual disposition; no rules or assets are changed.",
            "",
            f"**{len(candidates)} proposals across {result['promotion_target_count']} targets** are offered for independent coordinate/canonical-sequence validation. These are recommendations, not accepted footprints. One representative PDB per chemical is prioritized. Repeated deposits remain in the ledger.",
            "",
            "## Limits",
            "",
        ]
        + ["- " + x for x in result["limitations"]]
        + [
            "",
            "## Strongest explicit pairs",
            "",
            "| Accession | CCD | PDB | Name | Category |",
            "|---|---|---|---|---|",
        ]
    )
    for c in candidates:
        lines.append(
            f"| {c['uniprot_acc']} | {c['ccd']} | [{c['pdb']}]({c['primary_url']}) | {c['name']} | {c['category']} |"
        )
    lines += [
        "",
        "## Every-target disposition ledger",
        "",
        "Each source row below retains its exact CCD, PDB, topology, primary entry title and reason in the accompanying JSON. Primary entry metadata and CCD metadata were checked; contact-specific mutations still require the independent coordinate validator. This is a manual review of the bounded input chemicals, not a search for other ligands in the same structures.",
        "",
    ]
    for g in ledger:
        lines += [
            f"### {g['hgnc_symbol']} — {g['uniprot_acc']}",
            "",
            f"{g['source_candidate_count']} source records; {g['distinct_ccd_count']} CCD identities. {g['review_note']}",
            "",
        ]
        for o in g["observations"]:
            r = o["source_record"]
            lines.append(
                f"- {r['binder_id']} / [{r['pdb_id'].upper()}]({o['primary_url']}): **{o['disposition']}**; source topology `{r['topology']}`. Primary entry: {o['entry_title'] or 'unavailable'}. CCD: {o['ccd_name'] or r['binder_name']}."
            )
        lines.append("")
    lines += [
        "## Reproducibility",
        "",
        "Run `uv run --no-sync python scripts/audit/audit_remaining_chemical_candidates.py --baseline-release /private/tmp/contact-review-50/release.json --excluded-observations /private/tmp/contact-expansion-review/chemical-observations.json`. The script does not fetch or publish; it uses bounded cached RCSB entry/CCD metadata. SHA-256 hashes of all four pinned inputs are recorded in the JSON.",
        "",
        f"Disposition totals: `{json.dumps(dict(sorted(counts.items())))}`.",
        "",
    ]
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text("\n".join(lines))
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "reviewed_targets",
                    "source_candidate_count",
                    "promotion_candidate_count",
                    "promotion_target_count",
                    "disposition_counts",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
