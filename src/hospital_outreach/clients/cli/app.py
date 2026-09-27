"""Typer CLI: the local interface to the whole pipeline."""

import csv
import io
from pathlib import Path

import typer
from rich.prompt import Confirm, Prompt

from ...actions.suppression import suppress as suppress_action
from ...builders.prompts import default_scout_prompt, generate_prompt
from ...context import reset_invocation, set_invocation
from ...converters.contact import contact_from_input
from ...converters.draft import draft_to_preview
from ...converters.invocation import invocation_to_view
from ...converters.summary import summary_to_view
from ...di.providers import provide_container
from ...models.entities import Campaign, Hospital
from ...models.enums import AgentName, DraftStatus, InvocationStatus, SourceType
from ...models.invocation import Invocation, InvocationContext
from ...models.views import ContactInput
from ...services.ingestion import builtin_sources, fetch_source
from ...services.scoring import score_contacts
from ...services.sending import send_batch
from ...utils.ids import new_invocation_id
from . import views
from .editor import edit_draft

app = typer.Typer(
    name="ho",
    help="Local-first hospital scouting and personalized outreach. No AWS, no cloud.",
    no_args_is_help=True,
    add_completion=False,
)


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


@app.command("import-csv")
def import_csv(
    path: Path = typer.Argument(..., exists=True, readable=True, help="CSV of contacts"),
    hospital: str = typer.Option("", "--hospital", help="Default hospital name for rows"),
    source_url: str = typer.Option("", "--source-url"),
) -> None:
    """Import contacts from a CSV (columns: name,title,department,email,hospital_name,city,state,website)."""
    with provide_container() as container:
        raw = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        hospital_ids: dict[str, int] = {}
        contacts = []
        for row in reader:
            cleaned = {
                (key or "").strip().lower(): (value or "").strip()
                for key, value in row.items()
            }
            if not (cleaned.get("name") or cleaned.get("email")):
                continue
            hospital_name = (
                cleaned.get("hospital_name") or cleaned.get("hospital") or hospital
            )
            hospital_id = None
            if hospital_name:
                key = hospital_name.lower()
                if key not in hospital_ids:
                    hospital_ids[key] = container.dao.upsert_hospital(
                        Hospital(
                            name=hospital_name,
                            city=cleaned.get("city") or None,
                            state=cleaned.get("state") or None,
                            website=cleaned.get("website") or None,
                            source_type=SourceType.CSV,
                            source_url=source_url or str(path),
                        )
                    )
                hospital_id = hospital_ids[key]
            contacts.append(
                contact_from_input(
                    ContactInput(
                        name=cleaned.get("name") or None,
                        title=cleaned.get("title") or None,
                        department=cleaned.get("department") or None,
                        email=cleaned.get("email") or None,
                        hospital_name=hospital_name or None,
                        source_url=source_url or str(path),
                    ),
                    hospital_id,
                )
            )
        ids = container.dao.save_contacts(contacts)
        views.print_json({"rows_seen": len(contacts), "saved": len(ids), "path": str(path)})


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

        invocation_id = new_invocation_id()
        context = InvocationContext(invocation_id=invocation_id, agent_name="cli-send")
        container.dao.record_invocation(
            Invocation(
                id=invocation_id,
                agent_name="cli-send",
                status=InvocationStatus.RUNNING,
                input_json={"draft_ids": approved, "dry_run": effective_dry_run},
            )
        )
        token = set_invocation(context)
        try:
            result = send_batch(container, draft_ids, limit, effective_dry_run)
        finally:
            reset_invocation(token)
        container.dao.finish_invocation(
            invocation_id, InvocationStatus.SUCCEEDED, output=result
        )
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
