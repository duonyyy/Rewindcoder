"""Versioned trace events that are safe to persist as JSONL."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .validation import (
    ContractValidationError,
    ensure_no_sensitive_data,
    reject_unknown_fields,
    require_mapping,
    require_non_empty_string,
)


TRACE_SCHEMA_VERSION = "trace/v1"
_TRACE_FIELDS = {"schema_version", "timestamp", "run_id", "task_id", "node", "event", "details"}


@dataclass(frozen=True, slots=True)
class TraceEvent:
    timestamp: str
    run_id: str
    task_id: str
    node: str
    event: str
    details: dict[str, Any]
    schema_version: str = TRACE_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TraceEvent":
        validate_trace_event(raw)
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_trace_event(
    *, run_id: str, task_id: str, node: str, event: str, details: dict[str, Any]
) -> TraceEvent:
    return TraceEvent.from_dict(
        {
            "schema_version": TRACE_SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "task_id": task_id,
            "node": node,
            "event": event,
            "details": details,
        }
    )


def validate_trace_event(raw: Any) -> None:
    event = require_mapping(raw, "trace")
    reject_unknown_fields(event, _TRACE_FIELDS, "trace")
    missing = _TRACE_FIELDS - set(event)
    if missing:
        raise ContractValidationError(f"trace is missing required fields: {', '.join(sorted(missing))}")
    if event["schema_version"] != TRACE_SCHEMA_VERSION:
        raise ContractValidationError(
            f"unsupported trace schema_version: {event['schema_version']!r}; expected {TRACE_SCHEMA_VERSION!r}"
        )
    for key in ("timestamp", "run_id", "task_id", "node", "event"):
        require_non_empty_string(event[key], f"trace.{key}")
    try:
        parsed = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError("trace.timestamp must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ContractValidationError("trace.timestamp must be UTC")
    details = require_mapping(event["details"], "trace.details")
    ensure_no_sensitive_data(details, "trace.details")
