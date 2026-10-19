"""Guards for the tag-site disulfide-clearance calibration.

The whole calibration rests on three things being right: the bond is read off
the model geometry (not UniProt), the three distance conventions are computed
distinctly, and the derived insert size does not quietly call a single
unnatural-amino-acid substitution a tag insertion. Each is pinned here.

The anchor test reproduces five measurements made by hand on S4E9 constructs.
It needs AFDB + UniProt, so it is marked ``network``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from accessible_surfaceome.audit._disulfide_clearance import (
    CONVENTIONS,
    SG_SG_BOND_MAX_A,
    ModelResidue,
    ProteinStructure,
    _resolve_disulfides,
    load_structure,
    measure_site,
    uniprot_disulfides,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "calibrate_disulfide_clearance",
    REPO_ROOT / "scripts" / "audit" / "calibrate_disulfide_clearance.py",
)
assert _SPEC and _SPEC.loader
cal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cal)


def _struct(
    residues: dict[int, ModelResidue], annotated: frozenset[tuple[int, int]] = frozenset()
) -> ProteinStructure:
    s = ProteinStructure(
        uniprot_acc="TEST",
        model_pdb_url="file://test",
        model_sequence="",
        uniprot_sequence="",
        residues=residues,
        annotated_disulfides=set(annotated),
    )
    _resolve_disulfides(s)
    return s


def _cys(x: float, *, sg_offset: float = 1.8, y: float = 0.0) -> ModelResidue:
    """A minimal CYS with CA at (x, y) and SG ``sg_offset`` further along x."""
    return ModelResidue(
        resname="CYS",
        atoms={
            "CA": np.array([x, y, 0.0]),
            "CB": np.array([x + sg_offset / 2, y, 0.0]),
            "SG": np.array([x + sg_offset, y, 0.0]),
        },
    )


def _res(name: str, **atoms: np.ndarray) -> ModelResidue:
    return ModelResidue(resname=name, atoms=dict(atoms))


class TestBondsComeFromTheModel:
    def test_close_sg_pair_is_bonded(self):
        # SG atoms 2.04 A apart -> a bond, whatever UniProt says.
        s = _struct({10: _cys(0.0), 20: _cys(2.04 + 1.8 * 2, sg_offset=-1.8)})
        assert [d.label() for d in s.disulfides] == ["C10-C20"]
        assert s.disulfides[0].sg_sg_a == pytest.approx(2.04, abs=0.01)

    def test_unannotated_bond_is_still_a_bond(self):
        """ACKR3's C34-C287 is formed in the model and absent from UniProt.

        A calibration keyed on annotations would drop exactly the sites most
        likely to sit near a bond, so an empty annotation set must not empty
        the hazard set.
        """
        s = _struct(
            {10: _cys(0.0), 20: _cys(2.04 + 3.6, sg_offset=-1.8)},
            annotated=frozenset(),
        )
        assert len(s.disulfides) == 1
        assert s.disulfides[0].uniprot_annotated is False
        assert s.bonded_cys == {10, 20}

    def test_far_sg_pair_is_not_bonded(self):
        s = _struct({10: _cys(0.0), 20: _cys(30.0)})
        assert s.disulfides == []
        assert s.bonded_cys == set()
        assert s.unbonded_min_sg_sg_a is not None

    def test_annotation_flag_is_recorded_not_used_as_a_filter(self):
        s = _struct(
            {10: _cys(0.0), 20: _cys(2.04 + 3.6, sg_offset=-1.8)},
            annotated=frozenset({(10, 20)}),
        )
        assert s.disulfides[0].uniprot_annotated is True


class TestConventionsAreDistinct:
    def test_four_conventions_give_four_numbers(self):
        """The conventions are not a fixed offset apart — that is the point."""
        junction = _res(
            "ALA",
            CA=np.array([0.0, 0.0, 0.0]),
            CB=np.array([2.0, 0.0, 0.0]),  # reaches toward the Cys
        )
        s = _struct({5: junction, 10: _cys(10.0), 20: _cys(2.04 + 3.6 + 10.0, sg_offset=-1.8)})
        result = measure_site(s, 5)
        assert result is not None
        out, rows = result
        assert out["ca_ca_a"] == pytest.approx(10.0, abs=0.01)
        assert out["ca_sg_a"] == pytest.approx(11.8, abs=0.01)
        assert out["heavy_sg_a"] == pytest.approx(9.8, abs=0.01)
        assert out["heavy_a"] == pytest.approx(8.0, abs=0.01)
        # heavy-heavy is the tightest and CA-SG the loosest here; no two are
        # interchangeable at a boundary.
        assert out["heavy_a"] < out["heavy_sg_a"] < out["ca_ca_a"] < out["ca_sg_a"]
        assert len(rows) == 2
        assert {r["cys"] for r in rows} == {10, 20}

    def test_nearest_cys_may_differ_between_conventions(self):
        """Minimise each convention independently, or a boundary call flips."""
        junction = _res("ALA", CA=np.array([0.0, 0.0, 0.0]))
        # C10's CA is nearer, but its SG points away from the junction, while
        # C20 sits further out with its SG pointing back toward it. SG-SG is
        # 1.99 A, so the pair is bonded.
        s = _struct(
            {
                5: junction,
                10: _cys(9.0, sg_offset=1.8),
                20: _cys(12.0, sg_offset=-1.8, y=1.9),
            }
        )
        result = measure_site(s, 5)
        assert result is not None
        out, _rows = result
        assert out["ca_ca_cys"] == 10
        assert out["ca_sg_cys"] == 20
        # And the gap is small, so the report must not oversell "nearest".
        assert out["ca_sg_runner_up_gap_a"] < 1.0

    def test_no_bonded_cys_returns_none_not_infinity(self):
        junction = _res("ALA", CA=np.array([0.0, 0.0, 0.0]))
        s = _struct({5: junction, 10: _cys(40.0)})
        assert measure_site(s, 5) is None


class TestUniProtDisulfideParsing:
    def test_interchain_bond_without_distinct_ends_is_skipped(self):
        entry = {
            "features": [
                {
                    "type": "Disulfide bond",
                    "location": {"start": {"value": 10}, "end": {"value": 20}},
                },
                {   # interchain: start == end
                    "type": "Disulfide bond",
                    "location": {"start": {"value": 99}, "end": {"value": 99}},
                },
                {"type": "Signal", "location": {"start": {"value": 1}, "end": {"value": 25}}},
            ]
        }
        assert uniprot_disulfides(entry) == {(10, 20)}


class TestInsertSizeClassification:
    @pytest.mark.parametrize(
        ("tag_type", "expected_class", "expected_len"),
        [
            ("HA", "small_epitope", 9),
            ("HA (YPYDVPDYAS)", "small_epitope", 10),
            ("FLAG (DYKDDDDK)", "small_epitope", 8),
            ("3xHA", "small_epitope", 27),
            ("3xFLAG", "small_epitope", 24),
            # "+" joins parts, so 2xHA (18) + TEV (7) sums to 25.
            ("2xHA + TEV", "small_epitope", 25),
            ("15-aa peptide insertion", "small_epitope", 15),
            ("DogTag (22 aa)", "small_epitope", 22),
            ("EGFP", "large_domain", None),
            ("GFP / SNAP / HaloTag", "large_domain", None),
            ("HaloTag-FLAG", "large_domain", None),
            ("pHluorin (GFP variant)", "large_domain", None),
            ("ncAA (BocK/SphK via amber suppression)", "ncAA_single", 1),
            ("azido-phenylalanine (UAA, amber codon)", "ncAA_single", 1),
            ("epitope tag", "unknown", None),
            (None, "unknown", None),
        ],
    )
    def test_classify(self, tag_type, expected_class, expected_len):
        cls, length = cal.classify_insert(tag_type)
        assert cls == expected_class
        assert length == expected_len

    def test_a_large_domain_wins_over_a_co_listed_small_tag(self):
        """"HA / pHluorin" took a 238-aa fusion at that position too."""
        assert cal.classify_insert("HA / pHluorin")[0] == "large_domain"

    def test_ncaa_is_not_counted_as_a_small_tag(self):
        """A single amber-suppressed residue is a substitution, not an insert.

        Counting it as a 1-aa "tag" would let the weakest evidence in the
        corpus set the tightest observed clearance.
        """
        assert cal.classify_insert("Cy5 via UAA")[0] == "ncAA_single"


class TestInsertSizeBand:
    """The 12-30 aa band is the one the internal arms actually carry.

    ALFA is 15 aa (19 as installed with GS flanks) and DogTag 23, so both must
    land in `c_12_to_30aa` and neither may be filed with the bare epitope tags
    or with the >=100 aa fusion domains — a floor read off the wrong band is
    the transfer error this whole study is trying not to make.
    """

    @pytest.mark.parametrize(
        ("tag_type", "expected_band"),
        [
            ("HA", "b_epitope_to_11aa"),
            ("FLAG (DYKDDDDK)", "b_epitope_to_11aa"),
            ("HiBiT", "b_epitope_to_11aa"),
            ("ALFA", "c_12_to_30aa"),
            ("DogTag (22 aa)", "c_12_to_30aa"),
            ("15-aa peptide insertion", "c_12_to_30aa"),
            ("3xHA", "c_12_to_30aa"),
            ("V5", "c_12_to_30aa"),
            ("AP (biotin ligase acceptor peptide, 35 aa)", "d_31_to_99aa"),
            ("EGFP", "d_domain_100aa_plus"),
            ("HaloTag", "d_domain_100aa_plus"),
            ("ncAA (bioorthogonal dye)", "a_single_ncAA"),
            ("epitope tag", "e_unknown"),
        ],
    )
    def test_band(self, tag_type, expected_band):
        cls, length = cal.classify_insert(tag_type)
        assert cal.insert_size_band(cls, length) == expected_band

    def test_bands_sort_into_ascending_cargo_size(self):
        """The report orders bands by sorting the keys, so the keys must sort."""
        order = [
            "a_single_ncAA",
            "b_epitope_to_11aa",
            "c_12_to_30aa",
            "d_31_to_99aa",
            "d_domain_100aa_plus",
            "e_unknown",
        ]
        assert sorted(order) == order
        assert set(order) == set(cal.BAND_LABEL)

    def test_a_joined_cassette_is_not_filed_as_its_smaller_half(self):
        """"SpyTag003+ALFA" must not read as a bare 15-aa ALFA.

        `+` joins parts of one insert, so the parts sum: 16 + 15 = 31, which is
        a lower bound on the ~51 aa installed with linkers. Filing it in the
        12-30 aa band would put the cassette in the row reserved for the cargo
        the internal arms actually carry, which is the exact transfer error the
        bands exist to prevent.
        """
        cls, length = cal.classify_insert("SpyTag003+ALFA cassette")
        assert length is not None and length >= 31
        band = cal.insert_size_band(cls, length)
        assert band != "c_12_to_30aa"
        assert band == "d_31_to_99aa"

    def test_slash_lists_alternatives_and_plus_joins_parts(self):
        """The two separators mean opposite things and are handled apart."""
        # Alternatives: the smallest is the honest lower bound.
        assert cal.classify_insert("HA / 2xHA / FLAG")[1] == 8
        # Joined parts: they sum. 2xHA (18) + TEV (7).
        assert cal.classify_insert("2xHA + TEV")[1] == 25
        # A plus inside a parenthetical is not a join.
        assert cal.classify_insert("HA (9 aa + 4 aa flanking linkers)")[1] == 9

    def test_an_explicit_length_beats_the_canonical_table(self):
        """"AP (..., 35 aa)" is 35, not the 15 the bare name would contribute."""
        cls, length = cal.classify_insert("AP (biotin ligase acceptor peptide, 35 aa)")
        assert (cls, length) == ("small_epitope", 35)


class TestAdjacencyIsPerConvention:
    """An adjacency exclusion masked on one convention corrupts the others.

    Which cysteine wins flips with the ruler, so a site can be sequence-adjacent
    on one convention and hundreds of residues away on another. Masking every
    column on one column's separation throws away the far constraint and reads
    the site as a pure adjacency artifact.
    """

    def _frame(self):
        import pandas as pd

        # Row 0 is the ACKR3 P35 shape: CA-CA and heavy-heavy win on an
        # adjacent cysteine, CA-SG and heavy-SG on one 252 residues away.
        return pd.DataFrame(
            {
                "ca_ca_a": [3.83, 20.0],
                "ca_sg_a": [5.94, 20.0],
                "heavy_sg_a": [3.81, 20.0],
                "heavy_a": [1.35, 20.0],
                "ca_ca_seq_sep": [1, 50],
                "ca_sg_seq_sep": [252, 50],
                "heavy_sg_seq_sep": [252, 50],
                "heavy_seq_sep": [1, 50],
            }
        )

    def test_mask_is_taken_on_each_conventions_own_winner(self):
        df = self._frame()
        # The adjacent-on-heavy-heavy row must still count for CA-SG/heavy-SG,
        # where its winning cysteine is 252 residues away.
        assert cal.spatial_mask(df, "heavy").tolist() == [False, True]
        assert cal.spatial_mask(df, "ca_ca").tolist() == [False, True]
        assert cal.spatial_mask(df, "ca_sg").tolist() == [True, True]
        assert cal.spatial_mask(df, "heavy_sg").tolist() == [True, True]

    def test_spatial_sweep_keeps_the_far_constraint(self):
        """The 3.81 Å heavy-SG constraint must survive the spatial scope.

        Dropping it is how a site retired for sitting 3.81 Å from an
        unannotated bond nearly got un-retired as an adjacency artifact.
        """
        tab = cal.floor_table(self._frame(), spatial_only=True).set_index("floor_a")
        # heavy-SG keeps both rows, and the 3.81 is rejected by a 4 Å floor.
        assert tab.loc[4, "heavy_sg_n_sites"] == 2
        assert tab.loc[4, "heavy_sg_rejected_n"] == 1
        # heavy-heavy drops the adjacent row, so nothing is left below 4 Å.
        assert tab.loc[4, "heavy_n_sites"] == 1
        assert tab.loc[4, "heavy_rejected_n"] == 0

    def test_row_counts_may_differ_per_convention(self):
        tab = cal.floor_table(self._frame(), spatial_only=True)
        counts = {c: int(tab.iloc[0][f"{c}_n_sites"]) for c in CONVENTIONS}
        assert len(set(counts.values())) > 1, (
            "a per-convention scope must be allowed to have different n per "
            "column; equal counts here would mean the mask collapsed to one "
            "convention again"
        )


class TestFloorSweep:
    def test_rejection_is_strictly_below_the_floor(self):
        import pandas as pd

        sub = pd.DataFrame(
            {
                "heavy_a": [3.9, 4.0, 4.1],
                "heavy_sg_a": [3.9, 4.0, 4.1],
                "ca_ca_a": [9.9, 10.0, 10.1],
                "ca_sg_a": [1.0, 2.0, 3.0],
            }
        )
        tab = cal.floor_table(sub).set_index("floor_a")
        # 4 A floor rejects only the 3.9: a site exactly at the floor passes.
        assert tab.loc[4, "heavy_rejected_n"] == 1
        assert tab.loc[10, "ca_ca_rejected_n"] == 1
        assert tab.loc[4, "ca_sg_rejected_n"] == 3
        assert tab.loc[4, "heavy_rejected_frac"] == pytest.approx(1 / 3, abs=1e-4)

    def test_every_convention_has_a_floor_column(self):
        import pandas as pd

        sub = pd.DataFrame({f"{c}_a": [5.0, 12.0] for c in CONVENTIONS})
        tab = cal.floor_table(sub)
        for c in CONVENTIONS:
            assert f"{c}_rejected_n" in tab.columns
            assert f"{c}_rejected_frac" in tab.columns

    def test_floors_span_4_to_16(self):
        assert cal.FLOORS[0] == 4
        assert cal.FLOORS[-1] == 16
        assert len(cal.FLOORS) == 13


@pytest.mark.network
class TestFrameResolution:
    """`position_frame` is provenance, not a transform still to apply.

    All four frame-bearing sites in this corpus carry an `insert_after_residue`
    that is *already* canonical. Applying the signal-peptide offset that the
    word "mature" seems to ask for lands on a different residue entirely, and
    nothing downstream would flag it — so the resolver verifies the residue
    letter instead of trusting the frame label in either direction.
    """

    CACHE = REPO_ROOT / "data" / "cache" / "disulfide_clearance"

    @pytest.mark.parametrize(
        ("gene", "acc", "pos", "letter", "frame"),
        [
            ("GABRA4", "P48169", 39, "K", "mature"),
            ("GABRA6", "Q16445", 23, "V", "mature"),
            ("GABRP", "O00591", 27, "N", "mature"),
            ("CACNA2D1", "P54289", 568, "N", "isoform:P54289-2"),
        ],
    )
    def test_frame_bearing_positions_are_already_canonical(
        self, gene, acc, pos, letter, frame, tmp_path
    ):
        cache = self.CACHE if self.CACHE.exists() else tmp_path
        got_acc, got_pos, resolution, reason = cal.resolve_position(
            {
                "uniprot_acc": acc,
                "insert_after_residue": pos,
                "residue_before": letter,
                "position_frame": frame,
            },
            cache_dir=cache,
        )
        assert reason is None
        assert got_acc == acc, "must not redirect to an isoform that does not match"
        assert got_pos == pos, "must not apply an offset that is already applied"
        assert resolution == "canonical_as_given"

    def test_a_genuinely_offset_mature_position_is_offset(self, tmp_path):
        """The mature branch still works when the position really needs it.

        GABRA4's signal peptide is 1-35 and canonical 74 is V, so a row pinned
        at mature 39 with residue_before='V' is the offset case.
        """
        cache = self.CACHE if self.CACHE.exists() else tmp_path
        acc, pos, resolution, reason = cal.resolve_position(
            {
                "uniprot_acc": "P48169",
                "insert_after_residue": 39,
                "residue_before": "V",
                "position_frame": "mature",
            },
            cache_dir=cache,
        )
        assert reason is None
        assert (acc, pos, resolution) == ("P48169", 74, "mature_offset_applied")

    def test_a_position_matching_nothing_is_excluded_not_measured(self, tmp_path):
        cache = self.CACHE if self.CACHE.exists() else tmp_path
        _acc, pos, resolution, reason = cal.resolve_position(
            {
                "uniprot_acc": "P48169",
                "insert_after_residue": 39,
                "residue_before": "W",
                "position_frame": None,
            },
            cache_dir=cache,
        )
        assert pos is None
        assert resolution == "unresolved"
        assert reason is not None and "not the W" in reason


@pytest.mark.network
class TestS4E9Anchors:
    """Reproduce five measurements made by hand on built S4E9 constructs.

    If any of these moves, either the engine changed or AFDB re-released the
    model — find out which before trusting a floor derived from it.
    """

    ANCHORS = [
        ("P11836", 146, 167, 16.0, 16.0, 13.2),
        ("P11836", 161, 183, 11.3, 10.0, 8.0),
        ("P51681", 263, 269, 15.1, 17.8, 12.9),
        ("P51681", 271, 269, 5.6, 7.8, 3.4),
        ("P25106", 284, 287, 10.2, 11.4, 6.9),
    ]

    @pytest.mark.parametrize(("acc", "junction", "cys", "caca", "casg", "heavy"), ANCHORS)
    def test_anchor(self, acc, junction, cys, caca, casg, heavy, tmp_path):
        cache = REPO_ROOT / "data" / "cache" / "disulfide_clearance"
        struct = load_structure(acc, cache_dir=cache if cache.exists() else tmp_path)
        assert struct is not None
        j, c = struct.residues[junction], struct.residues[cys]
        assert c.resname == "CYS"
        j_ca, c_ca, c_sg = j.atom("CA"), c.atom("CA"), c.atom("SG")
        assert j_ca is not None and c_ca is not None and c_sg is not None
        assert float(np.linalg.norm(j_ca - c_ca)) == pytest.approx(caca, abs=0.1)
        assert float(np.linalg.norm(j_ca - c_sg)) == pytest.approx(casg, abs=0.1)
        got = float(
            np.min(np.linalg.norm(j.heavy[:, None, :] - c.heavy[None, :, :], axis=-1))
        )
        assert got == pytest.approx(heavy, abs=0.1)

    @pytest.mark.parametrize(
        ("acc", "junction", "conv", "expected"),
        [
            # Reported by the predictors session, measured independently.
            ("P11836", 161, "heavy_sg", 8.0),
            ("P11836", 161, "ca_ca", 11.3),
            # ACKR3 P35 sits 3.81 A from C287 — the site published as
            # "12.1 A clear" because the gate never saw that bond.
            ("P25106", 35, "heavy_sg", 3.81),
        ],
    )
    def test_peer_session_cross_check(self, acc, junction, conv, expected, tmp_path):
        """Agree with a second implementation on the same models."""
        cache = REPO_ROOT / "data" / "cache" / "disulfide_clearance"
        struct = load_structure(acc, cache_dir=cache if cache.exists() else tmp_path)
        assert struct is not None
        result = measure_site(struct, junction)
        assert result is not None
        out, _rows = result
        assert out[f"{conv}_a"] == pytest.approx(expected, abs=0.15)

    def test_ccr5_264_is_a_near_tie_not_a_nearest(self, tmp_path):
        """C20 at 16.33 and C269 at 16.54 — 0.21 A apart, so report both.

        Those two numbers are **CA-SG**. Under CA-CA the same site is not a tie
        at all (C269 13.71 vs C20 18.64, a 4.9 A gap), which is the same hazard
        the four-convention table exists to prevent: a pair of distances only
        means something once its convention is named.
        """
        cache = REPO_ROOT / "data" / "cache" / "disulfide_clearance"
        struct = load_structure("P51681", cache_dir=cache if cache.exists() else tmp_path)
        assert struct is not None
        result = measure_site(struct, 264)
        assert result is not None
        out, rows = result
        by_cys = {r["cys"]: r for r in rows}
        assert by_cys[20]["ca_sg_a"] == pytest.approx(16.33, abs=0.1)
        assert by_cys[269]["ca_sg_a"] == pytest.approx(16.54, abs=0.1)
        assert out["ca_sg_runner_up_gap_a"] == pytest.approx(0.21, abs=0.05)
        # Tighter still under heavy-SG: 15.42 vs 15.45.
        assert out["heavy_sg_runner_up_gap_a"] < 0.1
        # But under CA-CA it is a comfortable 4.9 A win, not a tie.
        assert out["ca_ca_runner_up_gap_a"] > 4.0

    def test_ackr3_c34_c287_is_formed_and_unannotated(self, tmp_path):
        """The load-bearing case for reading bonds off the model."""
        cache = REPO_ROOT / "data" / "cache" / "disulfide_clearance"
        struct = load_structure("P25106", cache_dir=cache if cache.exists() else tmp_path)
        assert struct is not None
        bond = next(d for d in struct.disulfides if (d.res_i, d.res_j) == (34, 287))
        assert bond.sg_sg_a < SG_SG_BOND_MAX_A
        assert bond.uniprot_annotated is False
