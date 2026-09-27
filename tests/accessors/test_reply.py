import imaplib

from electivesmed.accessors.reply import ImapAccessor

RAW_MESSAGE = b"From: sender@example.org\r\nSubject: Re: Hello\r\nDate: today\r\n\r\nBody"


class _FakeImapClient:
    def __init__(self, host, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def login(self, user, password):
        pass

    def select(self, mailbox):
        return ("OK", [b"1"])

    def search(self, charset, query):
        return ("OK", [b"1 2"])

    def fetch(self, uid, spec):
        return ("OK", [(b"1 (RFC822 {120})", RAW_MESSAGE)])

    def store(self, uid, flag, value):
        return ("OK", [b""])


class _MalformedImapClient(_FakeImapClient):
    def fetch(self, uid, spec):
        return ("OK", [b"not-a-tuple"])


def test_unconfigured_returns_empty():
    accessor = ImapAccessor(host="", user="", password="")

    assert not accessor.configured
    assert accessor.fetch_replies() == []


def test_fetch_replies_parses_messages(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _FakeImapClient)
    accessor = ImapAccessor(host="imap.test", user="user", password="secret")

    replies = accessor.fetch_replies()
    assert len(replies) == 2
    assert replies[0]["from"] == "sender@example.org"
    assert replies[0]["subject"] == "Re: Hello"
    assert replies[0]["uid"] == "1"


def test_fetch_replies_skips_malformed_entries(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _MalformedImapClient)
    accessor = ImapAccessor(host="imap.test", user="user", password="secret")

    assert accessor.fetch_replies() == []


def test_fetch_replies_swallows_errors(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", explode)
    accessor = ImapAccessor(host="imap.test", user="user", password="secret")

    assert accessor.fetch_replies() == []
    assert accessor.close() is None
