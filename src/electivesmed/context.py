"""Ambient invocation context shared by tools and actions."""

from contextvars import ContextVar, Token

from .models.invocation import InvocationContext

_current: ContextVar[InvocationContext | None] = ContextVar("current_invocation", default=None)


def set_invocation(ctx: InvocationContext) -> Token:
    return _current.set(ctx)


def reset_invocation(token: Token) -> None:
    _current.reset(token)


def current_invocation() -> InvocationContext | None:
    return _current.get()


def require_invocation() -> InvocationContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError(
            "No invocation context is active. Agent actions must run through agent.invoker."
        )
    return ctx
