import pytest

from electivesmed.clients.web.routes import settings as settings_routes
from electivesmed.components import config_writer, security
from electivesmed.errors import ConfigWriteError, LlmError

from tests.clients.web.conftest import TEST_PASSWORD, TEST_USER
from tests.fakes import FakeLlm


def test_settings_page_renders_state(client):
    response = client.get("/settings")

    assert response.status_code == 200
    assert "Account" in response.text
    assert "Secrets" in response.text
    assert "Not set" in response.text


def test_save_env_writes_masked_secrets(client, container):
    response = client.post(
        "/settings/env",
        data={
            "smtp_host": "smtp.test",
            "smtp_port": "2525",
            "smtp_user": "user",
            "smtp_password": "app-password-1",
            "smtp_from": "me@example.org",
            "smtp_reply_to": "reply@example.org",
            "imap_host": "imap.test",
            "imap_user": "imap-user",
            "imap_password": "imap-secret-1",
            "deepseek_api_key": "sk-test-key",
        },
        follow_redirects=True,
    )

    assert "environment saved" in response.text
    path = settings_routes.env_path()
    text = path.read_text()
    assert "SMTP_HOST=smtp.test" in text
    assert "SMTP_PASSWORD=app-password-1" in text
    assert "DEEPSEEK_API_KEY=sk-test-key" in text
    assert oct(path.stat().st_mode & 0o777) == "0o600"

    assert container.mail.host == "smtp.test"
    assert container.mail.password == "app-password-1"
    assert container.llm.api_key == "sk-test-key"

    page = client.get("/settings")
    assert "app-password-1" not in page.text
    assert "Set ••••" in page.text


def test_save_env_keeps_and_clears_secret(client, container):
    client.post(
        "/settings/env",
        data={"deepseek_api_key": "sk-test-key"},
        follow_redirects=True,
    )
    client.post("/settings/env", data={}, follow_redirects=True)
    assert "DEEPSEEK_API_KEY=sk-test-key" in settings_routes.env_path().read_text()

    client.post(
        "/settings/env",
        data={"clear_deepseek_api_key": "true"},
        follow_redirects=True,
    )
    assert "DEEPSEEK_API_KEY" not in settings_routes.env_path().read_text()
    assert container.llm.api_key == ""


def test_save_env_write_failure(client, monkeypatch):
    def explode(updates, path):
        raise ConfigWriteError("environment file is read-only")

    monkeypatch.setattr(config_writer, "write_env_values", explode)
    response = client.post("/settings/env", data={}, follow_redirects=True)

    assert "read-only" in response.text


def test_save_config_updates_yaml_and_container(client, container):
    response = client.post(
        "/settings/config",
        data={
            "sender_name": "Dr Example",
            "sender_role": "Cardiologist",
            "sender_email": "me@example.org",
            "sender_reply_to": "reply@example.org",
            "sender_organization": "Example Clinic",
            "sender_postal_address": "1 Main St, Fresno, CA",
            "daily_send_cap": "25",
            "per_domain_cap": "1",
            "min_delay_seconds": "10",
            "max_delay_seconds": "20",
            "dry_run_default": "true",
            "include_opt_out": "true",
            "window_enabled": "false",
            "window_days": "1, 3",
            "window_start": "08:30",
            "window_end": "16:30",
            "eu_policy": "warn",
            "us_policy": "block",
            "retention_days": "365",
            "login_attempts": "7",
            "lockout_seconds": "30",
            "max_files": "4",
            "max_file_mb": "5",
            "max_total_mb": "9",
            "goal": "Find electives",
            "ask": "Open to a call?",
            "tone": "direct",
            "language": "en",
            "specialties": "Cardiology\nEmergency Medicine",
            "target_roles": "Program Director",
            "locations": "Berlin",
            "hospital_types": "University Hospital",
            "must_haves": "teaching",
            "avoid": "pediatrics",
        },
        follow_redirects=True,
    )

    assert "configuration saved" in response.text
    assert container.settings.sender.name == "Dr Example"
    assert container.settings.sender.postal_address == "1 Main St, Fresno, CA"
    assert container.settings.limits.daily_send_cap == 25
    assert container.settings.sending.window_days == [1, 3]
    assert container.settings.sending.window_enabled is False
    assert container.settings.compliance.eu_policy == "warn"
    assert container.settings.attachments.max_files == 4
    assert container.settings.web.login_attempts == 7
    assert container.settings.web.lockout_seconds == 30
    assert container.profile.specialties == ["Cardiology", "Emergency Medicine"]
    assert container.profile.goal == "Find electives"

    from electivesmed.di.config_loader import profile_path, settings_path

    assert settings_path().with_suffix(".yaml.bak").exists()
    assert profile_path().with_suffix(".yaml.bak").exists()


