"""Versioned serializable state paired with a repository checkpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

from .validation import ContractValidationError, require_non_empty_string


STATE_SCHEMA_VERSION = "state/v1"


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
    schema_version: str = STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty_string(self.task_id, "state.task_id")
        require_non_empty_string(self.issue, "state.issue")
        if self.schema_version != STATE_SCHEMA_VERSION:
            raise ContractValidationError(
                f"unsupported state schema_version: {self.schema_version!r}; expected {STATE_SCHEMA_VERSION!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RewindCoderState":
        if not isinstance(raw, dict):
            raise ContractValidationError("state must be an object")
        accepted = {item.name for item in fields(cls)}
        unknown = sorted(set(raw) - accepted)
        if unknown:
            raise ContractValidationError(f"state contains unknown fields: {', '.join(unknown)}")
        normalized = dict(raw)
        normalized.setdefault("schema_version", STATE_SCHEMA_VERSION)
        return cls(**normalized)
