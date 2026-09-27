from electivesmed.utils.time import utcnow


def test_utcnow_is_timezone_aware():
    assert utcnow().tzinfo is not None
