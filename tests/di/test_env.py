import os

from electivesmed.di.env import load_env_file


def test_load_env_file_sets_variables(tmp_path, monkeypatch):
    monkeypatch.delenv("HO_TEST_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text('# comment\n\nHO_TEST_KEY=  spaced value  \nNOT_A_PAIR\n')

    load_env_file(path)

    assert os.environ["HO_TEST_KEY"] == "spaced value"


def test_load_env_file_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("HO_QUOTED_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("HO_QUOTED_KEY='quoted value'\n")

    load_env_file(path)

    assert os.environ["HO_QUOTED_KEY"] == "quoted value"


def test_load_env_file_does_not_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HO_TEST_KEY", "original")
    path = tmp_path / ".env"
    path.write_text("HO_TEST_KEY=replacement\n")

    load_env_file(path)

    assert os.environ["HO_TEST_KEY"] == "original"


def test_load_env_file_missing_is_noop(tmp_path):
    load_env_file(tmp_path / "does-not-exist.env")
