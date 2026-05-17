"""Pytest configuration: register the --network flag."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="Run tests that require internet access.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--network"):
        return
    skip_network = pytest.mark.skip(reason="Pass --network to run this test")
    for item in items:
        if item.get_closest_marker("network"):
            item.add_marker(skip_network)
