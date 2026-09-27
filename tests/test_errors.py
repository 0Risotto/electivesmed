from electivesmed.errors import (
    ConfigError,
    FetchError,
    LlmError,
    LlmUnavailable,
    OutreachError,
    PolicyDenied,
    StoreError,
)


def test_policy_denied_keeps_reason():
    error = PolicyDenied("draft not approved")

    assert error.reason == "draft not approved"
    assert str(error) == "draft not approved"


def test_error_hierarchy():
    for error_type in (ConfigError, FetchError, LlmError, LlmUnavailable, StoreError, PolicyDenied):
        assert issubclass(error_type, OutreachError)
        assert isinstance(error_type("x"), OutreachError)
