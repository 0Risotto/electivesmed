"""$EDITOR interaction for reviewing draft emails (cross-platform)."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from ...models.views import DraftEdit, DraftPreview


def _editor_command() -> list[str]:
    raw = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if raw:
        return shlex.split(raw, posix=(os.name != "nt"))
    return ["notepad"] if os.name == "nt" else ["vi"]


def edit_draft(preview: DraftPreview) -> DraftEdit | None:
    """Open the draft in $EDITOR (notepad on Windows) and return the edited subject/body."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".draft.txt", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(f"Subject: {preview.subject}\n\n{preview.body_text}\n")
        path = handle.name
    try:
        code = subprocess.call([*_editor_command(), path])
    except Exception:
        return None
    if code != 0:
        return None
    content = Path(path).read_text(encoding="utf-8")
    Path(path).unlink(missing_ok=True)

    subject = preview.subject
    body_lines: list[str] = []
    for line in content.splitlines():
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip() or subject
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        return None
    return DraftEdit(subject=subject, body_text=body)
