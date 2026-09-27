from electivesmed.models.entities import Send
from electivesmed.models.enums import SendStatus
from electivesmed.services.attachments import add_attachment

from tests import constants as C


def test_documents_page_empty(client):
    response = client.get("/documents")

    assert response.status_code == 200
    assert "No documents yet" in response.text


def test_upload_valid_and_invalid(client, container, cv_pdf):
    response = client.post(
        "/documents/upload",
        files=[
            ("files", ("cv.pdf", cv_pdf, "application/pdf")),
            ("files", ("bad.txt", b"nope", "text/plain")),
        ],
        follow_redirects=True,
    )

    assert "uploaded 1 document(s)" in response.text
    assert "unsupported" in response.text
    assert [item.filename for item in container.dao.list_attachments()] == ["cv.pdf"]


def test_upload_without_files(client):
    response = client.post("/documents/upload", data={}, follow_redirects=True)

    assert "no files selected" in response.text


def test_download_and_missing(client, container, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)

    ok = client.get(f"/documents/{attachment.id}/download")

    assert ok.status_code == 200
    assert ok.content == cv_pdf
    assert client.get("/documents/999/download").status_code == 404


def test_delete_and_defaults(client, container, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)

    deleted = client.post(f"/documents/{attachment.id}/delete", follow_redirects=True)
    assert "document deleted" in deleted.text
    assert container.dao.list_attachments() == []

    add_attachment(container, "cv.pdf", cv_pdf)
    defaults = client.post(
        "/documents/defaults", data={"defaults": ["cv.pdf"]}, follow_redirects=True
    )
    assert "1 default document(s) set" in defaults.text
    assert container.settings.attachments.defaults == ["cv.pdf"]


def test_delete_blocked_when_referenced_by_send(client, container, cv_pdf):
    attachment = add_attachment(container, "cv.pdf", cv_pdf)
    send_id = container.dao.record_send(
        Send(invocation_id=C.INVOCATION_ID, status=SendStatus.SENT)
    )
    container.dao.record_sent_attachments(send_id, [attachment])

    response = client.post(f"/documents/{attachment.id}/delete", follow_redirects=True)

    assert "cannot delete" in response.text
    assert len(container.dao.list_attachments()) == 1


def test_upload_with_blank_filename_is_ignored(container):
    import io

    from electivesmed.clients.web.routes import documents as documents_routes

    class BlankUpload:
        filename = ""
        file = io.BytesIO(b"bytes")

    response = documents_routes.upload(None, [BlankUpload()], container)

    assert response.status_code == 303
    assert "no%20files%20selected" in response.headers["location"]
