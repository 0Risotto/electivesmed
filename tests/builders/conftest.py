"""Fixtures for the builder layer."""

import pytest


@pytest.fixture
def keyed_container(container):
    """Container with a dummy API key so builders produce a configured model."""
    container.llm.api_key = "sk-dummy"
    return container
