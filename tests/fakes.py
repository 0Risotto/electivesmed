"""Test doubles for accessors and services."""

import httpx

from electivesmed.models.entities import SendReceipt
from electivesmed.models.enums import SendStatus


class FakeMail:
    def __init__(
        self,
        status: SendStatus = SendStatus.SENT,
        accepted: bool = True,
        error: str | None = None,
    ) -> None:
        self.calls: list[tuple] = []
        self.closed = False
        self._status = status
        self._accepted = accepted
        self._error = error

    def send(self, payload, dry_run: bool = True) -> SendReceipt:
        self.calls.append((payload, dry_run))
        return SendReceipt(
            message_id="<test@local>",
            accepted=self._accepted,
            status=SendStatus.DRY_RUN if dry_run else self._status,
            error=self._error,
            dry_run=dry_run,
        )

    def close(self) -> None:
        self.closed = True


class FakeLlm:
    def __init__(
        self,
        available: bool = True,
        json_response: dict | None = None,
        text_response: str = "ok",
    ) -> None:
        self._available = available
        self._json = json_response if json_response is not None else {}
        self._text = text_response
        self.calls: list[tuple] = []

    @property
    def available(self) -> bool:
        return self._available

    def chat_json(self, system, user, model=None, temperature=None, max_tokens=None) -> dict:
        self.calls.append(("json", system, user))
        if isinstance(self._json, Exception):
            raise self._json
        return self._json

    def chat_text(self, system, user, model=None, temperature=None, max_tokens=None) -> str:
        self.calls.append(("text", system, user))
        return self._text


class FakeFetch:
    def __init__(self, data: bytes = b"", json_response: dict | None = None) -> None:
        self.data = data
        self.json_response = json_response if json_response is not None else {}
        self.requests: list[str] = []
        self.json_calls: list[dict] = []
        self.closed = False

    def fetch_bytes(self, url: str, use_cache: bool = True) -> bytes:
        self.requests.append(url)
        return self.data

    def fetch_text(self, url: str, use_cache: bool = True) -> str:
        self.requests.append(url)
        return self.data.decode()

    def request_json(
        self,
        url: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        use_cache: bool = True,
    ) -> dict:
        self.json_calls.append({"url": url, "method": method, "params": params, "data": data})
        if isinstance(self.json_response, Exception):
            raise self.json_response
        return self.json_response

    def close(self) -> None:
        self.closed = True


class FakeReply:
    def __init__(self, replies: list[dict] | None = None) -> None:
        self.replies = replies or []
        self.closed = False

    def fetch_replies(self, limit: int = 50) -> list[dict]:
        return self.replies

    def close(self) -> None:
        self.closed = True


class FakeHttpResponse:
    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"",
        text: str = "",
        json_data: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.text = text
        self._json = json_data if json_data is not None else {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://test.local")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("bad status", request=request, response=response)

    def json(self) -> dict:
        return self._json


class FakeHttpClient:
    """Stands in for httpx.Client; serves robots.txt, page bodies, and JSON APIs."""

    def __init__(
        self,
        robots: str | None = "User-agent: *\nAllow: /",
        body: bytes = b"page",
        json_data: dict | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.robots = robots
        self.body = body
        self.json_data = json_data if json_data is not None else {}
        self.closed = False

    def get(self, url: str, timeout: float | None = None) -> FakeHttpResponse:
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            if self.robots is None:
                return FakeHttpResponse(status_code=404, text="")
            return FakeHttpResponse(text=self.robots)
        return FakeHttpResponse(content=self.body)

    def request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> FakeHttpResponse:
        self.calls.append(f"{method} {url}")
        return FakeHttpResponse(json_data=self.json_data)

    def close(self) -> None:
        self.closed = True


class FailingHttpClient(FakeHttpClient):
    def get(self, url: str, timeout: float | None = None) -> FakeHttpResponse:
        self.calls.append(url)
        raise httpx.ConnectError("no route")

    def request(self, method: str, url: str, **kwargs) -> FakeHttpResponse:
        self.calls.append(f"{method} {url}")
        raise httpx.ConnectError("no route")


class KeepOpen:
    """Wraps a container so CLI commands do not close the shared test container."""

    def __init__(self, container) -> None:
        self._container = container

    def __enter__(self):
        return self._container

    def __exit__(self, *exc_info) -> bool:
        return False
