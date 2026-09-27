"""Action: manage the do-not-contact suppression list."""


def suppress(container, email: str, reason: str = "manual") -> dict:
    email = email.strip().lower()
    if not email or "@" not in email:
        return {"status": "error", "error": f"invalid email: {email!r}"}
    container.dao.add_suppression(email, reason)
    return {"status": "suppressed", "email": email, "reason": reason}
