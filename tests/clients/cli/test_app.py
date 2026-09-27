import electivesmed.clients.cli.app as app_module
from electivesmed.clients.cli.app import app
from electivesmed.di.providers import provide_container
from electivesmed.models.entities import Campaign
from electivesmed.models.enums import DraftStatus, InvocationStatus
from electivesmed.models.invocation import Invocation
from electivesmed.models.views import DraftEdit

from tests import constants as C
from tests.fakes import FakeLlm


# --------------------------------------------------------------- basic commands


def test_init_db(runner, cli_container):
    result = runner.invoke(app, ["init-db"])

    assert result.exit_code == 0
    assert "database ready" in result.output


def test_status(runner, cli_container):
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "hospitals" in result.output


def test_list_sources(runner, cli_container):
    result = runner.invoke(app, ["list-sources"])

    assert result.exit_code == 0
    assert "cms" in result.output


def test_ingest(runner, cli_container, fake_fetch):
    result = runner.invoke(app, ["ingest", "-s", "cms", "-n", "10"])

    assert result.exit_code == 0
    assert "hospitals_added_or_updated" in result.output
    assert cli_container.dao.summary()["hospitals"] == 2


def test_import_csv(runner, cli_container, contacts_csv):
    result = runner.invoke(app, ["import-csv", str(contacts_csv)])

    assert result.exit_code == 0
    assert cli_container.dao.summary()["contacts"] == 2
    assert cli_container.dao.summary()["hospitals"] == 2


# ------------------------------------------------------------------------ scout


def test_scout_requires_llm(runner, cli_container):
    cli_container.llm = FakeLlm(available=False)

    result = runner.invoke(app, ["scout"])

    assert result.exit_code == 1
    assert "DEEPSEEK_API_KEY" in result.output


def test_scout_runs_agent_with_campaign(runner, cli_container, stub_invoker):
    cli_container.llm = FakeLlm(available=True)
    cli_container.dao.upsert_campaign(Campaign(name=C.CAMPAIGN_NAME, goal=C.CAMPAIGN_GOAL))
    calls = stub_invoker(cli_container, summary="scouted")

    result = runner.invoke(app, ["scout", "-c", C.CAMPAIGN_NAME, "-i", "teaching hospitals"])

    assert result.exit_code == 0
    assert calls[0]["campaign_id"] is not None
    assert "teaching hospitals" in calls[0]["prompt"]


def test_scout_with_unknown_campaign_runs_without_id(runner, cli_container, stub_invoker):
    cli_container.llm = FakeLlm(available=True)
    calls = stub_invoker(cli_container)

    result = runner.invoke(app, ["scout", "-c", "missing"])

    assert result.exit_code == 0
    assert calls[0]["campaign_id"] is None


def test_scout_failure_exits_with_error(runner, cli_container, monkeypatch):
    from electivesmed.models.invocation import InvocationResult

    cli_container.llm = FakeLlm(available=True)
    monkeypatch.setattr(
        cli_container.invoker,
        "invoke",
        lambda *a, **k: InvocationResult(
            invocation_id="inv_fail",
            status=InvocationStatus.FAILED,
            error="agent exploded",
        ),
    )

    result = runner.invoke(app, ["scout"])

    assert result.exit_code == 1
    assert "agent exploded" in result.output


# ------------------------------------------------------------------------ score


def test_score_command_uses_heuristic_without_llm(runner, cli_container, seeded):
    cli_container.llm = FakeLlm(available=False)

    result = runner.invoke(app, ["score", "-n", "10"])

    assert result.exit_code == 0
    assert "heuristic" in result.output


# --------------------------------------------------------------------- generate


def test_generate_requires_llm(runner, cli_container):
    cli_container.llm = FakeLlm(available=False)

    result = runner.invoke(app, ["generate", "-c", C.CAMPAIGN_NAME])

    assert result.exit_code == 1


def test_generate_runs_agent(runner, cli_container, seeded, stub_invoker):
    cli_container.llm = FakeLlm(available=True)
    calls = stub_invoker(cli_container)

    result = runner.invoke(app, ["generate", "-c", C.CAMPAIGN_NAME])

    assert result.exit_code == 0
    assert calls and C.CAMPAIGN_NAME in calls[0]["prompt"]


