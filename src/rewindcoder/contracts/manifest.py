"""Versioned manifest for reproducible local evaluation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from .validation import (
    ContractValidationError,
    ensure_no_sensitive_data,
    reject_unknown_fields,
    require_mapping,
    require_non_empty_string,
    require_string_list,
)


RUN_MANIFEST_SCHEMA_VERSION = "run-manifest/v1"
_MANIFEST_FIELDS = {
    "schema_version", "run_id", "task_id", "rewindcoder_commit", "fixture_base_commit",
    "python_version", "execution_mode", "test_commands", "test_results", "timestamp",
    "tool_policy_version", "status",
}


class ExecutionMode(StrEnum):
    STATIC = "STATIC"
    LOCAL = "LOCAL"
    REFERENCE = "REFERENCE"
    NOT_RUN = "NOT_RUN"


class RunStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_id: str
    task_id: str
    rewindcoder_commit: str
    fixture_base_commit: str
    python_version: str
    execution_mode: ExecutionMode
    test_commands: tuple[str, ...] = field(default_factory=tuple)
    test_results: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    tool_policy_version: str = "policy/v1"
    status: RunStatus = RunStatus.NOT_RUN
    schema_version: str = RUN_MANIFEST_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RunManifest":
        validate_run_manifest(raw)
        normalized = dict(raw)
        normalized["execution_mode"] = ExecutionMode(normalized["execution_mode"])
        normalized["status"] = RunStatus(normalized["status"])
        normalized["test_commands"] = tuple(normalized["test_commands"])
        return cls(**normalized)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_mode"] = self.execution_mode.value
        payload["status"] = self.status.value
        payload["test_commands"] = list(self.test_commands)
        return payload


def make_run_manifest(
    *,
    run_id: str,
    task_id: str,
    rewindcoder_commit: str,
    fixture_base_commit: str,
    python_version: str,
    execution_mode: ExecutionMode,
    test_commands: tuple[str, ...] = (),
    test_results: dict[str, Any] | None = None,
    tool_policy_version: str = "policy/v1",
    status: RunStatus = RunStatus.NOT_RUN,
) -> RunManifest:
    return RunManifest.from_dict(
        {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": task_id,
            "rewindcoder_commit": rewindcoder_commit,
            "fixture_base_commit": fixture_base_commit,
            "python_version": python_version,
            "execution_mode": execution_mode.value,
            "test_commands": list(test_commands),
            "test_results": test_results or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_policy_version": tool_policy_version,
            "status": status.value,
        }
    )


def validate_run_manifest(raw: Any) -> None:
    manifest = require_mapping(raw, "run_manifest")
    reject_unknown_fields(manifest, _MANIFEST_FIELDS, "run_manifest")
    missing = _MANIFEST_FIELDS - set(manifest)
    if missing:
        raise ContractValidationError(
            f"run_manifest is missing required fields: {', '.join(sorted(missing))}"
        )
    if manifest["schema_version"] != RUN_MANIFEST_SCHEMA_VERSION:
        raise ContractValidationError(
            "unsupported run_manifest schema_version: "
            f"{manifest['schema_version']!r}; expected {RUN_MANIFEST_SCHEMA_VERSION!r}"
        )
    for key in (
        "run_id", "task_id", "rewindcoder_commit", "fixture_base_commit", "python_version",
        "timestamp", "tool_policy_version",
    ):
        require_non_empty_string(manifest[key], f"run_manifest.{key}")
    if manifest["execution_mode"] not in {mode.value for mode in ExecutionMode}:
        raise ContractValidationError("run_manifest.execution_mode is invalid")
    if manifest["status"] not in {status.value for status in RunStatus}:
        raise ContractValidationError("run_manifest.status is invalid")
    require_string_list(manifest["test_commands"], "run_manifest.test_commands", allow_empty=True)
    require_mapping(manifest["test_results"], "run_manifest.test_results")
    try:
        parsed = datetime.fromisoformat(manifest["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError("run_manifest.timestamp must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ContractValidationError("run_manifest.timestamp must be UTC")
    ensure_no_sensitive_data(manifest, "run_manifest")
