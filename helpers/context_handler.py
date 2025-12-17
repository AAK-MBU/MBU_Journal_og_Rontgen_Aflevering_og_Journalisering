"""Helper functions and classes to manage run context using context variables."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_ctx: ContextVar[dict[str, Any] | None] = ContextVar("context_handler", default=None)


def get_context() -> dict[str, Any]:
    """Get the current run context."""
    return _ctx.get() or {}


def get_context_values(key: str, default: Any = None) -> Any:
    """Get a value from the current run context."""
    ctx = get_context()
    return ctx.get(key, default)


def require(key: str) -> Any:
    """Get a required value from the current run context."""
    ctx = _ctx.get()
    if ctx is None or key not in ctx:
        raise KeyError(f"Required context key '{key}' is missing.")
    return ctx[key]


def set_context_values(**values: Any) -> dict[str, Any]:
    """Set values in the current run context."""
    base = _ctx.get() or {}
    new_ctx = {**base, **values}
    _ctx.set(new_ctx)
    return new_ctx


def clear_context() -> None:
    """Manually clear the current run context."""
    _ctx.set({})


class Scope:
    """Context manager to temporarily set the run context."""

    def __init__(self, fresh: bool = False, **overrides: Any) -> None:
        self.fresh = fresh
        self.overrides = overrides
        self.token = None

    def __enter__(self) -> Mapping[str, Any]:
        base = {} if self.fresh else _ctx.get() or {}
        new_ctx = {**base, **self.overrides}
        self.token = _ctx.set(new_ctx)
        return new_ctx

    def __exit__(self, exc_type, exc_value, traceback):
        if self.token is not None:
            _ctx.reset(self.token)
