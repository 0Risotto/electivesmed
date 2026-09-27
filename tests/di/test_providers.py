from electivesmed.accessors.fetch import DEFAULT_USER_AGENT
from electivesmed.di.providers import provide_container


def _settings_file(tmp_path, content: str = "") -> str:
    path = tmp_path / "settings.yaml"
    path.write_text(content)
    return str(path)


def test_provide_container_wires_all_dependencies(tmp_path):
    container = provide_container(
        settings_path=_settings_file(tmp_path),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "wire.db",
    )

    assert type(container.dao).__name__ == "SqliteDao"
    assert container.invoker is not None
    assert container.policy is not None
    assert container.policy.dao is container.dao
    container.close()


def test_container_close_is_safe_to_call_twice(tmp_path):
    container = provide_container(
        settings_path=_settings_file(tmp_path),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "close.db",
    )
    container.close()
    container.close()


def test_smtp_env_overrides_and_invalid_port_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.env.test")
    monkeypatch.setenv("SMTP_PORT", "not-a-number")

    container = provide_container(
        settings_path=_settings_file(tmp_path),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "smtp.db",
    )

    assert container.mail.host == "smtp.env.test"
    assert container.mail.port == 587
    container.close()


def test_user_agent_uses_default_when_unset(tmp_path):
    container = provide_container(
        settings_path=_settings_file(tmp_path, "sources:\n  user_agent: ''\n  cms_url: ''\n"),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "ua.db",
    )

    assert container.http.user_agent == DEFAULT_USER_AGENT
    container.close()


class _BrokenResource:
    def close(self):
        raise RuntimeError("cannot close")


def test_container_close_swallows_resource_errors(tmp_path):
    container = provide_container(
        settings_path=_settings_file(tmp_path),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "broken.db",
    )
    container.mail = _BrokenResource()
    container.inbox = _BrokenResource()

    container.close()


def test_container_works_as_context_manager(tmp_path):
    with provide_container(
        settings_path=_settings_file(tmp_path),
        profile_path=str(tmp_path / "missing-profile.yaml"),
        db_path=tmp_path / "ctx.db",
    ) as container:
        assert container.policy is not None
