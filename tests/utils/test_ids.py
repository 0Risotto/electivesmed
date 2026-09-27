from electivesmed.utils.ids import new_invocation_id


def test_new_invocation_id_is_prefixed_and_unique():
    first = new_invocation_id()
    second = new_invocation_id()

    assert first.startswith("inv_")
    assert first != second
    assert first.count("_") == 2