def test_generate_lists_pending_drafts(runner, cli_container, seeded, stub_invoker):
    cli_container.llm = FakeLlm(available=True)
    stub_invoker(cli_container)

    result = runner.invoke(app, ["generate", "-c", C.CAMPAIGN_NAME])

    assert result.exit_code == 0
    assert C.DRAFT_SUBJECT[:20] in result.output


def test_generate_without_contacts_exits(runner, cli_container):
    cli_container.llm = FakeLlm(available=True)

    result = runner.invoke(app, ["generate", "-c", C.CAMPAIGN_NAME])

    assert result.exit_code == 1
    assert "no contacts" in result.output


# ----------------------------------------------------------------------- review


def test_review_approves(runner, cli_container, seeded, prompt_stub):
    prompt_stub(["a"])

    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0
    assert cli_container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.APPROVED


def test_review_rejects(runner, cli_container, seeded, prompt_stub):
    prompt_stub(["r"])

    runner.invoke(app, ["review"])

    assert cli_container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.REJECTED


def test_review_suppresses_and_rejects(runner, cli_container, seeded, prompt_stub):
    prompt_stub(["s"])

    runner.invoke(app, ["review"])

    assert cli_container.dao.is_suppressed(C.CONTACT_EMAIL)
    assert cli_container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.REJECTED


def test_review_skip_then_quit(runner, cli_container, seeded, prompt_stub, second_draft):
    second_draft(seeded["contact_id"])
    prompt_stub(["k", "q"])

    runner.invoke(app, ["review"])

    assert cli_container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.PENDING


def test_review_edits_and_approves(runner, cli_container, seeded, prompt_stub, confirm_stub, monkeypatch):
    prompt_stub(["e"])
    confirm_stub(True)
    monkeypatch.setattr(
        app_module,
        "edit_draft",
        lambda preview: DraftEdit(subject="Edited subject", body_text=C.CLEAN_BODY),
    )

    runner.invoke(app, ["review"])

    draft = cli_container.dao.get_draft(seeded["draft_id"])
    assert draft.subject == "Edited subject"
    assert draft.status is DraftStatus.APPROVED


def test_review_edit_cancel_leaves_pending(runner, cli_container, seeded, prompt_stub, monkeypatch):
    prompt_stub(["e"])
    monkeypatch.setattr(app_module, "edit_draft", lambda preview: None)

    result = runner.invoke(app, ["review"])

    assert "edit cancelled" in result.output
    assert cli_container.dao.get_draft(seeded["draft_id"]).status is DraftStatus.PENDING


def test_review_without_drafts(runner, cli_container):
    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0
    assert "no pending drafts" in result.output


# ------------------------------------------------------------------------- send


def test_send_without_approved_drafts_exits(runner, cli_container, fake_mail):
    result = runner.invoke(app, ["send"])

    assert result.exit_code == 0
    assert "no approved" in result.output


def test_send_dry_run_keeps_draft_approved(runner, cli_container, approved, fake_mail):
    result = runner.invoke(app, ["send", "--dry-run"])

    assert result.exit_code == 0
    assert "dry_run=1" in result.output
    assert cli_container.dao.get_draft(approved["draft_id"]).status is DraftStatus.APPROVED


def test_send_real_with_confirmation_flag(runner, cli_container, approved, fake_mail, open_window):
    result = runner.invoke(app, ["send", "--no-dry-run", "-y"])

    assert result.exit_code == 0
    assert "sent=1" in result.output
    assert cli_container.dao.get_draft(approved["draft_id"]).status is DraftStatus.SENT


def test_send_real_declined_confirmation(runner, cli_container, approved, fake_mail, confirm_stub):
    confirm_stub(False)

    result = runner.invoke(app, ["send", "--no-dry-run"])

    assert result.exit_code == 0
    assert not fake_mail.calls


def test_send_single_draft_by_id(runner, cli_container, approved, fake_mail):
    result = runner.invoke(app, ["send", "-d", str(approved["draft_id"]), "--dry-run"])

    assert result.exit_code == 0
    assert "dry_run=1" in result.output


# ------------------------------------------------------------------------- misc


def test_suppress_command(runner, cli_container):
    result = runner.invoke(app, ["suppress", "someone@example.org", "-r", "unsubscribe"])

    assert result.exit_code == 0
    assert cli_container.dao.is_suppressed("someone@example.org")


