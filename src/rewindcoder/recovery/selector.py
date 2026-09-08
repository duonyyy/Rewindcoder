"""Select only checkpoints that were explicitly marked safe."""

from __future__ import annotations

from dataclasses import dataclass

from rewindcoder.checkpoint.metadata import CheckpointMetadata


@dataclass(frozen=True, slots=True)
class CheckpointScore:
    checkpoint: CheckpointMetadata
    verified_progress: float
    test_health: float
    rollback_distance: int

    @property
    def value(self) -> float:
        return (
            0.4 * self.verified_progress
            + 0.3 * self.test_health
            + 0.2 * (1 - self.checkpoint.risk_score)
            - 0.1 * self.rollback_distance
        )


def select_checkpoint(candidates: list[CheckpointScore]) -> CheckpointMetadata:
    safe = [candidate for candidate in candidates if candidate.checkpoint.safe]
    if not safe:
        raise ValueError("No safe checkpoint is available for recovery")
    return max(safe, key=lambda candidate: candidate.value).checkpoint

