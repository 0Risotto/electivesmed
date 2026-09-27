# Development guide

This document explains how the codebase is organized, how to work on it, and the conventions
that keep it consistent. For user-facing documentation see [README.md](README.md).

## Setup

### Nix (recommended on NixOS)

```bash
nix-shell
# shellHook creates .venv, runs `uv pip install -e ".[dev]"`, sets PYTHONPATH and LD_LIBRARY_PATH
```

### Generic

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"        # editable install exposes the `el` command
```

Editable install matters: the `el` console script resolves to the working tree, so code changes
apply immediately.

## Running tests

```bash
pytest                        # coverage runs automatically (addopts in pyproject.toml)
pytest tests/dao -q           # subset
pytest -k policy -vv          # by keyword
```

Policy enforced by `pyproject.toml`:

- `addopts = "--cov=electivesmed --cov-report=term-missing"` — coverage is always on
- `fail_under = 98` — the suite fails below 98%; the project currently sits at **100%**
- `__main__.py` is excluded; `if __name__ == "__main__":` lines are excluded

### Test isolation (important)

`tests/conftest.py` runs before any `electivesmed` import and:

- copies `config/settings.yaml` and `config/profile.yaml` into a temp root
- points `EL_SETTINGS_PATH`, `EL_PROFILE_PATH`, `EL_ENV_PATH`, `EL_PEPPER_PATH`,
  `EL_SESSION_KEY_PATH` at that temp root
- sets fast scrypt params (`EL_SCRYPT_N=16384`, …) **for tests only**; production defaults in
  `components/security.py` remain `N=2^17`

`tests/clients/web/conftest.py`:

- `client` fixture creates `tester` and logs in before yielding a `TestClient`
- an autouse fixture snapshots `os.environ` and the config files and restores them after each
  test (the Settings UI writes both)

Never write tests that touch the repository `config/` or `.env`; always go through the temp
paths or explicit `tmp_path` arguments.

## Architecture

Layers and dependency direction (arrows point inward; nothing imports *up*):

```
clients (cli, web)
    │ uses DTOs + services/actions
services (activities)   actions (side effects)
    │                       │
    ├── components (business rules: policy, scoring, extraction, email_style, security)
    ├── builders (prompts, payloads, agents)
    ├── accessors (mail, fetch, llm, reply)   ← external I/O
    └── dao (sqlite)                          ← storage
models / constants / utils / compliance / prompts (leaf modules, no I/O)
di (composition root: container + providers) wires everything
agent (invoker + manual_invocation audit wrapper)
```

| Package | Responsibility |
|---|---|
| `accessors/` | external calls only: SMTP, HTTP (robots-aware, cached), DeepSeek via LiteLLM, IMAP |
| `dao/` | SQLite protocol, schema, migrations, row mappers |
| `services/` | use-case orchestration: ingestion, extraction, scoring, sending, importing, attachments |
| `actions/` | side-effect primitives: save draft, suppression (policy-gated) |
| `components/` | injectable rules and utilities: `policy`, `scoring`, `extraction`, `email_style`, `security`, `config_writer` |
| `builders/` | construction of prompts, mail payloads, Strands agents |
| `tools/` | thin agent-facing wrappers over services/actions |
| `agent/` | `Invoker` (agent runs, invocation audit) and `manual_invocation` |
| `clients/cli`, `clients/web` | user interfaces; no business logic |
| `converters/` | mapping functions domain ↔ client DTOs |
| `models/` | pure data: entities, enums, values, config, views (DTOs), invocation |
| `prompts/` | prompt text only; rendering lives in `builders/prompts.py` |
| `di/` | container, providers, env/config loading |
| `constants/`, `utils/`, `compliance.py`, `paths.py` | leaf helpers |

Rules of thumb:

- **I/O lives in accessors/dao**, never in models, components, or clients.
- **Business rules live in components**; services orchestrate them with accessors/dao.
- **Clients render DTOs**; all mapping happens in converters.
- **All side effects go through the policy gate** (`components/policy.py`).
- **Every write is audited** with an `invocation_id` (agent runs via `Invoker`, manual actions
  via `manual_invocation`).

## Repository layout

```
src/electivesmed/
├── accessors/  actions/  agent/  builders/  clients/{cli,web}/
├── components/ constants/ converters/ dao/ di/ models/
├── prompts/ services/ tools/ utils/
tests/                      # mirrors src/ one-to-one
├── accessors/ actions/ agent/ builders/ clients/{cli,web}/
├── components/ converters/ dao/ di/ models/ services/ tools/ utils/
├── conftest.py             # env isolation + shared fixtures
├── constants.py            # scalar test constants
├── fakes.py                # FakeMail/FakeLlm/FakeFetch/FakeReply/HTTP fakes
└── test_context.py, test_errors.py, test_main.py
config/                     # profile.yaml, settings.yaml
data/samples/               # datasets used by tests and demos
```

## Database and migrations

Schema version lives in `dao/schema.py` (`SCHEMA_VERSION`). `SqliteDao.init_schema()`:

1. runs the full `SCHEMA` script (idempotent `CREATE TABLE IF NOT EXISTS`)
2. if `schema_meta` has no version → fresh DB, writes the current version
3. otherwise applies `MIGRATIONS[version+1 … SCHEMA_VERSION]` in order and updates the version

Tables: `schema_meta`, `hospitals`, `contacts`, `campaigns`, `drafts`, `sends`,
`suppressions`, `invocations`, `users`, `attachments`, `draft_attachments`,
`sent_attachments`. Row↔model mapping is isolated in `dao/mappers.py`.

### Adding a migration

```python
# dao/schema.py
SCHEMA_VERSION = 4

