"""Typer CLI: the local interface to the whole pipeline."""

import getpass
from pathlib import Path

import typer
from rich.prompt import Confirm, Prompt

from ...actions.suppression import suppress as suppress_action
from ...agent.invoker import manual_invocation
from ...builders.prompts import default_scout_prompt, generate_prompt
from ...components import security
from ...converters.draft import draft_to_preview
from ...converters.invocation import invocation_to_view
from ...converters.summary import summary_to_view
from ...di.config_loader import profile_path, settings_path
from ...di.providers import provide_container
from ...errors import AttachmentError, SecurityError
from ...models.entities import Campaign
from ...models.enums import AgentName, DraftStatus
from ...services.attachments import add_attachment
from ...services.importing import import_contacts_csv
from ...services.ingestion import builtin_sources, configured_entries, fetch_source
from ...services.scoring import score_contacts
from ...services.sending import send_batch
from . import views
from .editor import edit_draft

app = typer.Typer(
    name="el",
    help="Local-first hospital scouting and personalized outreach. No AWS, no cloud.",
    no_args_is_help=True,
    add_completion=False,
)
user_app = typer.Typer(help="Local account management (scrypt + pepper).")
documents_app = typer.Typer(help="Attachment library: CVs, certificates, brochures.")
app.add_typer(user_app, name="user")
app.add_typer(documents_app, name="documents")


@app.command("init-db")
def init_db() -> None:
    """Create or migrate the local SQLite database."""
    with provide_container() as container:
        container.dao.init_schema()
        views.console.print("[green]database ready[/]")


@app.command()
def status() -> None:
    """Show pipeline status and remaining daily quota."""
    with provide_container() as container:
        summary = container.dao.summary()
        views.print_summary(
            summary_to_view(summary, container.settings.limits.daily_send_cap)
        )


@app.command()
def ingest(
    source: str = typer.Option("cms", "--source", "-s", help="Source name (see list-sources)"),
    limit: int = typer.Option(200, "--limit", "-n", help="Max hospital rows to ingest"),
) -> None:
    """Download and store public hospital data. No LLM required."""
    with provide_container() as container:
        views.print_json(fetch_source(container, source, limit))


@app.command("list-sources")
def list_sources() -> None:
    """List configured bulk data sources."""
    with provide_container() as container:
        views.print_json([s.model_dump(mode="json") for s in builtin_sources(container.settings)])


@app.command()
def sources() -> None:
    """List configured data sources with parser, country, and status."""
    with provide_container() as container:
        views.print_json(
            [
                {
                    "name": entry.name,
                    "type": entry.type,
                    "parser": entry.parser or entry.type,
                    "uri": entry.url or entry.path,
                    "country": entry.country or None,
                    "enabled": entry.enabled,
                }
                for entry in configured_entries(container.settings)
            ]
        )


@app.command("import-csv")
def import_csv(
    path: Path = typer.Argument(..., exists=True, readable=True, help="CSV of contacts"),
    hospital: str = typer.Option("", "--hospital", help="Default hospital name for rows"),
    source_url: str = typer.Option("", "--source-url"),
    country: str = typer.Option("", "--country", help="Default country code for rows"),
) -> None:
    """Import contacts from a CSV.

    Columns: name,title,department,email,hospital_name,city,state,country,
    timezone,lawful_basis,website.
    """
    with provide_container() as container:
        raw = path.read_text(encoding="utf-8-sig")
        result = import_contacts_csv(
            container,
            raw,
            source_url=source_url or str(path),
            hospital_name=hospital,
            country=country,
        )
        views.print_json({**result, "path": str(path)})


@app.command()
def scout(
    instructions: str = typer.Option("", "--instructions", "-i", help="Extra agent instructions"),
    campaign: str = typer.Option("", "--campaign", "-c", help="Optional campaign name"),
) -> None:
    """Run the scout agent to find hospitals, staff, and opportunities."""
    with provide_container() as container:
        if not container.llm.available:
            views.console.print(
                "[red]DEEPSEEK_API_KEY is not set.[/] Add it to .env, "
                "or use `ho ingest` / `ho import-csv` (no LLM needed)."
            )
            raise typer.Exit(code=1)
        campaign_id = None
        if campaign:
            existing = container.dao.get_campaign(campaign)
            campaign_id = existing.id if existing else None
        prompt = default_scout_prompt(container, instructions)
        result = container.invoker.invoke(AgentName.SCOUT, prompt, campaign_id=campaign_id)
        views.print_invocation_result(result)
        if not result.ok:
            raise typer.Exit(code=1)


