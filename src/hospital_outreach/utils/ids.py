"""Identifier generation."""

import uuid

from ..constants.app import INVOCATION_PREFIX
from .time import utcnow


def new_invocation_id() -> str:
    stamp = utcnow().strftime("%Y%m%d%H%M%S")
    return f"{INVOCATION_PREFIX}_{stamp}_{uuid.uuid4().hex[:12]}"
