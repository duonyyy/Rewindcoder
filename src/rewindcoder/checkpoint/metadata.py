"""Versioned, aligned checkpoint metadata. A safe flag alone is never evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from rewindcoder.contracts.state import RewindCoderState

CHECKPOINT_SCHEMA_VERSION = "checkpoint/v2"


@dataclass(frozen=True, slots=True)
class CheckpointMetadata:
    checkpoint_id: str
    node: str
    git_head: str | None
    workspace_manifest: dict[str, str | None]
    agent_state: dict[str, Any]
    test_status: dict[str, Any]
    verified_requirements: tuple[str, ...] = ()
    safe: bool = False
    risk_score: float = 1.0
    tracked_paths: tuple[str, ...] = ()
    untracked_paths: tuple[str, ...] = ()
    manifest_sha256: str = ""
    archive_sha256: str = ""
    evidence_sha256: str = ""
    agent_state_sha256: str = ""
    git_diff_sha256: str = ""
    workspace_root: str = ""
    created_at: str = ""
    schema_version: str = CHECKPOINT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("unsupported checkpoint schema_version")
        if not self.checkpoint_id or "/" in self.checkpoint_id or "\\" in self.checkpoint_id or ".." in self.checkpoint_id:
            raise ValueError("invalid checkpoint_id")
        RewindCoderState.from_dict(self.agent_state)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CheckpointMetadata":
        if not isinstance(raw, dict) or set(raw) - {item.name for item in fields(cls)}:
            raise ValueError("invalid checkpoint fields")
        normalized = dict(raw)
        normalized["verified_requirements"] = tuple(normalized.get("verified_requirements", ()))
        normalized["tracked_paths"] = tuple(normalized.get("tracked_paths", ()))
        normalized["untracked_paths"] = tuple(normalized.get("untracked_paths", ()))
        return cls(**normalized)
