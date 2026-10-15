"""Structured evidence from a failed trajectory, not free-form chat history."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RewindMemory:
    failure_type: str
    failed_hypothesis: str
    evidence: tuple[str, ...]
    failed_actions: tuple[str, ...]
    avoid_actions: tuple[str, ...]
    suggested_direction: str
    confidence: float
    source_trace_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((self.failure_type, self.failed_hypothesis, self.evidence,
                    self.failed_actions, self.avoid_actions, self.suggested_direction,
                    self.source_trace_ids)):
            raise ValueError("rewind memory requires concrete evidence and trace IDs")
        if not 0 <= self.confidence <= 1:
            raise ValueError("memory confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_alternative(action: str, memory: RewindMemory, *, new_evidence: tuple[str, ...] = ()) -> None:
    if not action.strip():
        raise ValueError("alternative action is empty")
    if action in memory.avoid_actions and not new_evidence:
        raise ValueError("alternative plan repeats avoid_action without new evidence")
    if action in memory.failed_actions and not new_evidence:
        raise ValueError("alternative plan repeats failed action without new evidence")

