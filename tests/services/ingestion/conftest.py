"""Fixtures for ingestion tests."""

import pytest

from electivesmed.models.config import SourceEntry


@pytest.fixture
def entry():
    def factory(**overrides) -> SourceEntry:
        base = dict(name="generic", type="csv", parser="generic_csv", country="")
        base.update(overrides)
        return SourceEntry(**base)

    return factory
