from typer.testing import CliRunner

from hospital_outreach.clients.cli.app import app
from hospital_outreach.context import require_invocation
from hospital_outreach.di.providers import provide_container
from hospital_outreach.models.enums import AgentName, InvocationStatus

runner = CliRunner()


def test_invoker_records_invocation_and_sets_context(container):
    seen = {}

    class FakeAgent:
        def __call__(self, prompt):
            seen["invocation_id"] = require_invocation().invocation_id
            return "scout finished"

    container.invoker._agents[AgentName.SCOUT.value] = FakeAgent()
    result = container.invoker.invoke(AgentName.SCOUT, "find hospitals")

    assert result.ok
    assert seen["invocation_id"] == result.invocation_id
    stored = container.dao.get_invocation(result.invocation_id)
    assert stored.status == InvocationStatus.SUCCEEDED
    assert stored.output_json["summary"] == "scout finished"


def test_invoker_records_failure(container):
    class BrokenAgent:
        def __call__(self, prompt):
            raise RuntimeError("boom")

    container.invoker._agents[AgentName.SCOUT.value] = BrokenAgent()
    result = container.invoker.invoke(AgentName.SCOUT, "find hospitals")

    assert not result.ok
    assert "boom" in result.error
    assert container.dao.get_invocation(result.invocation_id).status == InvocationStatus.FAILED


def test_cli_init_and_status(tmp_path, monkeypatch):
    monkeypatch.setenv("HO_DB_PATH", str(tmp_path / "cli.db"))
    assert runner.invoke(app, ["init-db"]).exit_code == 0
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "hospitals" in result.output


def test_cli_import_csv(tmp_path, monkeypatch):
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HO_DB_PATH", str(db_path))
    csv_path = tmp_path / "contacts.csv"
    csv_path.write_text(
        "name,title,email,hospital_name,city,state\n"
        "Jane Doe,CMO,jane@example.org,Test Hospital,Fresno,CA\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["import-csv", str(csv_path)])
    assert result.exit_code == 0
    with provide_container(db_path=db_path) as container:
        summary = container.dao.summary()
        assert summary["hospitals"] == 1
        assert summary["contacts"] == 1
        assert summary["contacts_with_email"] == 1


def test_cli_suppress(tmp_path, monkeypatch):
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("HO_DB_PATH", str(db_path))
    result = runner.invoke(app, ["suppress", "someone@example.org", "--reason", "unsubscribe"])
    assert result.exit_code == 0
    with provide_container(db_path=db_path) as container:
        assert container.dao.is_suppressed("someone@example.org")
