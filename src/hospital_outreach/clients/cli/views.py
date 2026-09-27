"""Render client DTOs. No I/O, no business logic."""

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...models.invocation import InvocationResult
from ...models.views import ContactView, DraftPreview, InvocationView, SummaryView

console = Console()


def print_json(data: object) -> None:
    console.print_json(json.dumps(data, default=str))


def print_summary(view: SummaryView) -> None:
    table = Table(title="hospital-outreach status", show_header=False, title_justify="left")
    table.add_column("metric", style="cyan")
    table.add_column("value", justify="right")
    rows = [
        ("hospitals", view.hospitals),
        ("contacts", view.contacts),
        ("contacts with email", view.contacts_with_email),
        ("contacts scored", view.contacts_scored),
        ("drafts pending", view.drafts_pending),
        ("drafts approved", view.drafts_approved),
        ("sent today", f"{view.sent_today} / {view.daily_cap} (remaining {view.remaining_today})"),
        ("sent total", view.sent_total),
        ("suppressed", view.suppressed),
    ]
    for metric, value in rows:
        table.add_row(metric, str(value))
    console.print(table)


def print_contacts(rows: list[ContactView]) -> None:
    table = Table(title=f"contacts ({len(rows)})")
    for column in ("id", "name", "title", "hospital", "email", "fit", "status"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            str(row.id),
            row.name or "-",
            (row.title or "-")[:32],
            (row.hospital or "-")[:32],
            row.email or "-",
            f"{row.fit_percent}%" if row.fit_percent is not None else "-",
            row.status,
        )
    console.print(table)


def print_drafts_table(rows: list[DraftPreview]) -> None:
    table = Table(title=f"drafts ({len(rows)})")
    for column in ("id", "to", "subject", "status", "confidence"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            str(row.id),
            row.to_email or "-",
            row.subject[:48],
            row.status,
            f"{row.confidence:.2f}",
        )
    console.print(table)


def print_draft_full(preview: DraftPreview) -> None:
    console.print(
        Panel(
            preview.body_text,
            title=f"draft #{preview.id} -> {preview.to_name or '?'} <{preview.to_email or '?'}>",
            subtitle=f"{preview.hospital or '?'} | confidence {preview.confidence:.2f} | {preview.invocation_id}",
            title_align="left",
            subtitle_align="left",
        )
    )
    console.print(f"[bold]Subject:[/] {preview.subject}")
    if preview.rationale:
        console.print(f"[dim]Rationale:[/] {preview.rationale}")
    console.print()


def print_invocation_result(result: InvocationResult) -> None:
    if result.ok:
        console.print(f"[green]invocation {result.invocation_id} succeeded[/]")
    else:
        console.print(f"[red]invocation {result.invocation_id} failed:[/] {result.error}")
    summary = (result.output or {}).get("summary")
    if summary:
        console.print(Panel(str(summary)[:4000], title="agent summary", title_align="left"))


def print_invocations(rows: list[InvocationView]) -> None:
    table = Table(title=f"invocations ({len(rows)})")
    for column in ("id", "agent", "status", "started", "error"):
        table.add_column(column)
    for row in rows:
        table.add_row(row.id, row.agent, row.status, row.started_at[:19], (row.error or "")[:40])
    console.print(table)


def print_send_results(result: dict) -> None:
    console.print(
        f"attempted={result.get('attempted', 0)} sent={result.get('sent', 0)} "
        f"dry_run={result.get('dry_run', 0)} denied={result.get('denied', 0)} "
        f"failed={result.get('failed', 0)}"
    )
    for row in result.get("results", []):
        status = row.get("status", "?")
        detail = row.get("reason") or row.get("error") or row.get("to") or ""
        console.print(f"  draft {row.get('draft_id', '?')}: {status} {detail}")
