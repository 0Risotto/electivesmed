import pytest

from electivesmed.models.values import EmailAddress, FitScore

from tests import constants as C


def test_email_address_normalizes():
    assert EmailAddress(value=" A.B@Hospital.ORG ").value == "a.b@hospital.org"
    assert str(EmailAddress(value=C.CONTACT_EMAIL)) == C.CONTACT_EMAIL


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "a b@c.org", ""])
def test_email_address_rejects_invalid(bad):
    with pytest.raises(ValueError):
        EmailAddress(value=bad)


def test_fit_score_clamps():
    assert FitScore(score=1.5).score == 1.0
    assert FitScore(score=-0.4).score == 0.0
    assert FitScore(score=0.5).reasons == []