MIGRATIONS = {
    # …
    4: [
        "ALTER TABLE contacts ADD COLUMN linkedin TEXT",
    ],
}
```

Also update the base `SCHEMA` for fresh databases, the entity model, `mappers`, and the
insert/update methods. Add a migration test that builds a v(N-1) database by hand and asserts
the new shape (see `test_init_schema_migrates_v1_database`).

## Common tasks

### Add a data source parser

1. Create `services/ingestion/parsers/my_source.py` with
   `parse_my_source(http, entry, limit) -> list[Hospital]`. Only touch the HTTP accessor and
   models; never the DAO.
2. Register it in `services/ingestion/parsers/__init__.py` (`PARSERS` map by name/type).
3. Add a `SourceEntry` example to `config/settings.yaml`.
4. Tests: `tests/services/ingestion/parsers/test_my_source.py` with a sample payload in
   `data/samples/` and fixtures from `tests/conftest.py`.

### Add an agent tool

1. Implement the logic in a service (`services/…`) or component.
2. Add a thin wrapper in `tools/`:

```python
@tool
def my_tool(arg: str) -> dict:
    """One-line docstring the model reads to understand the tool."""
    return my_service(container, arg)
```

3. Wire it into `tools.build_read_tools` (safe, read-only) or `build_action_tools`
   (side effects). Scout gets only read tools; outreach gets both.
4. Test the wrapper directly (`tool("x")`) — Strands tool objects are callable.

### Add a side effect (action)

1. Put the implementation in `actions/` or `services/`.
2. Route every check through `components/policy.py`; never bypass it in a client.
3. Ensure an invocation context exists (`require_invocation()`), so the write is audited.
4. Expose it to the agent via `tools/actions.py` and/or to the UI via a route.

### Add a web page

1. New router in `clients/web/routes/`, prefix + handlers. Use `Depends(get_container)`,
   `Depends(get_runner)` for background jobs, and the shared `templates` environment.
2. Register it in `clients/web/app.py` (protected routers get
   `Depends(require_user)` + `Depends(check_origin)`; auth routes do not).
3. Template in `clients/web/templates/`, extending `base.html` and the MD3 classes in
   `static/md3.css` (`.card`, `.btn btn-filled`, `.field`, `.chip`, `.table-wrap`,
   `.dialog`, `.empty`, `.action-bar`, …).
4. Long work goes through `clients/web/jobs.py` + `BackgroundRunner`; return the
   `partials/invocation_status.html` partial and let it poll `/invocations/{id}/status`.
5. Tests in `tests/clients/web/routes/` using the authenticated `client` fixture.

### Add an attachment type

1. Add the extension → content-type mapping and its magic bytes in
   `services/attachments.py` (`_EXTENSION_TYPES`, `_SIGNATURES`).
2. Add the content type to `ALLOWED_ATTACHMENT_CONTENT_TYPES` in `compliance.py`.
3. Update the file input `accept=` list in `templates/documents.html`.
4. Tests: accept case + a mismatched-bytes rejection case in
   `tests/services/test_attachments.py`.

### Add a setting

1. Add the field to the right model in `models/config.py` (with a default).
2. Add it to `config/settings.yaml` with a comment.
3. Surface it in the `/settings` form and the `save_config` handler if it should be editable.
4. Use it from services/components (never from models).
5. Test defaults in `tests/models/test_config.py`.

### Add or edit a prompt

1. Prompt text lives in `prompts/*.py` (templates use `$placeholders`).
2. Rendering/values live in `builders/prompts.py`.
3. Copy rules (opt-out sentence, banned words/phrases) live in `compliance.py`; the style lint
   lives in `components/email_style.py`. Keep them in sync when adding rules.

## Conventions

- **No comments** unless they explain non-obvious *why*; names should carry the meaning.
- Type hints everywhere; Pydantic models for data crossing layers.
- DTOs live in `models/views.py`; converters only map, never do I/O.
- Clients (`cli`, `web`) must not import accessors or DAO directly; they use the container.
- Side effects are policy-gated and audited; read-only tooling must stay read-only.
- Keep modules single-purpose. If a file grows multiple concerns, split it (the codebase was
  deliberately organized this way — see the layer table).
- Errors: raise typed errors from `errors.py` (`PolicyDenied`, `AttachmentError`,
  `LlmError`, `SecurityError`, `ConfigWriteError`, …) and convert to user-facing messages at
  the edge.

## Security notes for contributors

- `components/security.py` owns hashing, sessions, and lockout. Do not weaken the defaults;
  `EL_SCRYPT_*` env overrides exist **only** so the test suite stays fast. A test asserts the
  real defaults.
- `data/pepper.key` and `data/session.key` are auto-created with 0600. Never log their
  contents, never commit them (gitignored).
- **Never delete or rotate `data/pepper.key` while accounts exist.** Every stored password
  hash is peppered with it, so a changed pepper makes all logins fail forever (by design).
  The login route now refuses to auto-create a pepper when users exist and tells the user to
  restore the key or run `el user set-password`. Check state with `el doctor`.
- Secrets are only written through `components/config_writer.py` (`write_env_values`,
  `write_yaml_values`) — atomic writes, 0600 for `.env`, `.bak` for YAML.
- The web UI must never render a secret back to the browser; only `Set ••••` / `Not set`.
- `deps.check_origin` guards state-changing requests; keep it on protected routers.

## Testing patterns

- Mirror `src/` layout: `tests/accessors/test_mail.py` ↔ `accessors/mail.py`.
- Shared fixtures in the nearest `conftest.py`: `container`, `seeded`, `approved`,
  `invocation_ctx`, `fake_mail`, `fake_llm`, `fake_fetch`, `open_window`, `cli_container`,
  `client` (authenticated), `inline_runner` (synchronous background jobs).
- Test doubles in `tests/fakes.py`; shared sample data in `data/samples/` loaded by fixtures
  (`cms_csv`, `cv_pdf`, `certificate_png`, `osm_response`, …).
- Scalar constants in `tests/constants.py` (`HOSPITAL_NAME`, `CONTACT_EMAIL`, `CLEAN_BODY`, …).
- Prefer asserting on returned dicts/DB state over HTML where possible; when asserting HTML,
  use stable copy (`style ok`, `No contacts`, `Dashboard`) that the templates guarantee.
- New behavior needs tests for the happy path, policy denials, and error branches — the
  100% coverage gate will tell you what is missing.

## Debugging

```bash
el send --dry-run                       # renders payloads without SMTP
el invocations                          # recent agent runs with invocation ids
el sources                              # configured ingest sources
sqlite3 data/electivesmed.db 'select id,agent_name,status,error from invocations order by started_at desc limit 5;'
find data/cache -type f | wc -l         # cached HTTP responses
```

- The HTTP cache makes repeat ingests instant; delete `data/cache/` to force fresh fetches.
- Robots.txt decisions and throttle state are per-process in `accessors/fetch.py`.
- The web UI shows invocation status and error output inline; the same data is in the
  `invocations` table.
- Settings changes hot-reload accessors and the policy gate; YAML edits are re-read on save.

## Git conventions

- Conventional commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`.
- Commit messages describe user-visible behavior; include migration/breaking notes.
- Before committing:

```bash
pytest                                # must be green at 100% coverage
git status --short                    # no .env, no *.key, no *.bak
```

- Never commit secrets, keys, or database files. `.gitignore` covers `.env`,
  `data/*.db*`, `data/pepper.key`, `data/session.key`, `config/*.yaml.bak`.

## Release checklist

1. Full suite green (527+ tests, 100% coverage).
2. `el web` smoke: `/setup` → login → dashboard → upload a document → dry-run preview.
3. `el ingest -s cms -n 5`, `el score`, `el send --dry-run` on a scratch DB.
4. README/DEVELOPMENT updated for new user-visible behavior.
5. Version bump in `pyproject.toml` and `constants/app.py` (`APP_VERSION`) when publishing.
