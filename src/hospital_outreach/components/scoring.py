"""Component: heuristic fit-scoring rules. No I/O."""

from ..models.entities import Contact
from ..models.values import FitScore


class HeuristicScorer:
    """Scores a contact against the sender profile using keyword alignment."""

    def __init__(self, profile) -> None:
        self._profile = profile

    def score(self, contact: Contact) -> FitScore:
        haystack = " ".join(
            part
            for part in (
                contact.name,
                contact.title,
                contact.department,
                contact.hospital_name,
            )
            if part
        ).lower()

        score = 0.2
        reasons: list[str] = []
        role_hits = [r for r in self._profile.target_roles if r.lower() in haystack]
        spec_hits = [s for s in self._profile.specialties if s.lower() in haystack]
        location_hits = [l for l in self._profile.locations if l.lower() in haystack]
        avoid_hits = [a for a in self._profile.avoid if a.lower() in haystack]

        if role_hits:
            score += 0.35
            reasons.append(f"role matches: {', '.join(role_hits)}")
        if spec_hits:
            score += 0.3
            reasons.append(f"specialty matches: {', '.join(spec_hits)}")
        if location_hits:
            score += 0.15
            reasons.append(f"location matches: {', '.join(location_hits)}")
        if avoid_hits:
            score = min(score, 0.1)
            reasons.append(f"avoid-list match: {', '.join(avoid_hits)}")
        if not reasons:
            reasons.append("no preference keywords matched contact fields")
        return FitScore(score=min(score, 1.0), reasons=reasons)