def test_save_config_rejects_invalid_values(client):
    response = client.post(
        "/settings/config", data={"eu_policy": "bogus"}, follow_redirects=True
    )

    assert "invalid settings" in response.text


def test_save_config_write_failure(client, monkeypatch):
    def explode(path, updates):
        raise ConfigWriteError("yaml is locked")

    monkeypatch.setattr(config_writer, "write_yaml_values", explode)
    response = client.post("/settings/config", data={}, follow_redirects=True)

    assert "yaml is locked" in response.text


def test_change_password_paths(client, container):
    wrong = client.post(
        "/settings/password",
        data={
            "current_password": "not-the-password",
            "new_password": "another-long-passphrase",
            "confirm": "another-long-passphrase",
        },
        follow_redirects=True,
    )
    assert "current password is incorrect" in wrong.text

    mismatch = client.post(
        "/settings/password",
        data={
            "current_password": TEST_PASSWORD,
            "new_password": "another-long-passphrase",
            "confirm": "different-passphrase-1",
        },
        follow_redirects=True,
    )
    assert "new passwords do not match" in mismatch.text

    weak = client.post(
        "/settings/password",
        data={"current_password": TEST_PASSWORD, "new_password": "short", "confirm": "short"},
        follow_redirects=True,
    )
    assert "at least" in weak.text

    ok = client.post(
        "/settings/password",
        data={
            "current_password": TEST_PASSWORD,
            "new_password": "another-long-passphrase",
            "confirm": "another-long-passphrase",
        },
        follow_redirects=True,
    )
    assert "password updated" in ok.text
    user = container.dao.find_user(TEST_USER)
    assert security.verify_password(
        "another-long-passphrase", user.password_hash, security.load_pepper()
    )


def test_connection_test_buttons(client, container, monkeypatch):
    monkeypatch.setattr(
        container.mail, "test_connection", lambda: (True, "connected to smtp.test")
    )
    ok = client.post("/settings/test-smtp", follow_redirects=True)
    assert "SMTP ok" in ok.text

    monkeypatch.setattr(container.mail, "test_connection", lambda: (False, "refused"))
    failed = client.post("/settings/test-smtp", follow_redirects=True)
    assert "SMTP failed: refused" in failed.text

    container.llm = FakeLlm(text_response="ok")
    llm_ok = client.post("/settings/test-llm", follow_redirects=True)
    assert "DeepSeek ok: ok" in llm_ok.text

    def explode(*args, **kwargs):
        raise LlmError("no credits")

    monkeypatch.setattr(container.llm, "chat_text", explode)
    llm_failed = client.post("/settings/test-llm", follow_redirects=True)
    assert "DeepSeek failed: no credits" in llm_failed.text


def test_save_env_clears_smtp_and_imap_passwords(client, container):
    client.post(
        "/settings/env",
        data={"smtp_password": "smtp-secret", "imap_password": "imap-secret"},
        follow_redirects=True,
    )
    response = client.post(
        "/settings/env",
        data={"clear_smtp_password": "true", "clear_imap_password": "true"},
        follow_redirects=True,
    )

    assert "environment saved" in response.text
    text = settings_routes.env_path().read_text()
    assert "SMTP_PASSWORD" not in text
    assert "IMAP_PASSWORD" not in text
    assert container.mail.password == ""
    assert container.inbox.password == ""
