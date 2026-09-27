"""Activity: score stored contacts against the sender profile and persist results."""

import json

from ..builders.prompts import scoring_system
from ..components.scoring import HeuristicScorer
from ..models.entities import Contact
from ..models.enums import ContactStatus
from ..models.values import FitScore


def _llm_scores(container, contacts: list[Contact]) -> dict[int, FitScore]:
    payload = [
        {
            "id": c.id,
            "name": c.name,
            "title": c.title,
            "department": c.department,
            "hospital": c.hospital_name,
        }
        for c in contacts
        if c.id is not None
    ]
    data = container.llm.chat_json(
        scoring_system(container.profile),
        json.dumps({"contacts": payload}, ensure_ascii=True),
    )
    scores: dict[int, FitScore] = {}
    for item in data.get("scores") or []:
        try:
            cid = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        reasons = [str(r) for r in (item.get("reasons") or [])][:3]
        try:
            scores[cid] = FitScore(score=float(item.get("score", 0.0)), reasons=reasons)
        except (TypeError, ValueError):
            continue
    return scores


def score_contacts(container, contact_ids: list[int] | None = None, limit: int = 50) -> dict:
    if contact_ids:
        contacts = [
            c for c in (container.dao.get_contact(cid) for cid in contact_ids) if c is not None
        ]
    else:
        contacts = container.dao.find_contacts(with_email_only=False, limit=limit)
    if not contacts:
        return {"scored": 0, "note": "no contacts found to score"}

    heuristic = HeuristicScorer(container.profile)
    if container.llm.available:
        scores = _llm_scores(container, contacts)
        method = "llm"
    else:
        scores = {}
        method = "heuristic"

    for contact in contacts:
        if contact.id is None:
            continue
        result = scores.get(contact.id) or heuristic.score(contact)
        container.dao.update_contact_fit(
            contact.id, result.score, result.reasons, ContactStatus.SCORED
        )

    scored = [
        {
            "id": c.id,
            "name": c.name,
            "title": c.title,
            "hospital": c.hospital_name,
            "fit_score": round((scores.get(c.id) or heuristic.score(c)).score, 3),
        }
        for c in contacts
        if c.id is not None
    ]
    scored.sort(key=lambda row: row["fit_score"], reverse=True)
    return {"method": method, "scored": len(scored), "top": scored[:10]}
