"""Fixtures for the accessor layer."""

import pytest

from electivesmed.accessors.fetch import HttpAccessor


@pytest.fixture
def http_accessor(tmp_path):
    """Builds an HttpAccessor with a fake client and zero throttle delay."""

    def factory(client, delay_seconds: float = 0) -> HttpAccessor:
        accessor = HttpAccessor(cache_dir=tmp_path, delay_seconds=delay_seconds)
        accessor._client = client
        return accessor

    return factory
