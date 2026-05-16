"""Shared pytest configuration for the test suite.

Currently provides the ``--run-network`` flag and the ``network`` marker
gate used by ``tests/test_figure_provenance.py``.
"""
from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests that require external network (SWH, raw.githubusercontent)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-network"):
        return
    skip_marker = pytest.mark.skip(reason="needs --run-network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_marker)
