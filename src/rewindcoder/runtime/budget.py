"""Bound every workflow node, provider call, tool call, and elapsed time."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from rewindcoder.contracts.task import TaskBudget


class BudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True)
class BudgetMeter:
    limits: TaskBudget
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tokens: int = 0
    tool_calls: int = 0

    def remaining_seconds(self) -> float:
        remaining = self.limits.timeout_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise BudgetExceeded("timeout")
        return remaining

    def step(self) -> None:
        self.remaining_seconds()
        if self.steps >= self.limits.max_agent_steps:
            raise BudgetExceeded("max_agent_steps")
        self.steps += 1

    def tool(self) -> None:
        self.remaining_seconds()
        if self.tool_calls >= self.limits.max_tool_calls:
            raise BudgetExceeded("max_tool_calls")
        self.tool_calls += 1

    def charge_text(self, value: str) -> None:
        self.remaining_seconds()
        self.tokens += math.ceil(len(value.encode("utf-8")) / 4)
        if self.tokens > self.limits.max_tokens:
            raise BudgetExceeded("max_tokens")

    def usage(self) -> dict[str, int | float]:
        return {
            "steps": self.steps, "token_estimate": self.tokens,
            "tool_calls": self.tool_calls, "elapsed_seconds": round(time.monotonic() - self.started, 3),
        }
