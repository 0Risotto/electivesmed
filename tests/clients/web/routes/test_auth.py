from fastapi.testclient import TestClient

from electivesmed.clients.web.app import create_app
from electivesmed.components import security
from electivesmed.components.security import LoginThrottle

from tests.clients.web.conftest import TEST_PASSWORD, TEST_USER


def _create_user(container, username: str = TEST_USER, password: str = TEST_PASSWORD):
    container.dao.create_user(username, security.hash_password(password))


def test_first_run_redirects_to_setup(container):
    with TestClient(create_app(container=container)) as client:
        response = client.get("/")

        assert response.status_code == 200
        assert "Create your account" in response.text


def test_setup_flow_creates_account_and_signs_in(container):
    with TestClient(create_app(container=container)) as client:
        response = client.post(
            "/setup",
            data={"username": "owner", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD},
        )

        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert container.dao.find_user("owner") is not None

        again = client.get("/setup", follow_redirects=True)
        assert "Sign in" in again.text


def test_setup_validation_errors(container):
    with TestClient(create_app(container=container)) as client:
        missing = client.post(
            "/setup",
            data={"username": " ", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD},
            follow_redirects=True,
        )
        assert "username is required" in missing.text

        mismatch = client.post(
            "/setup",
            data={"username": "owner", "password": TEST_PASSWORD, "confirm": "different-pass-1"},
            follow_redirects=True,
        )
        assert "passwords do not match" in mismatch.text

        weak = client.post(
            "/setup",
            data={"username": "owner", "password": "short", "confirm": "short"},
            follow_redirects=True,
        )
        assert "at least" in weak.text
        assert container.dao.count_users() == 0


def test_login_page_redirects_to_setup_without_users(container):
    with TestClient(create_app(container=container)) as client:
        response = client.get("/login", follow_redirects=True)

        assert "Create your account" in response.text


def test_login_flow(container):
    _create_user(container)
    with TestClient(create_app(container=container)) as client:
        page = client.get("/login")
        assert "Sign in" in page.text
        assert "Create account" not in page.text  # remote clients cannot self-register

        wrong = client.post(
            "/login",
            data={"username": TEST_USER, "password": "wrong-password-1"},
            follow_redirects=True,
        )
        assert "invalid username or password" in wrong.text

        unknown = client.post(
            "/login",
            data={"username": "ghost", "password": "wrong-password-1"},
            follow_redirects=True,
        )
        assert "invalid username or password" in unknown.text

        success = client.post(
            "/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD, "next": "/drafts"},
        )
        assert success.status_code == 200
        assert "Drafts" in success.text

        client.post("/logout")
        protected = client.get("/drafts", follow_redirects=True)
        assert "Sign in" in protected.text


def test_login_lockout_after_failed_attempts(container):
    _create_user(container)
    app = create_app(container=container)
    with TestClient(app) as client:
        client.app.state.login_throttle = LoginThrottle(limit=1, window=60)

        client.post(
            "/login",
            data={"username": TEST_USER, "password": "wrong-password-1"},
            follow_redirects=True,
        )
        locked = client.post(
            "/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD},
            follow_redirects=True,
        )

        assert "too many attempts" in locked.text


def test_login_upgrades_weak_password_hash(container):
    pepper = security.load_pepper()
    weak = security.hash_password(TEST_PASSWORD, pepper, n=1024, r=8, p=1)
    container.dao.create_user(TEST_USER, weak)

    with TestClient(create_app(container=container)) as client:
        client.post("/login", data={"username": TEST_USER, "password": TEST_PASSWORD})

    stored = container.dao.find_user(TEST_USER).password_hash
    assert not security.needs_rehash(stored)


def test_unauthenticated_request_redirects_to_login(container):
    _create_user(container)
    with TestClient(create_app(container=container)) as client:
        response = client.get("/drafts", follow_redirects=True)

        assert "Sign in" in response.text


def test_cross_origin_post_is_rejected(client):
    response = client.post("/settings/password", headers={"Origin": "http://evil.example"})

    assert response.status_code == 403


def test_login_can_be_disabled(container):
    container.settings.web.require_login = False
    with TestClient(create_app(container=container)) as client:
        page = client.get("/")

        assert page.status_code == 200
        assert "Dashboard" in page.text

        unknown = client.post(
            "/settings/password",
            data={"current_password": "x", "new_password": "y", "confirm": "y"},
            follow_redirects=True,
        )
        assert "unknown user" in unknown.text


def test_setup_post_redirects_when_users_exist(container):
    _create_user(container)
    with TestClient(create_app(container=container)) as client:
        response = client.post(
            "/setup",
            data={"username": "other", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD},
            follow_redirects=True,
        )

        assert "Sign in" in response.text
        assert container.dao.count_users() == 1


def test_login_reports_missing_pepper_key(client, container, tmp_path, monkeypatch):
    monkeypatch.setenv("EL_PEPPER_PATH", str(tmp_path / "missing-pepper.key"))

    response = client.post(
        "/login",
        data={"username": TEST_USER, "password": TEST_PASSWORD},
        follow_redirects=True,
    )

    assert "pepper key is missing" in response.text
    assert not (tmp_path / "missing-pepper.key").exists()


def test_lockout_limits_come_from_settings(container):
    _create_user(container)
    container.settings.web.login_attempts = 1
    container.settings.web.lockout_seconds = 60

    with TestClient(create_app(container=container)) as client:
        client.post(
            "/login",
            data={"username": TEST_USER, "password": "wrong-password-1"},
            follow_redirects=True,
        )
        locked = client.post(
            "/login",
            data={"username": TEST_USER, "password": TEST_PASSWORD},
            follow_redirects=True,
        )

        assert "too many attempts" in locked.text


def test_local_failure_messages_are_helpful():
    from electivesmed.clients.web.routes.auth import _failure_message, _is_local

    assert _is_local("127.0.0.1") and _is_local("::1") and _is_local("localhost")
    assert not _is_local("10.0.0.5") and not _is_local(None)
    assert "no account named" in _failure_message("ghost", False, True)
    assert "incorrect password" in _failure_message("ghost", True, True)
    assert _failure_message("ghost", True, False) == "invalid username or password"


def test_local_user_can_create_additional_account(container, monkeypatch):
    _create_user(container)
    import electivesmed.clients.web.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_is_local", lambda host: True)

    with TestClient(create_app(container=container)) as client:
        page = client.get("/login")
        assert "Create account" in page.text

        created = client.post(
            "/setup",
            data={"username": "second", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD},
        )
        assert created.status_code == 200
        assert "Dashboard" in created.text
        assert container.dao.find_user("second") is not None

        duplicate = client.post(
            "/setup",
            data={"username": "second", "password": TEST_PASSWORD, "confirm": TEST_PASSWORD},
            follow_redirects=True,
        )
        assert "already exists" in duplicate.text
