import subprocess

from electivesmed.clients.cli import editor
from electivesmed.models.views import DraftPreview

from tests import constants as C


def _preview() -> DraftPreview:
    return DraftPreview(
        id=1,
        to_name=C.CONTACT_NAME,
        to_email=C.CONTACT_EMAIL,
        hospital=C.HOSPITAL_NAME,
        subject=C.DRAFT_SUBJECT,
        body_text=C.DRAFT_BODY,
        rationale=None,
        confidence=0.5,
        status="pending",
        invocation_id=C.INVOCATION_ID,
    )


def _write_editor(call, subject: str, body: str):
    def fake_call(command):
        with open(command[-1], "w", encoding="utf-8") as handle:
            handle.write(f"Subject: {subject}\n\n{body}\n")
        return 0

    return fake_call


def test_edit_draft_returns_edited_content(monkeypatch):
    monkeypatch.setenv("EDITOR", "code --wait")
    monkeypatch.setattr(subprocess, "call", _write_editor(None, "New subject", "New body text."))

    result = editor.edit_draft(_preview())

    assert result is not None
    assert result.subject == "New subject"
    assert "New body text." in result.body_text


def test_edit_draft_keeps_subject_when_missing(monkeypatch):
    monkeypatch.setenv("EDITOR", "vi")
    monkeypatch.setattr(subprocess, "call", _write_editor(None, "", "Body only."))

    result = editor.edit_draft(_preview())

    assert result.subject == C.DRAFT_SUBJECT
    assert result.body_text == "Body only."


def test_edit_draft_returns_none_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "call", lambda command: 1)

    assert editor.edit_draft(_preview()) is None


def test_edit_draft_swallows_launch_errors(monkeypatch):
    def explode(command):
        raise RuntimeError("editor missing")

    monkeypatch.setattr(subprocess, "call", explode)

    assert editor.edit_draft(_preview()) is None


def test_edit_draft_returns_none_when_body_empty(monkeypatch):
    monkeypatch.setattr(subprocess, "call", _write_editor(None, "Subject", ""))

    assert editor.edit_draft(_preview()) is None


def test_editor_command_uses_env(monkeypatch):
    monkeypatch.setenv("EDITOR", "code --wait")

    assert editor._editor_command() == ["code", "--wait"]


def test_editor_command_defaults_to_vi(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)

    assert editor._editor_command() == ["vi"]


def test_editor_command_defaults_to_notepad_on_windows(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setattr(editor.os, "name", "nt")

    assert editor._editor_command() == ["notepad"]
