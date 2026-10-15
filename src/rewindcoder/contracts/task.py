"""Versioned evaluation-task contract and safe agent-facing projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .validation import (
    ContractValidationError,
    ensure_no_sensitive_data,
    reject_unknown_fields,
    require_mapping,
    require_non_empty_string,
    require_string_list,
)


TASK_SCHEMA_VERSION = "task/v1"
_TASK_FIELDS = {
    "schema_version", "task_id", "repository", "issue", "explicit_requirements",
    "target_commands", "regression_commands", "forbidden_paths", "budget", "evaluator_only",
}
_REPOSITORY_FIELDS = {"kind", "path", "base_commit"}
_BUDGET_FIELDS = {"max_agent_steps", "max_rewinds", "max_tokens", "max_tool_calls", "timeout_seconds"}
_EVALUATOR_ONLY_FIELDS = {"hidden_requirements", "gold_patch", "expected_outcome"}


@dataclass(frozen=True, slots=True)
class TaskRepository:
    kind: str
    path: str
    base_commit: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "path": self.path, "base_commit": self.base_commit}


@dataclass(frozen=True, slots=True)
class TaskBudget:
    max_agent_steps: int
    max_rewinds: int
    max_tokens: int
    max_tool_calls: int
    timeout_seconds: int

    def to_dict(self) -> dict[str, int]:
        return {
            "max_agent_steps": self.max_agent_steps,
            "max_rewinds": self.max_rewinds,
            "max_tokens": self.max_tokens,
            "max_tool_calls": self.max_tool_calls,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class TaskContract:
    task_id: str
    repository: TaskRepository
    issue: str
    explicit_requirements: tuple[str, ...]
    target_commands: tuple[str, ...]
    regression_commands: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    budget: TaskBudget
    evaluator_only: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    schema_version: str = TASK_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TaskContract":
        validate_task_payload(raw)
        return cls(
            task_id=raw["task_id"],
            repository=TaskRepository(**raw["repository"]),
            issue=raw["issue"],
            explicit_requirements=tuple(raw["explicit_requirements"]),
            target_commands=tuple(raw["target_commands"]),
            regression_commands=tuple(raw["regression_commands"]),
            forbidden_paths=tuple(raw["forbidden_paths"]),
            budget=TaskBudget(**raw["budget"]),
            evaluator_only=dict(raw.get("evaluator_only", {})),
            schema_version=raw["schema_version"],
        )

    def to_dict(self, *, include_evaluator_only: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "repository": self.repository.to_dict(),
            "issue": self.issue,
            "explicit_requirements": list(self.explicit_requirements),
            "target_commands": list(self.target_commands),
            "regression_commands": list(self.regression_commands),
            "forbidden_paths": list(self.forbidden_paths),
            "budget": self.budget.to_dict(),
        }
        if include_evaluator_only and self.evaluator_only:
            payload["evaluator_only"] = dict(self.evaluator_only)
        return payload

    def to_agent_payload(self) -> dict[str, Any]:
        """Return only information the agent is allowed to observe."""

        return self.to_dict(include_evaluator_only=False)


def validate_task_payload(raw: Any) -> None:
    task = require_mapping(raw, "task")
    reject_unknown_fields(task, _TASK_FIELDS, "task")
    required = _TASK_FIELDS - {"evaluator_only"}
    missing = sorted(required - set(task))
    if missing:
        raise ContractValidationError(f"task is missing required fields: {', '.join(missing)}")
    if task["schema_version"] != TASK_SCHEMA_VERSION:
        raise ContractValidationError(
            f"unsupported task schema_version: {task['schema_version']!r}; expected {TASK_SCHEMA_VERSION!r}"
        )
    require_non_empty_string(task["task_id"], "task.task_id")
    require_non_empty_string(task["issue"], "task.issue")
    require_string_list(task["explicit_requirements"], "task.explicit_requirements")
    require_string_list(task["target_commands"], "task.target_commands")
    require_string_list(task["regression_commands"], "task.regression_commands")
    require_string_list(task["forbidden_paths"], "task.forbidden_paths")

    repository = require_mapping(task["repository"], "task.repository")
    reject_unknown_fields(repository, _REPOSITORY_FIELDS, "task.repository")
    missing_repository = _REPOSITORY_FIELDS - set(repository)
    if missing_repository:
        raise ContractValidationError(
            f"task.repository is missing required fields: {', '.join(sorted(missing_repository))}"
        )
    if repository["kind"] not in {"fixture", "local"}:
        raise ContractValidationError("task.repository.kind must be 'fixture' or 'local'")
    for key in ("kind", "path", "base_commit"):
        require_non_empty_string(repository[key], f"task.repository.{key}")

    budget = require_mapping(task["budget"], "task.budget")
    reject_unknown_fields(budget, _BUDGET_FIELDS, "task.budget")
    missing_budget = _BUDGET_FIELDS - set(budget)
    if missing_budget:
        raise ContractValidationError(
            f"task.budget is missing required fields: {', '.join(sorted(missing_budget))}"
        )
    for key in _BUDGET_FIELDS:
        value = budget[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ContractValidationError(f"task.budget.{key} must be a non-negative integer")
    if budget["timeout_seconds"] == 0:
        raise ContractValidationError("task.budget.timeout_seconds must be greater than zero")

    evaluator = require_mapping(task.get("evaluator_only", {}), "task.evaluator_only")
    reject_unknown_fields(evaluator, _EVALUATOR_ONLY_FIELDS, "task.evaluator_only")
    if "hidden_requirements" in evaluator:
        require_string_list(evaluator["hidden_requirements"], "task.evaluator_only.hidden_requirements")
    if "gold_patch" in evaluator:
        require_non_empty_string(evaluator["gold_patch"], "task.evaluator_only.gold_patch")
    if "expected_outcome" in evaluator:
        require_mapping(evaluator["expected_outcome"], "task.evaluator_only.expected_outcome")
    ensure_no_sensitive_data(task, "task")
