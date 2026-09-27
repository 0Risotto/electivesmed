from fastapi.testclient import TestClient

import electivesmed.clients.web.app as app_module


def test_create_app_without_container_uses_and_closes_provider(container, monkeypatch):
    monkeypatch.setattr(app_module, "provide_container", lambda: container)
    closed: list = []
    monkeypatch.setattr(container, "close", lambda: closed.append(True))

    app = app_module.create_app()
    with TestClient(app) as client:
        assert client.get("/login").status_code == 200

    assert closed == [True]


def test_create_app_with_container_does_not_close_it(container):
    app = app_module.create_app(container=container)
    with TestClient(app) as client:
        assert client.get("/login").status_code == 200

    assert container.dao.summary()["hospitals"] == 0


def test_static_assets_are_served(client):
    for path in (
        "/static/md3.css",
        "/static/app.js",
        "/static/icons.svg",
        "/static/favicon.svg",
        "/static/htmx.min.js",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content, path
