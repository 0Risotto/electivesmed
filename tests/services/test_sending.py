from datetime import datetime, timezone

from electivesmed.models.entities import Contact
from electivesmed.models.enums import DraftStatus, SendStatus
from electivesmed.services.sending import send_batch, send_one

from tests import constants as C
from tests.fakes import FakeMail


def test_send_one_denied_without_approval(container, seeded, invocation_ctx, fake_mail):
    result = send_one(container, seeded["draft_id"], dry_run=True)

    assert result["status"] == "denied"
    assert not fake_mail.calls


def test_send_one_dry_run_returns_receipt(container, approved, invocation_ctx, fake_mail):
    result = send_one(container, approved["draft_id"], dry_run=True)

    assert result["status"] == SendStatus.DRY_RUN.value
    assert result["dry_run"]
    assert fake_mail.calls[0][1] is True
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.APPROVED


def test_send_one_real_send_marks_draft_sent(container, approved, invocation_ctx, open_window):
    container.mail = FakeMail(status=SendStatus.SENT)

    result = send_one(container, approved["draft_id"], dry_run=False)

    assert result["status"] == SendStatus.SENT.value
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.SENT
    assert container.dao.sends_today() == 1


def test_send_one_failed_send_marks_draft_failed(container, approved, invocation_ctx, open_window):
    container.mail = FakeMail(status=SendStatus.FAILED, accepted=False, error="smtp down")

    result = send_one(container, approved["draft_id"], dry_run=False)

    assert result["status"] == SendStatus.FAILED.value
    assert result["error"] == "smtp down"
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.SEND_FAILED


def test_send_one_unknown_draft(container, invocation_ctx):
    result = send_one(container, 4242, dry_run=True)

    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_send_one_unknown_contact(container, approved, invocation_ctx, monkeypatch):
    monkeypatch.setattr(container.dao, "get_contact", lambda contact_id: None)

    result = send_one(container, approved["draft_id"], dry_run=True)

    assert result["status"] == "error"


def test_send_batch_noop_without_approved_drafts(container, invocation_ctx):
    assert send_batch(container)["status"] == "noop"


def test_send_batch_counts_denied(container, seeded, invocation_ctx, fake_mail):
    result = send_batch(container, draft_ids=[seeded["draft_id"]], dry_run=True)

    assert result["denied"] == 1
    assert result["sent"] == 0


def test_send_batch_dry_run_counts(
    container, approved, invocation_ctx, fake_mail, approved_draft_factory
):
    approved_draft_factory(approved["contact_id"])

    result = send_batch(container, limit=10, dry_run=True)

    assert result["attempted"] == 2
    assert result["dry_run"] == 2


def test_send_batch_real_sends_with_zero_delay(
    container, approved, invocation_ctx, approved_draft_factory, open_window
):
    container.settings.limits.min_delay_seconds = 0
    container.settings.limits.max_delay_seconds = 0
    container.mail = FakeMail(status=SendStatus.SENT)
    second_id = approved_draft_factory(approved["contact_id"], subject="Second")

    result = send_batch(
        container, draft_ids=[approved["draft_id"], second_id], dry_run=False
    )

    assert result["sent"] == 2
    assert result["failed"] == 0
    assert container.dao.sends_today() == 2


def test_send_batch_failed_send_is_counted(container, approved, invocation_ctx, open_window):
    container.mail = FakeMail(status=SendStatus.FAILED, accepted=False, error="smtp down")

    result = send_batch(container, draft_ids=[approved["draft_id"]], dry_run=False)

    assert result["failed"] == 1


def test_send_one_uses_sender_email_and_reply_to(container, approved, invocation_ctx, fake_mail):
    container.settings.sender.reply_to = C.REPLY_TO

    send_one(container, approved["draft_id"], dry_run=True)
    payload, _ = fake_mail.calls[0]

    assert payload.reply_to == C.REPLY_TO
    assert "List-Unsubscribe" in payload.headers


# ------------------------------------------------------------ send windows


def _freeze(monkeypatch, moment):
    import electivesmed.services.sending as sending_module

    monkeypatch.setattr(sending_module, "_now", lambda: moment)


def test_send_one_deferred_outside_window(container, approved, invocation_ctx, fake_mail, monkeypatch):
    # Saturday 03:00 UTC: outside the default Tue-Thu 09:00-17:00 UTC window.
    _freeze(monkeypatch, datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc))

    result = send_one(container, approved["draft_id"], dry_run=False)

    assert result["status"] == "deferred"
    assert "outside send window" in result["reason"]
    assert not fake_mail.calls
    assert container.dao.get_draft(approved["draft_id"]).status is DraftStatus.APPROVED


def test_send_one_force_window_bypasses_check(container, approved, invocation_ctx, monkeypatch):
    _freeze(monkeypatch, datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc))
    container.mail = FakeMail(status=SendStatus.SENT)

    result = send_one(container, approved["draft_id"], dry_run=False, force_window=True)

    assert result["status"] == SendStatus.SENT.value


def test_send_batch_counts_deferred(container, approved, invocation_ctx, fake_mail, monkeypatch):
    _freeze(monkeypatch, datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc))

    result = send_batch(container, draft_ids=[approved["draft_id"]], dry_run=False)

    assert result["deferred"] == 1
    assert result["sent"] == 0


def test_window_status_inside_local_window(container, monkeypatch):
    from electivesmed.services.sending import _window_status

    _freeze(monkeypatch, datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc))  # Tue 10:00 UTC
    assert _window_status(container.settings, Contact(country="DE")) is None


def test_window_status_outside_local_time(container, monkeypatch):
    from electivesmed.services.sending import _window_status

    _freeze(monkeypatch, datetime(2026, 1, 6, 3, 0, tzinfo=timezone.utc))  # Tue 04:00 Berlin

    reason = _window_status(container.settings, Contact(country="DE"))
    assert reason and "outside send window" in reason


def test_window_status_unknown_timezone_falls_back_to_utc(container, monkeypatch):
    from electivesmed.services.sending import _window_status

    _freeze(monkeypatch, datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc))

    assert _window_status(container.settings, Contact(timezone="Not/AZone")) is None


def test_window_status_disabled_returns_none(container, monkeypatch):
    from electivesmed.services.sending import _window_status

    _freeze(monkeypatch, datetime(2026, 1, 3, 3, 0, tzinfo=timezone.utc))
    container.settings.sending.window_enabled = False

    assert _window_status(container.settings, Contact(country="DE")) is None


def test_window_status_invalid_window_time_returns_none(container, monkeypatch):
    from electivesmed.services.sending import _window_status

    _freeze(monkeypatch, datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc))
    container.settings.sending.window_start = "bogus"

    assert _window_status(container.settings, Contact(country="DE")) is None


def test_now_returns_utc_timestamp():
    from electivesmed.services.sending import _now

    assert _now().tzinfo is not None
