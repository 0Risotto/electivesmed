import os
import time

import pytest

from electivesmed.components import security
from electivesmed.errors import SecurityError


def test_hash_format_and_verify(tmp_path):
    pepper = security.load_pepper(tmp_path / "pepper.key")
    stored = security.hash_password("correct-horse-battery", pepper)

    assert stored.startswith("scrypt$")
    assert security.verify_password("correct-horse-battery", stored, pepper)
    assert not security.verify_password("wrong-password-123", stored, pepper)


def test_verify_rejects_malformed_hashes(tmp_path):
    pepper = security.load_pepper(tmp_path / "pepper.key")

    for malformed in ("", "not-a-hash", "bcrypt$1$2$3$4$5", "scrypt$bad$x$y$z$w"):
        assert not security.verify_password("x", malformed, pepper)


def test_needs_rehash_detects_weaker_params(tmp_path):
    pepper = security.load_pepper(tmp_path / "pepper.key")
    weak = security.hash_password("correct-horse-battery", pepper, n=1024, r=8, p=1)

    assert security.needs_rehash(weak)
    assert not security.needs_rehash(security.hash_password("correct-horse-battery", pepper))
    assert security.needs_rehash("garbage")


def test_defaults_are_hardened(monkeypatch):
    for name in ("EL_SCRYPT_N", "EL_SCRYPT_R", "EL_SCRYPT_P", "EL_SCRYPT_DKLEN"):
        monkeypatch.delenv(name, raising=False)

    assert security._scrypt_params() == (2 ** 17, 8, 1, 64)


def test_pepper_file_is_created_0600(tmp_path):
    path = tmp_path / "nested" / "pepper.key"

    pepper = security.load_pepper(path)

    assert len(pepper) == security.PEPPER_BYTES
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert security.load_pepper(path) == pepper


def test_short_pepper_file_is_rejected(tmp_path):
    path = tmp_path / "pepper.key"
    path.write_bytes(b"short")

    with pytest.raises(SecurityError, match="too short"):
        security.load_pepper(path)


def test_validate_password_rules():
    security.validate_password("long-enough-passphrase", "user")

    with pytest.raises(SecurityError, match="at least"):
        security.validate_password("short", "user")
    with pytest.raises(SecurityError, match="username"):
        security.validate_password("supersecurepassphrase", "supersecurepassphrase")
    with pytest.raises(SecurityError, match="common"):
        security.validate_password("password1234", "user")


def test_dummy_verify_is_stable(tmp_path):
    pepper = security.load_pepper(tmp_path / "pepper.key")

    assert not security.dummy_verify("something", pepper)
    assert not security.dummy_verify("something", pepper)


def test_session_token_roundtrip_and_tamper(tmp_path):
    secret = security.load_session_key(tmp_path / "session.key")

    token = security.create_session_token("tester", secret)
    assert security.read_session_token(token, secret) == "tester"

    payload, signature = token.split(".")
    assert security.read_session_token(f"{payload}.AAAA", secret) is None
    assert security.read_session_token("garbage", secret) is None
    assert security.read_session_token(f"{payload}.{signature}.x", secret) is None

    other_secret = security.load_session_key(tmp_path / "other.key")
    assert security.read_session_token(token, other_secret) is None


def test_session_token_expiry(tmp_path):
    secret = security.load_session_key(tmp_path / "session.key")
    token = security.create_session_token("tester", secret, ttl=-1)

    assert security.read_session_token(token, secret) is None


def test_session_token_rejects_bad_expiry(tmp_path):
    secret = security.load_session_key(tmp_path / "session.key")
    import base64
    import hashlib
    import hmac

    payload = "tester:not-a-number"
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).digest()
    token = (
        base64.b64encode(payload.encode()).decode()
        + "."
        + base64.b64encode(signature).decode()
    )

    assert security.read_session_token(token, secret) is None


def test_login_throttle_locks_after_failures():
    throttle = security.LoginThrottle(limit=2, window=60)

    assert throttle.locked_seconds("1.2.3.4", "user") == 0
    throttle.record_failure("1.2.3.4", "user")
    assert throttle.locked_seconds("1.2.3.4", "user") == 0
    throttle.record_failure("1.2.3.4", "user")
    assert throttle.locked_seconds("1.2.3.4", "user") > 0

    throttle.record_success("1.2.3.4", "user")
    assert throttle.locked_seconds("1.2.3.4", "user") == 0


def test_login_throttle_prunes_old_failures():
    throttle = security.LoginThrottle(limit=2, window=0)
    throttle.record_failure("1.2.3.4", "user")
    throttle.record_failure("1.2.3.4", "user")

    time.sleep(0.01)
    assert throttle.locked_seconds("1.2.3.4", "user") == 0


def test_resolve_paths_prefer_explicit_argument(tmp_path):
    assert security.resolve_pepper_path(tmp_path / "x") == tmp_path / "x"
    assert security.resolve_session_key_path(tmp_path / "y") == tmp_path / "y"
    assert security.resolve_pepper_path() == security.PEPPER_PATH or os.environ.get(
        "EL_PEPPER_PATH"
    )


def test_verify_rejects_invalid_scrypt_params(tmp_path):
    pepper = security.load_pepper(tmp_path / "pepper.key")

    # n=3 is not a power of two: _derive raises, verification returns False.
    assert not security.verify_password("x", "scrypt$3$8$1$AAAA$AAAA", pepper)


def test_needs_rehash_with_invalid_params_returns_true():
    assert security.needs_rehash("scrypt$x$y$z$a$b")
    assert security.needs_rehash("bcrypt$1$2$3$a$b")
