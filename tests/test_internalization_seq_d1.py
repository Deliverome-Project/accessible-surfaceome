from datetime import UTC, datetime

from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    InternalizationRecord,
    IsoformPrior,
    ModelPriorTrack,
    MotifHit,
)
from accessible_surfaceome.cloud.internalization import _COLS, flat_row


def _record() -> InternalizationRecord:
    iso = IsoformPrior(
        isoform_id="P02786",
        is_canonical=True,
        length_aa=760,
        topology_summary="type II; cytoplasmic N-term ~65 aa",
        endocytic_motifs_noted="YTRF in cytoplasmic tail",
        motifs=[
            MotifHit(
                motif_type="yxxphi", sequence="YTRF", region="cytoplasmic",
                functional_context=True,
            ),
            MotifHit(
                motif_type="acidic_cluster", sequence="EEENAD",
                region="extracellular", functional_context=False,
            ),
        ],
        grade="moderate",
        confidence="moderate",
        rationale="cytoplasmic YXXphi motif",
    )
    return InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol="TFRC",
        hgnc_id="HGNC:11763",
        uniprot_acc="P02786",
        model_priors=[
            ModelPriorTrack(
                model="claude-opus-4-8",
                overall_grade="moderate",
                overall_confidence="moderate",
                model_reasoning="r",
                per_isoform=[iso],
            )
        ],
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        runner_version="internalization-model-prior/0.1.0",
    )


def test_flat_row_projects_seq_track():
    row = flat_row(_record())
    # every declared column is present (the INSERT binds positionally on _COLS)
    assert set(row) == set(_COLS)
    assert row["gene_symbol"] == "TFRC"
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["seq_model"] == "claude-opus-4-8"
    assert row["seq_scope"] == "intrinsic_propensity"
    assert row["seq_overall_grade"] == "moderate"
    assert row["seq_canonical_grade"] == "moderate"
    # two motifs, one of them functional (cytoplasmic)
    assert row["n_seq_motifs"] == 2
    assert row["n_seq_functional_motifs"] == 1
    # model-prior-only record → literature columns null / flag off
    assert row["has_literature"] == 0
    assert row["lit_overall_grade"] is None
    # the full record round-trips through record_json
    again = InternalizationRecord.model_validate_json(str(row["record_json"]))
    assert again.gene_symbol == "TFRC"
    assert again.model_priors[0].per_isoform[0].motifs[0].sequence == "YTRF"
