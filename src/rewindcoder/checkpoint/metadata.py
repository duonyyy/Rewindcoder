"""Metadata required to reproduce a recoverable checkpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckpointMetadata:
    checkpoint_id: str
    node: str
    git_head: str | None
    workspace_manifest: dict[str, str]
    agent_state: dict[str, Any]
    test_status: dict[str, Any]
    verified_requirements: tuple[str, ...] = ()
    safe: bool = False
    risk_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CheckpointMetadata":
        raw = dict(raw)
        raw["verified_requirements"] = tuple(raw.get("verified_requirements", ()))
        return cls(**raw)