@app.command()
def score(
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Score stored contacts against your profile (LLM if key set, heuristic otherwise)."""
    with provide_container() as container:
        views.print_json(score_contacts(container, limit=limit))


@app.command()
def generate(
    campaign: str = typer.Option(..., "--campaign", "-c", prompt=True),
    limit: int = typer.Option(5, "--limit", "-n"),
    min_score: float = typer.Option(0.3, "--min-score"),
    instructions: str = typer.Option("", "--instructions", "-i"),
) -> None:
    """Run the outreach agent to draft personalized emails for top contacts."""
    with provide_container() as container:
        if not container.llm.available:
            views.console.print(
                "[red]DEEPSEEK_API_KEY is not set.[/] Drafting needs the LLM accessor."
            )
            raise typer.Exit(code=1)
        prepared = container.dao.get_campaign(campaign) or Campaign(
            name=campaign,
            goal=container.profile.goal,
            tone=container.profile.tone,
            language=container.profile.language,
        )
        campaign_id = container.dao.upsert_campaign(prepared)

        contacts = [
            c
            for c in container.dao.find_contacts(scored_only=True, limit=limit * 3)
            if (c.fit_score or 0.0) >= min_score
        ][:limit]
        if not contacts:
            contacts = container.dao.find_contacts(with_email_only=True, limit=limit)
        if not contacts:
            views.console.print("[yellow]no contacts available; run `ho ingest` and `ho score` first[/]")
            raise typer.Exit(code=1)

        prompt = generate_prompt(container, prepared, contacts, instructions)
        result = container.invoker.invoke(AgentName.OUTREACH, prompt, campaign_id=campaign_id)
        views.print_invocation_result(result)
        pending = container.dao.find_drafts(DraftStatus.PENDING, limit=limit)
        if pending:
            views.print_drafts_table(
                [
                    draft_to_preview(d, container.dao.get_contact(d.contact_id))
                    for d in pending
                ]
            )
        if not result.ok:
            raise typer.Exit(code=1)


@app.command()
def review(
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """Approve, edit, reject, or suppress pending drafts."""
    with provide_container() as container:
        drafts = container.dao.find_drafts(DraftStatus.PENDING, limit=limit)
        if not drafts:
            views.console.print("no pending drafts")
            raise typer.Exit()
        for draft in drafts:
            if draft.id is None:
                continue
            contact = container.dao.get_contact(draft.contact_id)
            preview = draft_to_preview(draft, contact)
            views.print_draft_full(preview)
            choice = Prompt.ask(
                "[a]pprove / [e]dit / [r]eject / [s]uppress / [k]skip / [q]uit",
                choices=["a", "e", "r", "s", "k", "q"],
                default="a",
            )
            if choice == "q":
                break
            if choice == "k":
                continue
            if choice == "a":
                container.dao.set_draft_status(draft.id, DraftStatus.APPROVED)
                views.console.print(f"[green]approved draft #{draft.id}[/]")
            elif choice == "r":
                container.dao.set_draft_status(draft.id, DraftStatus.REJECTED)
                views.console.print(f"[yellow]rejected draft #{draft.id}[/]")
            elif choice == "s":
                if contact and contact.email_value:
                    suppress_action(container, contact.email_value, "review")
                container.dao.set_draft_status(draft.id, DraftStatus.REJECTED)
                views.console.print(f"[yellow]suppressed and rejected draft #{draft.id}[/]")
            elif choice == "e":
                edit = edit_draft(preview)
                if edit is None:
                    views.console.print("edit cancelled")
                    continue
                container.dao.update_draft_body(
                    draft.id,
                    edit.subject or preview.subject,
                    edit.body_text or preview.body_text,
                    edit.body_html,
                )
                if Confirm.ask("approve edited draft?", default=True):
                    container.dao.set_draft_status(draft.id, DraftStatus.APPROVED)
                    views.console.print(f"[green]approved edited draft #{draft.id}[/]")


@app.command()
def send(
    draft_id: int = typer.Option(None, "--draft", "-d", help="Send a single draft by id"),
    dry_run: bool = typer.Option(None, "--dry-run/--no-dry-run", help="Override dry-run default"),
    limit: int = typer.Option(10, "--limit", "-n"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the real-send confirmation"),
    force_window: bool = typer.Option(
        False, "--force-window", help="Send even outside the recipient's local send window"
    ),
) -> None:
    """Send approved drafts via SMTP. Dry-run by default."""
    with provide_container() as container:
        effective_dry_run = (
            container.settings.sending.dry_run_default if dry_run is None else dry_run
        )
        draft_ids = [draft_id] if draft_id else None
        approved = (
            draft_ids
            or [
                d.id
                for d in container.dao.find_drafts(DraftStatus.APPROVED, limit=limit)
                if d.id is not None
            ]
        )
        if not approved:
            views.console.print("[yellow]no approved drafts to send[/]")
            raise typer.Exit()
        if not effective_dry_run and not yes:
            if not Confirm.ask(f"Send up to {len(approved)} real emails now?", default=False):
                raise typer.Exit()

        with manual_invocation(container, "cli-send") as run:
            result = send_batch(
                container, draft_ids, limit, effective_dry_run, force_window
            )
            run.output.update(result)
        views.print_send_results(result)


@app.command()
def suppress(
    email: str = typer.Argument(...),
    reason: str = typer.Option("manual", "--reason", "-r"),
) -> None:
    """Add an address to the do-not-contact list."""
    with provide_container() as container:
        views.print_json(suppress_action(container, email, reason))


@app.command()
def invocations(
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """List recent agent runs and their invocation ids."""
    with provide_container() as container:
        rows = [invocation_to_view(i) for i in container.dao.find_invocations(limit)]
        views.print_invocations(rows)


@app.command("export-contact")
def export_contact(email: str = typer.Argument(...)) -> None:
    """Export every stored record for an email address (GDPR/CCPA access)."""
    with provide_container() as container:
        views.print_json(container.dao.export_contact(email))


@app.command("erase-contact")
def erase_contact(email: str = typer.Argument(...)) -> None:
    """Erase stored data for an email address and suppress it (GDPR/CCPA erasure)."""
    with provide_container() as container:
        views.print_json(container.dao.erase_contact(email))


@app.command()
def purge(
    older_than: int = typer.Option(
        None, "--older-than", help="Retention in days; defaults to settings.compliance.retention_days"
    ),
) -> None:
    """Delete records older than the retention window."""
    with provide_container() as container:
        days = (
            older_than
            if older_than is not None
            else container.settings.compliance.retention_days
        )
        views.print_json(container.dao.purge_older_than(days))


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (localhost by default)"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Serve the local web UI (FastAPI + Jinja + HTMX)."""
    import uvicorn

    from ..web.app import create_app

    uvicorn.run(create_app(), host=host, port=port)


@app.command()
def doctor() -> None:
    """Diagnose local setup: database, keys, config paths, and providers."""
    with provide_container() as container:
        pepper = security.resolve_pepper_path()
        session = security.resolve_session_key_path()
        views.print_json(
            {
                "db_path": str(getattr(container.dao, "db_path", "")),
                "users": container.dao.count_users(),
                "usernames": [user.username for user in container.dao.list_users()],
                "pepper_key": {"path": str(pepper), "present": pepper.exists()},
                "session_key": {"path": str(session), "present": session.exists()},
                "settings_path": str(settings_path()),
                "profile_path": str(profile_path()),
                "deepseek_key_set": container.llm.available,
                "smtp_configured": bool(container.mail.host),
                "login_required": container.settings.web.require_login,
                "sources": [entry.name for entry in configured_entries(container.settings)],
            }
        )


@user_app.command("set-password")
def user_set_password(
    username: str = typer.Option("ellectives", "--username", "-u"),
    password: str = typer.Option("", "--password", help="Omit to enter it securely"),
) -> None:
    """Create or update a local account (scrypt N=2^17 + pepper)."""
    with provide_container() as container:
        if not password:
            password = getpass.getpass("New password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                views.console.print("[red]passwords do not match[/]")
                raise typer.Exit(code=1)
        try:
            security.validate_password(password, username)
        except SecurityError as exc:
            views.console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        password_hash = security.hash_password(password)
        existing = container.dao.find_user(username)
        if existing is None:
            container.dao.create_user(username, password_hash)
            action = "created"
        else:
            container.dao.update_user_password(username, password_hash)
            action = "updated"
        views.console.print(f"[green]user {username!r} {action}[/]")


@user_app.command("list")
def user_list() -> None:
    """List local accounts."""
    with provide_container() as container:
        views.print_json(
            [
                {"username": user.username, "updated_at": user.updated_at.isoformat()}
                for user in container.dao.list_users()
            ]
        )


@documents_app.command("add")
def documents_add(
    path: Path = typer.Argument(..., exists=True, readable=True),
) -> None:
    """Add a document (PDF, PNG, JPG, DOC, DOCX) to the attachment library."""
    with provide_container() as container:
        try:
            attachment = add_attachment(container, path.name, path.read_bytes())
        except AttachmentError as exc:
            views.console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        views.print_json(
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size": attachment.size,
                "sha256": attachment.sha256[:16],
            }
        )


@documents_app.command("list")
def documents_list() -> None:
    """List documents in the attachment library."""
    with provide_container() as container:
        views.print_json(
            [
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                }
                for attachment in container.dao.list_attachments(limit=200)
            ]
        )
