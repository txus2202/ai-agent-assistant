"""
Infrastructure helper for thread- and coroutine-isolated LLM token usage tracking.
"""
from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Any

_VAR_INIT_LOCK = threading.Lock()


def _safe_int(value: Any) -> int:
    """Convert numeric SDK counters cleanly without letting MagicMocks or bools slip in."""
    if isinstance(value, bool):
        return 0
    return value if isinstance(value, int) else 0


def build_usage(input_tokens: Any, output_tokens: Any, total_tokens: Any = None) -> dict[str, int]:
    """Build a normalized ``{input, output, total}`` usage dictionary."""
    in_t = _safe_int(input_tokens)
    out_t = _safe_int(output_tokens)
    tot_t = _safe_int(total_tokens) if total_tokens is not None else (in_t + out_t)
    if tot_t == 0 and (in_t or out_t):
        tot_t = in_t + out_t
    return {"input": in_t, "output": out_t, "total": tot_t}


class UsageTrackingMixin:
    """
    Replaces mutable shared instance state (``self._last_usage``) with a
    per-context ``ContextVar`` so concurrent threads/tasks sharing one adapter
    instance never overwrite each other's token metrics.
    """

    def _get_usage_var(self) -> ContextVar[dict[str, int] | None]:
        var: ContextVar[dict[str, int] | None] | None = getattr(self, "_scoped_usage_var", None)
        if var is None:
            with _VAR_INIT_LOCK:
                var = getattr(self, "_scoped_usage_var", None)
                if var is None:
                    var = ContextVar(f"{self.__class__.__name__}_usage_{id(self)}", default=None)
                    setattr(self, "_scoped_usage_var", var)
        return var

    def _set_scoped_usage(self, usage: dict[str, int]) -> dict[str, int]:
        copied = dict(usage)
        self._get_usage_var().set(copied)
        return dict(copied)

    def get_last_usage(self) -> dict[str, int]:
        """Return token usage recorded in the current execution context."""
        usage = self._get_usage_var().get()
        return dict(usage) if usage else {}
