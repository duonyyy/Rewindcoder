"""Serializable state that is paired with a repository checkpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RewindCoderState:
    task_id: str
    issue: str
    requirements: list[str] = field(default_factory=list)
    current_goal: str = ""
    plan: list[str] = field(default_factory=list)
    current_step: int = 0
    context_summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    rewind_count: int = 0
    current_checkpoint: str | None = None
    rewind_memories: list[dict[str, Any]] = field(default_factory=list)
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    budget_remaining: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RewindCoderState":
        return cls(**raw)

