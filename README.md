# electivesmed

Local-first hospital scouting and personalized outreach. It finds hospitals and staff from
public data, ranks them against your preferences, has DeepSeek write one personalized email
per person, and sends only what you approve — through your own SMTP account. No AWS, no cloud
services, no data leaves your machine except the LLM calls you configure and the emails you send.

```
sources → contacts → fit scores → AI drafts → human review → throttled SMTP send → audit
```

## Features

- **Scouting from public data**: CMS hospital dataset (US), OpenStreetMap Overpass
  (worldwide), Wikidata SPARQL (worldwide), or any CSV/file you add in settings
- **AI personalization**: DeepSeek drafts a unique email per recipient from their record
  (name, title, department, hospital, location) plus your profile — never inventing facts
- **Human in the loop**: drafts are `pending` until you approve them; nothing sends without you
- **Strict copy rules**: enforced in the prompt *and* by the policy gate — no em/en dashes,
  exclamation marks, emoji, spam words, or AI-cliché vocabulary
- **Compliance gates**: EU/EEA/UK recipients need a recorded lawful basis; US recipients need
  a postal address (CAN-SPAM); opt-out sentence and suppression list enforced on every send
- **Deliverability guardrails**: 50/day cap, 2 per domain/day, 60–180s throttle,
  recipient-local send window (Tue–Thu 09:00–17:00 by default), dry-run by default
- **Attachments**: upload your CV, certificates, or brochures once; defaults auto-attach to
  every new draft; per-draft override; validated by content and capped for email limits
- **Data rights**: export, erase, and retention purge commands for contacts
- **Audit trail**: every agent run and every send carries an `invocation_id` in SQLite
- **Two clients**: a full CLI (`el`) and a local Material Design 3 web UI (`el web`)

## Requirements

- Python 3.12+
- Optional: Nix (the included `shell.nix` sets everything up on NixOS)
- A DeepSeek API key for agent/scoring calls (`DEEPSEEK_API_KEY`)
- An SMTP account for real sends (app password recommended)
- `tzdata` is installed automatically (needed for send windows on Windows)

## Quick start

### NixOS / Nix

```bash
cd electivesmed
nix-shell          # creates .venv, installs the package editable, activates it
cp .env.example .env
el web             # http://127.0.0.1:8000 — first run opens /setup
```

### Any other system (Linux, macOS, Windows)

```bash
cd electivesmed
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
el web                             # or use the CLI directly
```

