"""Documents: validated attachment storage (CVs, certificates) in SQLite."""

import hashlib
from pathlib import Path

from ..errors import AttachmentError
from ..models.entities import Attachment, MailAttachment

_EXTENSION_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/msword": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        b"PK\x03\x04",
    ),
}


def detect_content_type(data: bytes, extension: str) -> str:
    """Verify magic bytes match the claimed extension; never trust the filename."""
    expected = _EXTENSION_TYPES.get(extension.lower())
    if expected is None:
        raise AttachmentError(
            f"unsupported file type {extension or '(none)'}; allowed: pdf, png, jpg, doc, docx"
        )
    for content_type, signatures in _SIGNATURES.items():
        if any(data.startswith(signature) for signature in signatures):
            if content_type != expected:
                raise AttachmentError(
                    f"file content ({content_type}) does not match extension {extension}"
                )
            return content_type
    raise AttachmentError("could not verify file content; upload a real PDF/PNG/JPG/DOC/DOCX")


def add_attachment(container, filename: str, data: bytes) -> Attachment:
    safe_name = Path(filename or "document").name or "document"
    if not data:
        raise AttachmentError("file is empty")
    max_bytes = container.settings.attachments.max_file_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise AttachmentError(
            f"file exceeds the {container.settings.attachments.max_file_mb} MB per-file limit"
        )
    content_type = detect_content_type(data, Path(safe_name).suffix)
    digest = hashlib.sha256(data).hexdigest()
    existing = container.dao.find_attachment_by_sha(digest)
    if existing is not None:
        return existing
    attachment = Attachment(
        filename=safe_name,
        content_type=content_type,
        size=len(data),
        sha256=digest,
        data=data,
    )
    attachment_id = container.dao.save_attachment(attachment)
    stored = container.dao.get_attachment(attachment_id)
    if stored is None:  # pragma: no cover - defensive
        raise AttachmentError("failed to store attachment")
    return stored


def attach_to_draft(container, draft_id: int, attachment_id: int) -> None:
    current = container.dao.find_draft_attachments(draft_id)
    if any(item.id == attachment_id for item in current):
        return
    limit = container.settings.attachments.max_files
    if len(current) >= limit:
        raise AttachmentError(f"at most {limit} attachments per email")
    container.dao.attach_to_draft(draft_id, attachment_id)


def attach_by_names(container, draft_id: int, names: list[str]) -> list[str]:
    library = {item.filename: item for item in container.dao.list_attachments(limit=500)}
    attached: list[str] = []
    for name in names:
        attachment = library.get(name.strip())
        if attachment is None:
            continue
        attach_to_draft(container, draft_id, attachment.id or 0)
        attached.append(attachment.filename)
    return attached


def attach_defaults(container, draft_id: int) -> list[str]:
    return attach_by_names(container, draft_id, container.settings.attachments.defaults)


def draft_attachments(container, draft_id: int) -> list[Attachment]:
    return container.dao.find_draft_attachments(draft_id)


def mail_attachments(container, draft_id: int) -> list[MailAttachment]:
    result: list[MailAttachment] = []
    for attachment in container.dao.find_draft_attachments(draft_id):
        data = container.dao.get_attachment_data(attachment.id or 0)
        if data is None:
            continue
        result.append(
            MailAttachment(
                filename=attachment.filename,
                content_type=attachment.content_type,
                data=data,
            )
        )
    return result


def remove_from_draft(container, draft_id: int, attachment_id: int) -> None:
    container.dao.detach_from_draft(draft_id, attachment_id)


def delete_attachment(container, attachment_id: int) -> bool:
    return container.dao.delete_attachment(attachment_id)
