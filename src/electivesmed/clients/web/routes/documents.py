"""Documents: upload, list, download, delete, and default attachments."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from ....components import config_writer
from ....di import providers
from ....di.config_loader import settings_path
from ....errors import AttachmentError
from ....services.attachments import add_attachment, delete_attachment
from ..deps import get_container
from ..helpers import redirect_with_flash
from ..templating import templates

router = APIRouter(prefix="/documents")


@router.get("", response_class=HTMLResponse)
def documents_page(request: Request, container=Depends(get_container)):
    return templates.TemplateResponse(
        request,
        "documents.html",
        {
            "documents": container.dao.list_attachments(limit=500),
            "defaults": container.settings.attachments.defaults,
            "limits": container.settings.attachments,
        },
    )


@router.post("/upload")
def upload(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    container=Depends(get_container),
):
    saved: list[str] = []
    errors: list[str] = []
    for upload in files:
        if not upload.filename:
            continue
        data = upload.file.read()
        try:
            attachment = add_attachment(container, upload.filename, data)
            saved.append(attachment.filename)
        except AttachmentError as exc:
            errors.append(f"{upload.filename}: {exc}")
    if not saved and not errors:
        return redirect_with_flash("/documents", "no files selected")
    message = f"uploaded {len(saved)} document(s)" if saved else "nothing uploaded"
    if errors:
        message += " · " + "; ".join(errors[:3])
    return redirect_with_flash("/documents", message)


@router.get("/{attachment_id}/download")
def download(attachment_id: int, container=Depends(get_container)):
    attachment = container.dao.get_attachment(attachment_id)
    data = container.dao.get_attachment_data(attachment_id)
    if attachment is None or data is None:
        raise HTTPException(status_code=404, detail="document not found")
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )


@router.post("/{attachment_id}/delete")
def delete(request: Request, attachment_id: int, container=Depends(get_container)):
    if delete_attachment(container, attachment_id):
        return redirect_with_flash("/documents", "document deleted")
    return redirect_with_flash(
        "/documents", "cannot delete: document is referenced by sent history"
    )


@router.post("/defaults")
def set_defaults(
    request: Request,
    defaults: list[str] = Form(default=[]),
    container=Depends(get_container),
):
    config_writer.write_yaml_values(settings_path(), {"attachments": {"defaults": defaults}})
    providers.reload_settings(container)
    providers.refresh_accessors(container)
    return redirect_with_flash("/documents", f"{len(defaults)} default document(s) set")
