"""Pytest configuration: register the --network and --slow flags."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="Run tests that require internet access.",
    )
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Run tests that take a long time to run.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    skip_network = pytest.mark.skip(reason="Pass --network to run this test")
    skip_slow = pytest.mark.skip(reason="Pass --slow to run this test")
    for item in items:
        if not config.getoption("--network") and item.get_closest_marker("network"):
            item.add_marker(skip_network)
        if not config.getoption("--slow") and item.get_closest_marker("slow"):
            item.add_marker(skip_slow)
