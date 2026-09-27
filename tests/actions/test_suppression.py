from electivesmed.actions.suppression import suppress


def test_suppress_normalizes_and_persists(container):
    result = suppress(container, "  Person@Example.ORG ", "unsubscribe")

    assert result["status"] == "suppressed"
    assert result["email"] == "person@example.org"
    assert container.dao.is_suppressed("person@example.org")
    assert container.dao.list_suppressions()[0].reason == "unsubscribe"


def test_suppress_rejects_invalid_email(container):
    result = suppress(container, "not-an-email")

    assert result["status"] == "error"
    assert not container.dao.is_suppressed("not-an-email")


def test_suppress_rejects_empty_email(container):
    assert suppress(container, "   ")["status"] == "error"
