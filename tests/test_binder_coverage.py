"""Guard the pilot against species, identity, complex and evidence inflation."""

import json

import pytest

from accessible_surfaceome.binders.coverage import (
    antibody_observations,
    biogrid_table_rows,
    coverage_rows,
    gtop_observations,
    observation,
    unique_index,
)

GENE = dict(
    hgnc_id="HGNC:1",
    hgnc_symbol="GENE_X",
    uniprot_acc="P00001",
    ensembl_gene="ENSG1",
    ncbi_gene_id="1",
)


def interaction(**updates):
    fields = [
        "Target Species",
        "Target UniProt ID",
        "Target Ligand UniProt ID",
        "Target Subunit IDs",
        "Target Ligand Subunit IDs",
        "Ligand ID",
        "Ligand",
        "Ligand Type",
        "Endogenous",
        "Approved",
        "Original Affinity Units",
        "Affinity Units",
        "Original Affinity Median nm",
        "Affinity Median",
        "Original Affinity Low nm",
        "Affinity Low",
        "Original Affinity High nm",
        "Affinity High",
        "Original Affinity Relation",
        "Assay Description",
        "Type",
        "Action",
        "Receptor Site",
        "PubMed ID",
    ]
    row = dict.fromkeys(fields, "")
    row.update(
        {
            "Target Species": "Human",
            "Target UniProt ID": "P00001",
            "Ligand ID": "1",
            "Ligand": "binder X",
            "Ligand Type": "Antibody",
        }
    )
    row.update(updates)
    return row


def test_ambiguous_accession_is_not_arbitrarily_resolved():
    other = dict(GENE, hgnc_id="HGNC:2")
    assert unique_index([GENE, other], "uniprot_acc") == {}


def test_species_and_complex_scope_are_preserved():
    other = dict(GENE, hgnc_id="HGNC:2", uniprot_acc="P00002")
    inputs = [
        interaction(**{"Target Species": "Mouse"}),
        interaction(
            **{"Target UniProt ID": "P00001|P00002", "Target Subunit IDs": "1|2"}
        ),
    ]
    rows, audit = gtop_observations(
        inputs,
        [{"Ligand ID": "1", "Name": "binder X"}],
        [],
        {"P00001": GENE, "P00002": other},
    )
    assert audit["nonhuman_or_unspecified_species"] == 1
    assert len(rows) == 2
    assert all(r["target_scope"] == "complex_component" for r in rows)
    covered = coverage_rows([GENE, other], rows, set())
    assert all(r["any_named_binder"] == 0 for r in covered)


def test_potency_is_not_affinity_and_structure_is_not_epitope():
    inputs = [
        interaction(
            **{"Original Affinity Units": "IC50", "Original Affinity Median nm": "2.5"}
        )
    ]
    thera = [
        {
            "Therapeutic": "Binder X",
            "HeavySequence": "AAAAAAAAAAA",
            "100% SI Structure": "1abc",
        }
    ]
    rows, _ = gtop_observations(
        inputs, [{"Ligand ID": "1", "Name": "binder X"}], thera, {"P00001": GENE}
    )
    assert rows[0]["binding_evidence"] == "curated_pharmacology"
    assert rows[0]["measurement_type"] == "IC50"
    assert rows[0]["measurement_value"] == "2.5"
    assert rows[0]["sequence_available"] == "yes"
    assert rows[0]["epitope_evidence"] == "not_reported"
    assert rows[0]["surface_evidence"] == "not_established"


def test_generic_antibody_and_fixed_staining_do_not_inflate_live_cell_coverage():
    method = {
        "method_subclass": "IHC",
        "permeabilization": "nonpermeabilized",
        "accessibility_relevance": "direct_surface_accessibility",
        "antibodies": [
            {
                "name": "anti-X",
                "antibody_epitope_region": "extracellular",
                "validation_strength": "strong",
                "validation_strategy": "genetic_KO",
            }
        ],
    }
    record = {
        "gene_json": json.dumps(GENE),
        "methods_json": json.dumps([method]),
        "record_generated_at": "2026-01-01",
    }
    rows, annotated = antibody_observations([record], {"HGNC:1": GENE})
    assert annotated == {"HGNC:1"}
    assert rows[0]["exact_identity"] == "no"
    assert rows[0]["surface_evidence"] == "not_established"
    assert coverage_rows([GENE], rows, annotated)[0]["any_named_binder"] == 0
    method["antibodies"][0]["clone"] = "clone-X"
    method["permeabilization"] = "live_cell"
    record["methods_json"] = json.dumps([method])
    rows, annotated = antibody_observations([record], {"HGNC:1": GENE})
    assert (
        coverage_rows([GENE], rows, annotated)[0]["validated_live_cell_antibody"] == 1
    )


def test_latest_annotation_wins_and_duplicate_observations_do_not_inflate_genes():
    old = {
        "gene_json": json.dumps(GENE),
        "methods_json": json.dumps(
            [{"antibodies": [{"name": "anti-X", "clone": "clone-X"}]}]
        ),
        "record_generated_at": "2025-01-01",
    }
    newer = dict(old, methods_json="[]", record_generated_at="2026-01-01")
    rows, _ = antibody_observations([old, newer], {"HGNC:1": GENE})
    assert rows == []
    one = observation(GENE, source="gtopdb", binder_id="GTOPDB:1")
    coverage = coverage_rows([GENE], [one, one], set())[0]
    assert coverage["named_binder_ids"] == 1
    assert coverage["any_named_binder"] == 1


def test_biogrid_rowspan_keeps_the_correct_target():
    first = (
        "<tr>"
        + "".join(
            f"<td>{v}</td>"
            for v in [
                "X",
                "aliases",
                "Human",
                "bait",
                "SPR",
                "2 nM",
                "low",
                "qualification",
                "PMID",
            ]
        )
        + "</tr>"
    )
    second = (
        "<tr>"
        + "".join(
            f"<td>{v}</td>"
            for v in ["bait", "Display", "-", "low", "qualification", "PMID"]
        )
        + "</tr>"
    )
    rows = biogrid_table_rows("<table>" + first + second + "</table>")
    assert rows[1][:3] == ["X", "aliases", "Human"]
    assert rows[1][4] == "Display"
    with pytest.raises(ValueError, match="row shape"):
        biogrid_table_rows("<tr><td>unexpected</td></tr>")


def test_log_affinity_is_never_labeled_nanomolar():
    inputs = [
        interaction(
            **{
                "Original Affinity Units": "-",
                "Affinity Units": "pKi",
                "Affinity Median": "8.6",
            }
        )
    ]
    rows, _ = gtop_observations(
        inputs, [{"Ligand ID": "1", "Name": "binder X"}], [], {"P00001": GENE}
    )
    assert rows[0]["measurement_type"] == "pKi"
    assert rows[0]["measurement_value"] == "8.6"
    assert rows[0]["measurement_units"] == "negative_log_molar"
    assert rows[0]["binding_evidence"] == "quantitative_affinity"
