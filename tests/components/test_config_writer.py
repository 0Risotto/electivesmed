import pytest
import yaml

from electivesmed.components.config_writer import write_env_values, write_yaml_values
from electivesmed.errors import ConfigWriteError


def test_env_update_insert_remove_and_permissions(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# comment\nSMTP_HOST=old\nKEEP=me\n")

    write_env_values(
        {"SMTP_HOST": "new", "SMTP_PORT": "587", "SMTP_PASSWORD": None, "DEEPSEEK_API_KEY": "sk-x"},
        path,
    )

    text = path.read_text()
    assert "# comment" in text
    assert "SMTP_HOST=new" in text
    assert "KEEP=me" in text
    assert "SMTP_PORT=587" in text
    assert "DEEPSEEK_API_KEY=sk-x" in text
    assert "SMTP_PASSWORD" not in text
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_env_removes_existing_secret(tmp_path):
    path = tmp_path / ".env"
    path.write_text("SMTP_PASSWORD=secret\n")

    write_env_values({"SMTP_PASSWORD": None}, path)

    assert "SMTP_PASSWORD" not in path.read_text()


def test_env_creates_missing_file(tmp_path):
    path = tmp_path / "nested" / ".env"

    write_env_values({"A": "1"}, path)

    assert path.read_text() == "A=1\n"


def test_yaml_deep_merge_and_backup(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("sender:\n  name: Old\nlimits:\n  daily_send_cap: 10\n")

    write_yaml_values(path, {"sender": {"name": "New"}, "attachments": {"defaults": ["cv.pdf"]}})

    merged = yaml.safe_load(path.read_text())
    assert merged["sender"]["name"] == "New"
    assert merged["limits"]["daily_send_cap"] == 10
    assert merged["attachments"]["defaults"] == ["cv.pdf"]

    backup = path.with_suffix(".yaml.bak")
    assert "name: Old" in backup.read_text()


def test_yaml_rejects_non_mapping(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("- just\n- a\n- list\n")

    with pytest.raises(ConfigWriteError):
        write_yaml_values(path, {"a": 1})


def test_write_failure_raises_and_cleans_temp_file(tmp_path, monkeypatch):
    import os as os_module

    from electivesmed.components import config_writer

    def explode(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os_module, "replace", explode)
    path = tmp_path / "settings.yaml"

    with pytest.raises(ConfigWriteError, match="disk full"):
        config_writer.write_yaml_values(path, {"a": 1})

    leftovers = [item for item in tmp_path.iterdir() if item.name.startswith(".tmp-")]
    assert leftovers == []
