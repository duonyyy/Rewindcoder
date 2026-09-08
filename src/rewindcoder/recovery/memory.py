"""Structured evidence from a failed trajectory, not free-form chat history."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RewindMemory:
    failure_type: str
    failed_hypothesis: str
    evidence: tuple[str, ...]
    failed_actions: tuple[str, ...]
    avoid_actions: tuple[str, ...]
    suggested_direction: str
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