> The web UI requires you to create a local account on first run (`/setup`). Passwords are
> hashed with scrypt + pepper; see [Security](#security).

## Configure

There are three layers of configuration:

| What | Where | How to edit |
|---|---|---|
| Secrets (DeepSeek key, SMTP/IMAP app passwords) | `.env` (0600) | **Web UI → Settings**, or manually |
| App settings (sender, limits, window, compliance, attachments, sources) | `config/settings.yaml` | **Web UI → Settings**, or by hand |
| Your profile (goal, ask, tone, specialties, target roles, locations, avoid list) | `config/profile.yaml` | **Web UI → Settings**, or by hand |

The Settings page masks secrets (`Set ••••` / `Not set`), preserves `.env` comments, writes
files atomically with 0600 permissions for `.env`, and keeps one-deep `.bak` backups of YAML.
It also has **Test SMTP** (connects, STARTTLS, logs in — sends nothing) and **Test DeepSeek**
buttons.

## Web UI

```bash
el web                          # 127.0.0.1:8000
el web --port 8765
el web --host 0.0.0.0           # LAN exposure: login is mandatory, but treat this carefully
```

| Page | What you can do |
|---|---|
| Dashboard | pipeline stats, quota, getting-started checklist, recent agent runs |
| Contacts | search/filter, CSV import, score, run the scout agent, per-contact detail |
| Drafts | inbox by status, personalization editor with live style lint, regenerate, bulk approve/reject/suppress |
| Campaigns | create campaigns (goal/tone), generate drafts for top-fit contacts |
| Send | dry-run preview (rendered emails + attachments), typed-confirm real send, force-window override |
| Documents | upload/download/delete CVs and certificates, pick default attachments |
| Sources | inspect configured sources and run ingest |
| Compliance | suppression list, retention purge, policy status |
| Settings | account/password, secrets, sender, limits, window, compliance, attachments, profile |

Agent runs happen in the background; the UI polls the invocation row and shows progress and
the result summary.

## CLI

```bash
el --help
```

| Command | Purpose |
|---|---|
| `el init-db` | Create/migrate the local SQLite database |
| `el status` | Pipeline counts and remaining daily quota |
| `el ingest -s cms -n 200` | Pull a configured source (`cms`, `osm`, `wikidata`, custom) |
| `el sources` / `el list-sources` | Show configured sources |
| `el import-csv contacts.csv --country US` | Import contacts + hospitals from CSV |
| `el scout -i "teaching hospitals" -c spring` | Agent: find staff/opportunities from public pages |
| `el score -n 200` | Fit-score contacts (LLM if key, heuristic otherwise) |
| `el generate -c spring -n 10 --min-score 0.4` | Agent: draft personalized emails |
| `el review` | Approve / edit (`$EDITOR`) / reject / suppress pending drafts |
| `el send --dry-run` | Render everything, send nothing |
| `el send --no-dry-run -y` | Real send (throttled, capped, policy-gated) |
| `el send --no-dry-run --force-window` | Ignore the recipient send window |
| `el suppress someone@hospital.org -r unsubscribe` | Add to the do-not-contact list |
| `el invocations` | Recent agent runs and their invocation ids |
| `el export-contact EMAIL` | JSON export of everything stored for a contact |
| `el erase-contact EMAIL` | Delete the contact/drafts/sends and suppress the address |
| `el purge --older-than 365` | Retention cleanup (defaults to `compliance.retention_days`) |
| `el web` | Serve the web UI |
| `el user set-password -u NAME` | Create/update a local account (prompts securely) |
| `el documents add FILE` / `el documents list` | Manage the attachment library |

## Data sources

Configured in `config/settings.yaml` under `sources.entries`:

```yaml
sources:
  entries:
    - name: cms
      type: csv
      parser: cms_hospitals
      url: "https://data.cms.gov/…/download?format=csv"
      country: US
    - name: osm
      type: overpass
      url: "https://overpass-api.de/api/interpreter"
    - name: wikidata
      type: sparql
      url: "https://query.wikidata.org/sparql"
    - name: my_list
      type: file          # or csv with a url
      parser: generic_csv
      path: data/sources/my_hospitals.csv
      country: DE
```

Parsers: `cms_hospitals`, `generic_csv` (name/city/state/country/website columns),
`osm` (Overpass `amenity=hospital`), `wikidata` (SPARQL). HTTP access is robots-aware,
throttled, and cached in `data/cache/`.

**Note:** hospitals from bulk sources have no email addresses. Contacts come from your own
CSV, or from the scout agent reading public staff pages — extraction stores an email only if
it appears verbatim on the page; it never guesses addresses.

## How emails are personalized

1. `el score` (or the UI) ranks contacts against `config/profile.yaml`
2. `el generate` runs the outreach agent over the top contacts; it reads each record and calls
   `save_draft` with subject, body, rationale, and confidence
3. The policy gate validates the draft at save time and again at send time
4. You review in `el review` or the web editor: live style lint highlights violations
   (em dashes, AI clichés, word count), and "Rendered preview" shows the final email with the
   opt-out line and (for US recipients) your postal address footer
5. `el send` delivers through your SMTP with throttling, caps, suppression checks, and a
   recipient-local send window

## Attachments

- Upload PDF/PNG/JPG/DOC/DOCX in **Documents** (or `el documents add`). Files are validated by
  magic bytes, deduplicated by SHA-256, and stored in your local SQLite database.
- Pick **default attachments** — they are attached to every newly generated draft. Toggle them
  per draft in the editor.
- Limits (configurable): 10 MB per file, 5 files per email, 20 MB total; a 25 MB guard is
  enforced when building the MIME message.
- Sent attachments are snapshotted for audit and surfaced in dry-runs, results, and contact
  history.

## Safety and compliance

Every send passes through `components/policy.py`:

- requires an **approved** draft and a recipient email
- blocks **suppressed** addresses
- **EU/EEA/UK** recipients are blocked without a lawful basis (`consent`,
  `legitimate_interest_b2b`, `contract`, or per-country override); set `eu_policy: warn` to
  only warn
- **US** recipients require `sender.postal_address` (CAN-SPAM); set `us_policy: warn` to relax
- no em/en dashes, exclamation marks, emoji, spam trigger words, or AI-cliché terms
- opt-out sentence must be present (it is appended automatically if missing)
- daily and per-domain caps; dry-run is the default
- recipient-local send window (default Tue–Thu 09:00–17:00, `--force-window` to override)

Data rights: `el export-contact`, `el erase-contact`, and `el purge --older-than N`
(also available in the web UI). Erasure keeps only a minimal suppression record.

## Security

- **App accounts**: passwords hashed with scrypt `N=2^17, r=8, p=1, dklen=64`, 32-byte salt,
  and peppered with `data/pepper.key` (0600) — a stolen DB alone is not crackable. Hashes are
  upgraded on login if parameters change. Verification is constant-time; unknown usernames are
  compared against a dummy hash to avoid enumeration.
- **Sessions**: HMAC-SHA256-signed cookies (`data/session.key`, 0600), 12-hour expiry,
  SameSite=Lax, Origin checks on state-changing requests.
- **Lockout**: 5 failed logins per IP+username → 15-minute lockout.
- **Secrets**: SMTP app passwords and API keys cannot be hashed (they must be replayed to the
  provider). They live in `.env`, written only through Settings with atomic 0600 writes, and
  are never rendered back to the browser.
- `data/pepper.key`, `data/session.key`, `.env`, and config backups are gitignored.

## Files and locations

| Path | Contents |
|---|---|
| `data/electivesmed.db` | SQLite: hospitals, contacts, campaigns, drafts, sends, suppressions, invocations, users, attachments |
| `data/cache/` | HTTP response cache (robots-aware) |
| `data/pepper.key`, `data/session.key` | Local secrets, 0600, auto-generated |
| `data/samples/` | Sample datasets used by tests and demos |
| `config/profile.yaml` | Your scouting preferences |
| `config/settings.yaml` | App settings |
| `.env` | Secrets |

Back up `data/electivesmed.db` and `data/*.key`; that pair contains everything.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `el: command not found` | Activate the venv (`source .venv/bin/activate`) or run `python -m electivesmed` |
| `DEEPSEEK_API_KEY is not set` | Add it in Settings or `.env`; scouting/generation/LLM scoring need it (heuristic scoring and ingest do not) |
| Sends show `deferred` | Recipient-local time is outside the send window; wait or use `--force-window` |
| Sends show `denied` | Read the reason: approval, suppression, jurisdiction basis, missing postal address, caps, or style violations |
| SMTP fails | Use the Test SMTP button; check app password (Gmail needs 2FA + app password) and provider limits |
| LLM errors | Check Settings → Test DeepSeek; verify the key and credits |
| Slow first agent run | The first run builds the model and imports the LLM stack (~3–5 s), then it is fast |

## License

Not specified yet.
