from electivesmed.components.scoring import HeuristicScorer
from electivesmed.models.config import Profile
from electivesmed.models.entities import Contact

from tests import constants as C


def _scorer(**profile_overrides) -> HeuristicScorer:
    defaults = dict(
        target_roles=[C.CONTACT_TITLE],
        specialties=["Cardiology"],
        locations=[C.HOSPITAL_CITY],
        avoid=["Pediatrics"],
    )
    defaults.update(profile_overrides)
    return HeuristicScorer(Profile(**defaults))


def test_role_match_scores_higher():
    result = _scorer().score(Contact(name=C.CONTACT_NAME, title=C.CONTACT_TITLE))

    assert result.score >= 0.5
    assert any("role matches" in reason for reason in result.reasons)


def test_specialty_match_scores():
    result = _scorer().score(Contact(name="A", department="Cardiology"))

    assert any("specialty matches" in reason for reason in result.reasons)


def test_location_match_scores():
    result = _scorer().score(Contact(name="A", hospital_name=f"{C.HOSPITAL_CITY} General"))

    assert any("location matches" in reason for reason in result.reasons)


def test_avoid_list_caps_score():
    result = _scorer().score(Contact(name="A", department="Pediatrics"))

    assert result.score <= 0.1
    assert any("avoid-list" in reason for reason in result.reasons)


def test_no_matches_returns_baseline():
    result = _scorer().score(Contact(name="A", title="Groundskeeper"))

    assert result.score == 0.2
    assert result.reasons == ["no preference keywords matched contact fields"]


def test_full_alignment_scores_high():
    result = _scorer().score(
        Contact(
            name=C.CONTACT_NAME,
            title=C.CONTACT_TITLE,
            department="Cardiology",
            hospital_name=f"{C.HOSPITAL_CITY} General",
        )
    )

    assert result.score == 1.0
