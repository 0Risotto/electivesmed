import pytest

from electivesmed.errors import AttachmentError
from electivesmed.models.entities import Send
from electivesmed.models.enums import SendStatus
from electivesmed.services.attachments import (
    add_attachment,
    attach_by_names,
    attach_defaults,
    attach_to_draft,
    delete_attachment,
    draft_attachments,
    mail_attachments,
    remove_from_draft,
)

from tests import constants as C


def test_add_attachment_validates_and_stores(container, cv_pdf, certificate_png):
    pdf = add_attachment(container, "cv.pdf", cv_pdf)
    png = add_attachment(container, "certificate.png", certificate_png)

    assert pdf.filename == "cv.pdf"
    assert pdf.content_type == "application/pdf"
    assert pdf.size == len(cv_pdf)
    assert container.dao.get_attachment_data(pdf.id) == cv_pdf
    assert png.content_type == "image/png"


def test_add_attachment_deduplicates_by_sha(container, cv_pdf):
    first = add_attachment(container, "cv.pdf", cv_pdf)
    second = add_attachment(container, "cv-renamed.pdf", cv_pdf)

    assert first.id == second.id
    assert len(container.dao.list_attachments()) == 1


def test_add_attachment_strips_paths(container, cv_pdf):
    attachment = add_attachment(container, "../../etc/cv.pdf", cv_pdf)

    assert attachment.filename == "cv.pdf"


@pytest.mark.parametrize(
    "filename,data,message",
    [
        ("cv.txt", b"hello", "unsupported"),
        ("cv.exe", b"MZ\x90\x00", "unsupported"),
        ("cv.pdf", b"not really a pdf", "could not verify"),
        ("certificate.png", b"%PDF-1.4 fake", "does not match"),
        ("empty.pdf", b"", "empty"),
    ],
)
def test_add_attachment_rejections(container, filename, data, message):
    with pytest.raises(AttachmentError, match=message):
        add_attachment(container, filename, data)


def test_add_attachment_enforces_size_limit(container, cv_pdf):
    container.settings.attachments.max_file_mb = 0

    with pytest.raises(AttachmentError, match="per-file limit"):
        add_attachment(container, "cv.pdf", cv_pdf)


def test_attach_and_detach_draft(container, seeded, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)

    attach_to_draft(container, seeded["draft_id"], attachment.id)
    attach_to_draft(container, seeded["draft_id"], attachment.id)  # idempotent

    assert [item.filename for item in draft_attachments(container, seeded["draft_id"])] == [
        "cv.pdf"
    ]
    mail = mail_attachments(container, seeded["draft_id"])
    assert mail[0].data == cv_pdf

    remove_from_draft(container, seeded["draft_id"], attachment.id)
    assert draft_attachments(container, seeded["draft_id"]) == []


def test_attach_enforces_file_count(container, seeded, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    container.settings.attachments.max_files = 0

    with pytest.raises(AttachmentError, match="at most"):
        attach_to_draft(container, seeded["draft_id"], attachment.id)


def test_attach_by_names_and_defaults(container, seeded, cv_pdf, certificate_png):
    add_attachment(container, "cv.pdf", cv_pdf)
    add_attachment(container, "certificate.png", certificate_png)
    container.settings.attachments.defaults = ["cv.pdf", "missing.pdf"]

    assert attach_defaults(container, seeded["draft_id"]) == ["cv.pdf"]
    assert attach_by_names(container, seeded["draft_id"], ["certificate.png", "nope"]) == [
        "certificate.png"
    ]
    assert {item.filename for item in draft_attachments(container, seeded["draft_id"])} == {
        "cv.pdf",
        "certificate.png",
    }


def test_mail_attachments_skips_missing_data(container, seeded, cv_pdf, monkeypatch):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    attach_to_draft(container, seeded["draft_id"], attachment.id)
    monkeypatch.setattr(container.dao, "get_attachment_data", lambda attachment_id: None)

    assert mail_attachments(container, seeded["draft_id"]) == []


def test_delete_attachment_and_sent_reference_block(container, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    assert delete_attachment(container, attachment.id) is True

    second = add_attachment(container, "cv.pdf", cv_pdf)
    send_id = container.dao.record_send(
        Send(invocation_id=C.INVOCATION_ID, status=SendStatus.SENT)
    )
    container.dao.record_sent_attachments(send_id, [second])

    assert delete_attachment(container, second.id) is False
