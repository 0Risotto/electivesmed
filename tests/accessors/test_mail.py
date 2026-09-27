import smtplib

import pytest

from electivesmed.accessors.mail import SmtpAccessor
from electivesmed.models.entities import MailPayload
from electivesmed.models.enums import SendStatus

from tests import constants as C


def _payload(**overrides) -> MailPayload:
    base = dict(
        to=C.CONTACT_EMAIL,
        from_email=C.SENDER_EMAIL,
        subject=C.DRAFT_SUBJECT,
        body_text=C.DRAFT_BODY,
        body_html="<p>Hello</p>",
    )
    base.update(overrides)
    return MailPayload(**base)


class _FakeSmtp:
    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        pass


def test_build_message_includes_headers_and_html():
    accessor = SmtpAccessor(
        host="smtp.test", port=587, from_email=C.SENDER_EMAIL, reply_to=C.REPLY_TO
    )
    message = accessor.build_message(
        _payload(headers={"List-Unsubscribe": "<mailto:reply@example.org>"})
    )
    assert message["To"] == C.CONTACT_EMAIL
    assert message["From"] == C.SENDER_EMAIL
    assert message["Reply-To"] == C.REPLY_TO
    assert message["Subject"] == C.DRAFT_SUBJECT
    assert message["Message-ID"]
    assert message["List-Unsubscribe"] == "<mailto:reply@example.org>"
    assert message.is_multipart()


def test_dry_run_returns_receipt_without_smtp():
    receipt = SmtpAccessor(host="", port=587).send(_payload(), dry_run=True)
    assert receipt.accepted
    assert receipt.status is SendStatus.DRY_RUN
    assert receipt.dry_run


def test_send_without_host_fails():
    receipt = SmtpAccessor(host="", port=587).send(_payload(), dry_run=False)
    assert not receipt.accepted
    assert receipt.status is SendStatus.FAILED
    assert "SMTP_HOST" in receipt.error


def test_send_success_uses_starttls_and_login(monkeypatch):
    sent: list = []
    logged: list = []

    class RecordingSmtp(_FakeSmtp):
        def login(self, user, password):
            logged.append((user, password))

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(smtplib, "SMTP", RecordingSmtp)
    accessor = SmtpAccessor(host="smtp.test", port=587, user="user", password="secret")
    receipt = accessor.send(_payload(), dry_run=False)

    assert receipt.status is SendStatus.SENT
    assert receipt.accepted
    assert logged == [("user", "secret")]
    assert len(sent) == 1


def test_send_failure_returns_failed_receipt(monkeypatch):
    class BrokenSmtp(_FakeSmtp):
        def send_message(self, message):
            raise RuntimeError("server rejected")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSmtp)
    receipt = SmtpAccessor(host="smtp.test", port=587).send(_payload(), dry_run=False)

    assert not receipt.accepted
    assert receipt.status is SendStatus.FAILED
    assert "server rejected" in receipt.error


def test_close_is_noop():
    assert SmtpAccessor(host="smtp.test", port=587).close() is None


def test_build_message_includes_validated_attachment():
    from electivesmed.models.entities import MailAttachment

    accessor = SmtpAccessor(host="smtp.test", port=587)
    payload = _payload(attachments=[MailAttachment(filename="cv.pdf", content_type="application/pdf", data=b"%PDF-1.4 fake")])
    message = accessor.build_message(payload)

    attachments = [part for part in message.walk() if part.get_filename()]
    assert attachments and attachments[0].get_filename() == "cv.pdf"


def test_send_rejects_oversized_attachments(monkeypatch):
    import electivesmed.accessors.mail as mail_module
    from electivesmed.models.entities import MailAttachment

    monkeypatch.setattr(mail_module, "SMTP_MAX_MESSAGE_BYTES", 10)
    accessor = SmtpAccessor(host="smtp.test", port=587)
    payload = _payload(attachments=[MailAttachment(filename="cv.pdf", content_type="application/pdf", data=b"x" * 50)])

    receipt = accessor.send(payload, dry_run=True)

    assert not receipt.accepted
    assert receipt.status is SendStatus.FAILED
    assert "message limit" in receipt.error


def test_test_connection_success(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)
    accessor = SmtpAccessor(host="smtp.test", port=587, user="u", password="p")

    ok, message = accessor.test_connection()

    assert ok
    assert "connected to smtp.test:587" in message


def test_test_connection_without_host():
    ok, message = SmtpAccessor(host="", port=587).test_connection()

    assert not ok
    assert "SMTP_HOST" in message


def test_test_connection_failure(monkeypatch):
    class Broken(_FakeSmtp):
        def login(self, user, password):
            raise RuntimeError("auth failed")

    monkeypatch.setattr(smtplib, "SMTP", Broken)
    accessor = SmtpAccessor(host="smtp.test", port=587, user="u", password="p")

    ok, message = accessor.test_connection()

    assert not ok
    assert "auth failed" in message
