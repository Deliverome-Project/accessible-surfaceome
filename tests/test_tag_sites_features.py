import gzip
import shutil
from pathlib import Path

from accessible_surfaceome.tag_sites.features import hazard_residues, feature_distances

FIXTURE = Path(__file__).parent / "fixtures" / "AF-P02786.pdb.gz"


def test_hazard_residues_extracts_the_right_feature_types():
    features = [
        {"type": "Disulfide bond", "location": {"start": {"value": 89}, "end": {"value": 98}}},
        {"type": "Glycosylation", "location": {"start": {"value": 251}, "end": {"value": 251}}},
        {"type": "Binding site", "location": {"start": {"value": 640}, "end": {"value": 642}}},
        {"type": "Chain", "location": {"start": {"value": 1}, "end": {"value": 760}}},  # ignored
        {"type": "Region", "location": {"start": {"value": 100}, "end": {"value": 110}}},  # ignored
    ]
    res = hazard_residues(features)
    assert 89 in res and 98 in res     # both disulfide partners (endpoints)
    assert 251 in res                  # glycosylation
    assert 640 in res and 642 in res   # binding site span
    assert 1 not in res and 105 not in res  # Chain / Region are not hazards


def _model(tmp_path) -> str:
    out = tmp_path / "AF-P02786.pdb"
    with gzip.open(FIXTURE, "rb") as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return str(out)


def test_feature_distances_on_real_model(tmp_path):
    p = _model(tmp_path)
    # TFRC glycosylation sequons include N251 and N317; nearest disulfide 353/363.
    dist = feature_distances(p, {251, 317, 353, 363})
    assert dist[251] == 0.0                 # the feature residue itself
    assert dist[290] > 10.0                 # I290 is 3D-clear of the nearest feature
