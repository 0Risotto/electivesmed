"""Status and type enums (str-based for sqlite/JSON friendliness)."""

from enum import StrEnum


class ContactStatus(StrEnum):
    NEW = "new"
    ENRICHED = "enriched"
    SCORED = "scored"
    SKIPPED = "skipped"
    SUPPRESSED = "suppressed"


class DraftStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    SEND_FAILED = "send_failed"


class SendStatus(StrEnum):
    DRY_RUN = "dry_run"
    SENT = "sent"
    FAILED = "failed"


class InvocationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SourceType(StrEnum):
    CMS_DATASET = "cms_dataset"
    HOSPITAL_SITE = "hospital_site"
    CSV = "csv"
    FILE = "file"
    OSM_OVERPASS = "overpass"
    WIKIDATA = "wikidata"
    MANUAL = "manual"


class AgentName(StrEnum):
    SCOUT = "scout"
    OUTREACH = "outreach"
