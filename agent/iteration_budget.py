"""Per-agent iteration budget — thread-safe consume/refund counter.

Each ``AIAgent`` (parent or subagent) holds its own :class:`IterationBudget`: the parent's
cap is ``max_iterations`` (default 500), each subagent's ``delegation.max_iterations``
(default 50), so total iterations across parent + subagents can exceed the parent's cap.
"""

from __future__ import annotations

import math
import threading


def normalize_budget_warning_ratio(value) -> float | None:
    """A finite ratio strictly between zero and one, or None (feature off)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return None
    return ratio if math.isfinite(ratio) and 0 < ratio < 1 else None


class IterationBudget:
    """Thread-safe iteration counter; ``execute_code`` (programmatic tool calling)
    iterations are refunded via :meth:`refund` so they don't eat into the budget.
    Saved specialist descendants can also charge a parent pool; local caps still apply.
    Locks are acquired from descendant to ancestor, never in the reverse order.
    """

    def __init__(self, max_total: int, *, parent: IterationBudget | None = None):
        self.max_total = max_total
        self.parent = parent
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Try to consume one iteration.  Returns True if allowed."""
        with self._lock:
            if self._used >= self.max_total:
                return False
            if self.parent is not None and not self.parent.consume():
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """Give back one iteration (e.g. for execute_code turns)."""
        with self._lock:
            if self._used > 0:
                self._used -= 1
                if self.parent is not None:
                    self.parent.refund()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            local = max(0, self.max_total - self._used)
            return min(local, self.parent.remaining) if self.parent is not None else local


__all__ = ["IterationBudget"]
