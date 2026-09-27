"""Fixtures for the component layer."""

import pytest

from electivesmed.components.policy import PolicyGate


@pytest.fixture
def policy_gate(container) -> PolicyGate:
    return PolicyGate(container.dao, container.settings)
