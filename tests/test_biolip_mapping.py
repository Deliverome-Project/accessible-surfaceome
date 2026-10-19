"""Prevent structural construct numbering from becoming false human epitopes."""

import runpy
import sys
from pathlib import Path
from unittest.mock import patch

AUDIT = Path(__file__).resolve().parents[1] / "scripts/audit"
with patch.object(sys, "path", [str(AUDIT), *sys.path]):
    map_site = runpy.run_path(str(AUDIT / "audit_biolip_gpcrdb.py"))["map_biolip_site"]


def test_fragment_is_mapped_to_canonical_positions():
    assert map_site("MMACDEFGHIKWW", "ACDEFGHIK", "A1 E4 K9") == [3, 6, 11]


def test_repeated_domain_is_not_arbitrarily_assigned():
    assert map_site("ACDEFGHIKWWACDEFGHIK", "ACDEFGHIK", "A1 E4 K9") == []


def test_wrong_contact_residue_or_out_of_range_is_rejected():
    assert map_site("ACDEFGHIK", "ACDEFGHIK", "Y1") == []
    assert map_site("ACDEFGHIK", "ACDEFGHIK", "A0 K99") == []


def test_low_identity_construct_is_not_credited():
    assert map_site("ACDEFGHIK", "ACYEFGHIK", "A1 K9") == []
