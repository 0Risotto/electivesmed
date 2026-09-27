"""Value objects with validation."""

from pydantic import BaseModel, field_validator

_EMAIL_AT = "@"


class EmailAddress(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, v: str) -> str:
        v = v.strip().lower()
        local, _, domain = v.partition(_EMAIL_AT)
        if not local or not domain or "." not in domain or " " in v:
            raise ValueError(f"invalid email address: {v!r}")
        return v

    def __str__(self) -> str:
        return self.value


class FitScore(BaseModel):
    score: float
    reasons: list[str] = []

    @field_validator("score")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))