def test_invocations_command(runner, cli_container):
    cli_container.dao.record_invocation(
        Invocation(
            id="inv_cli",
            agent_name="scout",
            status=InvocationStatus.SUCCEEDED,
            input_json={},
        )
    )

    result = runner.invoke(app, ["invocations"])

    assert result.exit_code == 0
    assert "inv_cli" in result.output


def test_import_csv_tolerates_extra_columns(runner, cli_container, tmp_path):
    csv_path = tmp_path / "ragged.csv"
    csv_path.write_text("name,email\n,,\nJane Doe,jane@example.org\n", encoding="utf-8")

    result = runner.invoke(app, ["import-csv", str(csv_path)])

    assert result.exit_code == 0
    assert cli_container.dao.summary()["contacts"] == 1


def test_review_skips_drafts_without_id(runner, cli_container, monkeypatch):
    from electivesmed.models.entities import Draft

    monkeypatch.setattr(
        cli_container.dao,
        "find_drafts",
        lambda *args, **kwargs: [
            Draft(
                invocation_id=C.INVOCATION_ID,
                contact_id=1,
                subject="No id",
                body_text=C.DRAFT_BODY,
            )
        ],
    )

    result = runner.invoke(app, ["review"])

    assert result.exit_code == 0


def test_generate_failure_exits_with_error(runner, cli_container, seeded, monkeypatch):
    from electivesmed.models.invocation import InvocationResult

    cli_container.llm = FakeLlm(available=True)
    monkeypatch.setattr(
        cli_container.invoker,
        "invoke",
        lambda *args, **kwargs: InvocationResult(
            invocation_id="inv_fail",
            status=InvocationStatus.FAILED,
            error="drafting exploded",
        ),
    )

    result = runner.invoke(app, ["generate", "-c", C.CAMPAIGN_NAME])

    assert result.exit_code == 1
    assert "drafting exploded" in result.output


# ------------------------------------------------------------ worldwide/GDPR


def test_sources_command(runner, cli_container):
    result = runner.invoke(app, ["sources"])

    assert result.exit_code == 0
    output = result.output
    assert "cms" in output and "osm" in output and "wikidata" in output


def test_export_contact_command(runner, cli_container, seeded):
    result = runner.invoke(app, ["export-contact", C.CONTACT_EMAIL])

    assert result.exit_code == 0
    assert C.CONTACT_EMAIL in result.output
    assert "drafts" in result.output


def test_erase_contact_command(runner, cli_container, seeded):
    result = runner.invoke(app, ["erase-contact", C.CONTACT_EMAIL])

    assert result.exit_code == 0
    assert cli_container.dao.get_contact(seeded["contact_id"]) is None
    assert cli_container.dao.is_suppressed(C.CONTACT_EMAIL)


def test_purge_command_uses_explicit_days(runner, cli_container, seeded):
    result = runner.invoke(app, ["purge", "--older-than", "0"])

    assert result.exit_code == 0
    assert cli_container.dao.summary()["contacts"] == 0


def test_purge_command_uses_retention_default(runner, cli_container, seeded):
    cli_container.settings.compliance.retention_days = 0

    result = runner.invoke(app, ["purge"])

    assert result.exit_code == 0
    assert cli_container.dao.summary()["contacts"] == 0


def test_send_deferred_outside_window(runner, cli_container, approved, fake_mail, monkeypatch):
    import electivesmed.services.sending as sending_module
    from datetime import datetime, timezone

    monkeypatch.setattr(
        sending_module, "_now", lambda: datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc)
    )

    result = runner.invoke(app, ["send", "--no-dry-run", "-y"])

    assert result.exit_code == 0
    assert "deferred=1" in result.output
    assert not fake_mail.calls


def test_send_force_window_bypasses_window(runner, cli_container, approved, fake_mail, monkeypatch):
    import electivesmed.services.sending as sending_module
    from datetime import datetime, timezone

    monkeypatch.setattr(
        sending_module, "_now", lambda: datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc)
    )

    result = runner.invoke(app, ["send", "--no-dry-run", "-y", "--force-window"])

    assert result.exit_code == 0
    assert "sent=1" in result.output


