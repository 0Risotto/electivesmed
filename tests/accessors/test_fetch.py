import time
from urllib.robotparser import RobotFileParser

import pytest

from electivesmed.accessors.fetch import DEFAULT_USER_AGENT, HttpAccessor
from electivesmed.errors import FetchError

from tests.fakes import FailingHttpClient, FakeHttpClient


def test_default_user_agent_is_used(tmp_path):
    accessor = HttpAccessor(cache_dir=tmp_path)

    assert accessor.user_agent == DEFAULT_USER_AGENT
    accessor.close()


def test_fetch_bytes_caches_response(http_accessor):
    client = FakeHttpClient(body=b"hello")
    accessor = http_accessor(client)

    assert accessor.fetch_bytes("http://test.local/page") == b"hello"
    calls_after_first = len(client.calls)
    assert accessor.fetch_bytes("http://test.local/page") == b"hello"
    assert len(client.calls) == calls_after_first


def test_fetch_bytes_bypasses_cache_when_asked(http_accessor):
    client = FakeHttpClient(body=b"hello")
    accessor = http_accessor(client)

    accessor.fetch_bytes("http://test.local/page")
    accessor.fetch_bytes("http://test.local/page", use_cache=False)

    assert len([call for call in client.calls if call.endswith("/page")]) == 2


def test_robots_disallow_raises(http_accessor):
    client = FakeHttpClient(robots="User-agent: *\nDisallow: /private")
    accessor = http_accessor(client)

    with pytest.raises(FetchError, match="robots.txt"):
        accessor.fetch_bytes("http://test.local/private/page")


def test_missing_robots_allows_fetch(http_accessor):
    client = FakeHttpClient(robots=None, body=b"ok")
    accessor = http_accessor(client)

    assert accessor.fetch_bytes("http://test.local/page") == b"ok"


def test_robot_parser_cache_is_reused(http_accessor):
    client = FakeHttpClient()
    accessor = http_accessor(client)

    accessor.fetch_bytes("http://test.local/one")
    accessor.fetch_bytes("http://test.local/two", use_cache=False)

    assert len([call for call in client.calls if call.endswith("robots.txt")]) == 1


def test_throttle_sleeps_for_same_host(http_accessor, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    accessor = http_accessor(FakeHttpClient(), delay_seconds=1.0)
    accessor._last_request["test.local"] = time.monotonic()

    accessor._throttle("http://test.local/page")
    accessor.close()

    assert sleeps and sleeps[0] > 0


def test_http_error_raises_fetch_error(http_accessor):
    accessor = http_accessor(FailingHttpClient())

    with pytest.raises(FetchError, match="failed to fetch"):
        accessor.fetch_bytes("http://test.local/page")


def test_fetch_text_falls_back_to_latin1(http_accessor):
    accessor = http_accessor(FakeHttpClient())
    url = "http://test.local/binary"
    accessor._cache_path(url).write_bytes(b"\xff\xfe caf\xe9")

    assert "caf" in accessor.fetch_text(url)


def test_close_closes_client(http_accessor):
    client = FakeHttpClient()
    accessor = http_accessor(client)

    accessor.close()

    assert client.closed


def test_disallowed_url_with_preloaded_parser(http_accessor):
    parser = RobotFileParser()
    parser.set_url("http://test.local/robots.txt")
    parser.parse(["User-agent: *", "Disallow: /"])
    accessor = http_accessor(FakeHttpClient())
    accessor._robots["http://test.local"] = parser

    with pytest.raises(FetchError):
        accessor.fetch_bytes("http://test.local/anything")


def test_request_json_returns_and_caches_payload(http_accessor):
    client = FakeHttpClient(json_data={"ok": True})
    accessor = http_accessor(client)

    assert accessor.request_json("http://api.test/x", params={"q": "1"}) == {"ok": True}
    calls_after_first = len(client.calls)
    assert accessor.request_json("http://api.test/x", params={"q": "1"}) == {"ok": True}
    assert len(client.calls) == calls_after_first


def test_request_json_bypasses_cache(http_accessor):
    client = FakeHttpClient(json_data={"ok": True})
    accessor = http_accessor(client)

    accessor.request_json("http://api.test/x", use_cache=False)
    accessor.request_json("http://api.test/x", use_cache=False)

    request_calls = [call for call in client.calls if call.startswith("GET http")]
    assert len(request_calls) == 2


def test_request_json_http_error_raises(http_accessor):
    accessor = http_accessor(FailingHttpClient())

    with pytest.raises(FetchError, match="failed to fetch"):
        accessor.request_json("http://api.test/x")
