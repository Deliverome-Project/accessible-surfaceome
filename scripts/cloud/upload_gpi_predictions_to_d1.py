"""Store versioned NetGPI outputs and independent curated GPI records in both D1s.

Input JSON contains ``predictions`` and ``curation`` arrays. Default is a dry run;
``--execute`` appends records to both databases and verifies their exact content.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.gpi_predictions import publish, validate_prediction
from accessible_surfaceome.env import load_env


class PacedD1Client(D1Client):
    """Share the account's request budget with other running lab jobs."""

    def query(self, sql, params=None):
        time.sleep(0.4)
        return super().query(sql, params)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    predictions = payload["predictions"]
    curation = payload["curation"]
    for row in predictions:
        validate_prediction(row)
    print(
        f"{len(predictions)} NetGPI predictions; {len(curation)} separate curation records"
    )
    if not args.execute:
        print("dry run; no database changes")
        return 0
    load_env()
    for name, config in (
        ("surfaceome_agents", D1Config.from_env()),
        ("surfaceome_public", D1Config.from_env_public()),
    ):
        with PacedD1Client(config) as client:
            print(name, publish(client, predictions, curation), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
