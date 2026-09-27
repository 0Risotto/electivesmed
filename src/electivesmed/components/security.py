"""Credential security: hardened scrypt hashing with pepper, sessions, login throttle.

Storage format: scrypt$n$r$p$salt_b64$hash_b64
Defaults: N=2^17, r=8, p=1, dklen=64 (~128 MiB per attempt, OWASP scrypt guidance).
Passwords are HMAC-SHA256-peppered before scrypt, so a stolen database copy alone
cannot be cracked without data/pepper.key.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

from ..errors import SecurityError
from ..paths import PEPPER_PATH, SESSION_KEY_PATH

SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SALT_BYTES = 32
PEPPER_BYTES = 32
SESSION_KEY_BYTES = 32

MIN_PASSWORD_LENGTH = 12
SESSION_TTL_SECONDS = 12 * 60 * 60
LOCKOUT_AFTER = 10
LOCKOUT_SECONDS = 2 * 60

COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "123456789012",
        "qwertyuiop12",
        "letmein12345",
        "adminadmin12",
        "welcome12345",
        "iloveyou1234",
        "changeme1234",
        "passwordpassword",
    }
)


class LoginThrottle:
    """In-memory lockout: 5 failures per (ip, username) -> 15 minutes."""

    def __init__(self, limit: int = LOCKOUT_AFTER, window: int = LOCKOUT_SECONDS) -> None:
        self._limit = limit
        self._window = window
        self._failures: dict[tuple[str, str], list[float]] = {}

    def _key(self, ip: str, username: str) -> tuple[str, str]:
        return (ip or "-", (username or "").strip().lower())

    def locked_seconds(self, ip: str, username: str) -> int:
        entries = self._failures.get(self._key(ip, username))
        if not entries:
            return 0
        now = time.monotonic()
        entries[:] = [stamp for stamp in entries if now - stamp < self._window]
        if len(entries) >= self._limit:
            return max(1, int(self._window - (now - entries[-1])))
        return 0

    def record_failure(self, ip: str, username: str) -> None:
        self._failures.setdefault(self._key(ip, username), []).append(time.monotonic())

    def record_success(self, ip: str, username: str) -> None:
        self._failures.pop(self._key(ip, username), None)


def _scrypt_params() -> tuple[int, int, int, int]:
    # EL_SCRYPT_* overrides exist for the test suite only; the defaults are hardened.
    return (
        int(os.environ.get("EL_SCRYPT_N", SCRYPT_N)),
        int(os.environ.get("EL_SCRYPT_R", SCRYPT_R)),
        int(os.environ.get("EL_SCRYPT_P", SCRYPT_P)),
        int(os.environ.get("EL_SCRYPT_DKLEN", SCRYPT_DKLEN)),
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _derive(
    password: str,
    salt: bytes,
    pepper: bytes,
    n: int,
    r: int,
    p: int,
    dklen: int,
) -> bytes:
    peppered = hmac.new(pepper, password.encode("utf-8"), hashlib.sha256).digest()
    return hashlib.scrypt(
        peppered,
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=max(32 * 1024 * 1024, 256 * n * r),
    )


def resolve_pepper_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    return Path(os.environ.get("EL_PEPPER_PATH", str(PEPPER_PATH)))


def resolve_session_key_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    return Path(os.environ.get("EL_SESSION_KEY_PATH", str(SESSION_KEY_PATH)))


def _load_or_create_key(path: Path, length: int) -> bytes:
    if path.exists():
        data = path.read_bytes()
        if len(data) < 16:
            raise SecurityError(f"key file {path} is too short")
        return data
    path.parent.mkdir(parents=True, exist_ok=True)
    data = secrets.token_bytes(length)
    path.write_bytes(data)
    path.chmod(0o600)
    return data


def load_pepper(path: Path | None = None) -> bytes:
    return _load_or_create_key(resolve_pepper_path(path), PEPPER_BYTES)


def pepper_exists(path: Path | None = None) -> bool:
    return resolve_pepper_path(path).exists()


def load_session_key(path: Path | None = None) -> bytes:
    return _load_or_create_key(resolve_session_key_path(path), SESSION_KEY_BYTES)


def validate_password(password: str, username: str = "") -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SecurityError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if username and password.strip().lower() == username.strip().lower():
        raise SecurityError("password must not be the username")
    if password.strip().lower() in COMMON_PASSWORDS:
        raise SecurityError("password is too common")


def hash_password(
    password: str,
    pepper: bytes | None = None,
    *,
    n: int | None = None,
    r: int | None = None,
    p: int | None = None,
    dklen: int | None = None,
) -> str:
    current_n, current_r, current_p, current_dklen = _scrypt_params()
    n = current_n if n is None else n
    r = current_r if r is None else r
    p = current_p if p is None else p
    dklen = current_dklen if dklen is None else dklen
    pepper = pepper if pepper is not None else load_pepper()
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _derive(password, salt, pepper, n, r, p, dklen)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str, pepper: bytes | None = None) -> bool:
    try:
        algorithm, n_raw, r_raw, p_raw, salt_b64, hash_b64 = stored.split("$")
        if algorithm != "scrypt":
            return False
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
    except (ValueError, TypeError):
        return False
    pepper = pepper if pepper is not None else load_pepper()
    try:
        derived = _derive(password, salt, pepper, n, r, p, len(expected))
    except ValueError:
        return False
    return hmac.compare_digest(derived, expected)


def needs_rehash(stored: str) -> bool:
    try:
        algorithm, n_raw, r_raw, p_raw, _, _ = stored.split("$")
        if algorithm != "scrypt":
            return True
        n, r, p, dklen = _scrypt_params()
        return (int(n_raw), int(r_raw), int(p_raw)) != (n, r, p)
    except (ValueError, TypeError):
        return True


_DUMMY_CACHE: dict[bytes, str] = {}


def dummy_verify(password: str, pepper: bytes | None = None) -> bool:
    """Equalize timing for unknown usernames."""
    pepper = pepper if pepper is not None else load_pepper()
    stored = _DUMMY_CACHE.get(pepper)
    if stored is None:
        stored = hash_password("dummy-password-for-timing", pepper)
        _DUMMY_CACHE[pepper] = stored
    return verify_password(password, stored, pepper)


def create_session_token(
    username: str, secret: bytes, ttl: int = SESSION_TTL_SECONDS
) -> str:
    expiry = int(time.time()) + ttl
    payload = f"{username}:{expiry}"
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{_b64(payload.encode('utf-8'))}.{_b64(signature)}"


def read_session_token(token: str, secret: bytes) -> str | None:
    try:
        payload_b64, signature_b64 = token.split(".")
        payload = _unb64(payload_b64).decode("utf-8")
        signature = _unb64(signature_b64)
    except (ValueError, TypeError):
        return None
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        return None
    username, _, expiry = payload.rpartition(":")
    if not username or not expiry.isdigit() or int(expiry) < time.time():
        return None
    return username
