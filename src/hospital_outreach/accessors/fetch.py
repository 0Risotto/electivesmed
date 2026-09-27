"""Robots-aware, throttled, cached HTTP fetcher."""

import hashlib
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..constants.limits import FETCH_DELAY_SECONDS, HTTP_TIMEOUT_SECONDS
from ..errors import FetchError

DEFAULT_USER_AGENT = "hospital-outreach/0.1 (local research tool; contact: set-sender-email)"


class FetchAccessor(Protocol):
    def fetch_text(self, url: str, use_cache: bool = True) -> str: ...
    def fetch_bytes(self, url: str, use_cache: bool = True) -> bytes: ...
    def close(self) -> None: ...


class HttpAccessor:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_dir: str | Path = "data/cache",
        delay_seconds: float = FETCH_DELAY_SECONDS,
        timeout: float = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_seconds = delay_seconds
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    # ----------------------------------------------------------------- robots
    def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser: RobotFileParser | None = None
        try:
            resp = self._client.get(f"{origin}/robots.txt", timeout=10)
            if resp.status_code == 200:
                parser = RobotFileParser()
                parser.parse(resp.text.splitlines())
        except Exception:
            parser = None
        self._robots[origin] = parser
        return parser

    def _check_robots(self, url: str) -> None:
        parser = self._robots_for(url)
        if parser is not None and not parser.can_fetch(self.user_agent, url):
            raise FetchError(f"robots.txt disallows fetching {url}")

    # --------------------------------------------------------------- throttle
    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host, 0.0)
        wait = self.delay_seconds - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    # ------------------------------------------------------------------ cache
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.bin"

    # ------------------------------------------------------------------- fetch
    def _get(self, url: str, use_cache: bool) -> bytes:
        cache_path = self._cache_path(url)
        if use_cache and cache_path.exists():
            return cache_path.read_bytes()
        self._check_robots(url)
        self._throttle(url)
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"failed to fetch {url}: {exc}") from exc
        cache_path.write_bytes(resp.content)
        return resp.content

    def fetch_bytes(self, url: str, use_cache: bool = True) -> bytes:
        return self._get(url, use_cache)

    def fetch_text(self, url: str, use_cache: bool = True) -> str:
        raw = self._get(url, use_cache)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def close(self) -> None:
        self._client.close()
