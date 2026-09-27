import electivesmed.main as main_module


def test_cli_delegates_to_typer_app(monkeypatch):
    called: list = []
    monkeypatch.setattr(main_module, "app", lambda: called.append(True))

    main_module.cli()

    assert called == [True]
