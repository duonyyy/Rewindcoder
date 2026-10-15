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
    "provider", "provider_config", "seed", "budget", "usage", "verifier_result", "stop_reason",
    "patch_sha256", "workspace_head", "trace_sha256", "runner_source_sha256", "task_sha256",
    "recovery", "evaluation",
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
    provider: str = ""
    provider_config: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    budget: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    verifier_result: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = ""
    patch_sha256: str = ""
    workspace_head: str = ""
    trace_sha256: str = ""
    runner_source_sha256: str = ""
    task_sha256: str = ""
    recovery: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
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
    provider: str = "",
    provider_config: dict[str, Any] | None = None,
    seed: int = 0,
    budget: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    verifier_result: dict[str, Any] | None = None,
    stop_reason: str = "",
    patch_sha256: str = "",
    workspace_head: str = "",
    trace_sha256: str = "",
    runner_source_sha256: str = "",
    task_sha256: str = "",
    recovery: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
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
            "provider": provider,
            "provider_config": provider_config or {},
            "seed": seed,
            "budget": budget or {},
            "usage": usage or {},
            "verifier_result": verifier_result or {},
            "stop_reason": stop_reason,
            "patch_sha256": patch_sha256,
            "workspace_head": workspace_head,
            "trace_sha256": trace_sha256,
            "runner_source_sha256": runner_source_sha256,
            "task_sha256": task_sha256,
            "recovery": recovery or {},
            "evaluation": evaluation or {},
        }
    )


def validate_run_manifest(raw: Any) -> None:
    manifest = require_mapping(raw, "run_manifest")
    reject_unknown_fields(manifest, _MANIFEST_FIELDS, "run_manifest")
    missing = (_MANIFEST_FIELDS - {"recovery", "evaluation"}) - set(manifest)
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
    for key in ("provider", "stop_reason", "patch_sha256", "workspace_head", "trace_sha256", "runner_source_sha256", "task_sha256"):
        if key in manifest and not isinstance(manifest[key], str):
            raise ContractValidationError(f"run_manifest.{key} must be a string")
    if "seed" in manifest and (not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool)):
        raise ContractValidationError("run_manifest.seed must be an integer")
    for key in ("provider_config", "budget", "usage", "verifier_result", "recovery", "evaluation"):
        if key in manifest:
            require_mapping(manifest[key], f"run_manifest.{key}")
    try:
        parsed = datetime.fromisoformat(manifest["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError("run_manifest.timestamp must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ContractValidationError("run_manifest.timestamp must be UTC")
    ensure_no_sensitive_data(manifest, "run_manifest")
