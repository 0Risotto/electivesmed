"""SQLite schema definition, version, and migrations."""

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hospitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT,
    state TEXT,
    country TEXT DEFAULT '',
    website TEXT,
    hospital_type TEXT,
    ownership TEXT,
    beds INTEGER,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_url TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (name, city, state)
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL,
    name TEXT,
    title TEXT,
    department TEXT,
    email TEXT,
    country TEXT,
    timezone TEXT,
    lawful_basis TEXT NOT NULL DEFAULT 'unknown',
    source_url TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    fit_score REAL,
    fit_reasons TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    UNIQUE (email, hospital_id)
);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    goal TEXT NOT NULL,
    tone TEXT,
    language TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invocation_id TEXT NOT NULL,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    campaign_id INTEGER REFERENCES campaigns(id),
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    rationale TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    provider TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    approved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
CREATE TABLE IF NOT EXISTS sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invocation_id TEXT NOT NULL,
    draft_id INTEGER REFERENCES drafts(id),
    contact_id INTEGER REFERENCES contacts(id),
    message_id TEXT,
    to_email TEXT,
    status TEXT NOT NULL,
    error TEXT,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sends_sent_at ON sends(sent_at);
CREATE TABLE IF NOT EXISTS suppressions (
    email TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invocations (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    campaign_id INTEGER,
    status TEXT NOT NULL,
    input_json TEXT NOT NULL DEFAULT '{}',
    output_json TEXT,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
"""

# Applied in order when a stored database is older than SCHEMA_VERSION.
MIGRATIONS: dict[int, list[str]] = {
    2: [
        "ALTER TABLE contacts ADD COLUMN country TEXT",
        "ALTER TABLE contacts ADD COLUMN timezone TEXT",
        "ALTER TABLE contacts ADD COLUMN lawful_basis TEXT NOT NULL DEFAULT 'unknown'",
    ],
}
