"""Versioned metadata required to reproduce a recoverable checkpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CHECKPOINT_SCHEMA_VERSION = "checkpoint/v1"


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
    schema_version: str = CHECKPOINT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported checkpoint schema_version: {self.schema_version!r}; "
                f"expected {CHECKPOINT_SCHEMA_VERSION!r}"
            )
        if not self.checkpoint_id:
            raise ValueError("checkpoint_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CheckpointMetadata":
        normalized = dict(raw)
        normalized["verified_requirements"] = tuple(normalized.get("verified_requirements", ()))
        normalized.setdefault("schema_version", CHECKPOINT_SCHEMA_VERSION)
        return cls(**normalized)