def test_import_csv_country_column(runner, cli_container, tmp_path):
    csv_path = tmp_path / "eu_contacts.csv"
    csv_path.write_text(
        "name,email,hospital_name,country,lawful_basis\n"
        "Hans Weber,hans@klinik.de,Charité,DE,legitimate_interest_b2b\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import-csv", str(csv_path)])

    assert result.exit_code == 0
    contact = cli_container.dao.find_contacts(with_email_only=True)[0]
    assert contact.country == "DE"
    assert contact.lawful_basis == "legitimate_interest_b2b"


def test_import_csv_country_option(runner, cli_container, tmp_path):
    csv_path = tmp_path / "us_contacts.csv"
    csv_path.write_text(
        "name,email,hospital_name\nJane,jane@hospital.org,Test Hospital\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import-csv", str(csv_path), "--country", "US"])

    assert result.exit_code == 0
    contact = cli_container.dao.find_contacts(with_email_only=True)[0]
    assert contact.country == "US"


def test_web_command_starts_uvicorn(runner, monkeypatch):
    import sys
    import types

    calls: dict = {}
    fake_uvicorn = types.ModuleType("uvicorn")

    def fake_run(app, host, port):
        calls.update(app=app, host=host, port=port)

    fake_uvicorn.run = fake_run
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    import electivesmed.clients.web.app as web_app

    monkeypatch.setattr(web_app, "create_app", lambda: "APP")

    result = runner.invoke(app, ["web", "--host", "0.0.0.0", "--port", "9999"])

    assert result.exit_code == 0
    assert calls == {"app": "APP", "host": "0.0.0.0", "port": 9999}


# ------------------------------------------------------------ accounts + docs


def test_user_set_password_cli(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("EL_DB_PATH", str(db_path))

    created = runner.invoke(
        app,
        ["user", "set-password", "--username", "cli-user", "--password", "correct-horse-battery"],
    )
    assert created.exit_code == 0
    assert "created" in created.output

    with provide_container(db_path=db_path) as container:
        assert container.dao.find_user("cli-user") is not None

    updated = runner.invoke(
        app,
        ["user", "set-password", "--username", "cli-user", "--password", "another-long-passphrase"],
    )
    assert updated.exit_code == 0
    assert "updated" in updated.output


def test_user_set_password_rejects_weak(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("EL_DB_PATH", str(tmp_path / "users.db"))

    result = runner.invoke(
        app, ["user", "set-password", "--username", "cli-user", "--password", "short"]
    )

    assert result.exit_code == 1
    assert "at least" in result.output


def test_user_set_password_prompt_mismatch(runner, tmp_path, monkeypatch):
    import electivesmed.clients.cli.app as cli_module

    monkeypatch.setenv("EL_DB_PATH", str(tmp_path / "users.db"))
    answers = iter(["long-enough-passphrase", "different-passphrase"])
    monkeypatch.setattr(cli_module.getpass, "getpass", lambda prompt="": next(answers))

    result = runner.invoke(app, ["user", "set-password"])

    assert result.exit_code == 1
    assert "do not match" in result.output


def test_documents_add_and_list(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("EL_DB_PATH", str(tmp_path / "docs.db"))
    pdf_path = tmp_path / "cv.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nminimal")

    added = runner.invoke(app, ["documents", "add", str(pdf_path)])
    assert added.exit_code == 0
    assert "cv.pdf" in added.output

    listing = runner.invoke(app, ["documents", "list"])
    assert listing.exit_code == 0
    assert "cv.pdf" in listing.output


def test_documents_add_rejects_invalid_file(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("EL_DB_PATH", str(tmp_path / "docs.db"))
    bad_path = tmp_path / "cv.txt"
    bad_path.write_bytes(b"not a document")

    result = runner.invoke(app, ["documents", "add", str(bad_path)])

    assert result.exit_code == 1
    assert "unsupported" in result.output


def test_doctor_reports_local_state(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("EL_DB_PATH", str(tmp_path / "doctor.db"))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert '"users"' in result.output
    assert '"pepper_key"' in result.output
    assert '"db_path"' in result.output


def test_user_list_cli(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    monkeypatch.setenv("EL_DB_PATH", str(db_path))
    runner.invoke(
        app,
        ["user", "set-password", "--username", "hello", "--password", "correct-horse-battery"],
    )

    result = runner.invoke(app, ["user", "list"])

    assert result.exit_code == 0
    assert "hello" in result.output
