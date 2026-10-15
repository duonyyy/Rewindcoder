"""Versioned, framework-neutral data contracts for RewindCoder."""

from .manifest import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ExecutionMode,
    RunManifest,
    RunStatus,
    make_run_manifest,
)
from .state import STATE_SCHEMA_VERSION, RewindCoderState
from .task import TASK_SCHEMA_VERSION, TaskBudget, TaskContract, TaskRepository
from .trace import TRACE_SCHEMA_VERSION, TraceEvent, make_trace_event
from .validation import ContractValidationError

__all__ = [
    "ContractValidationError",
    "ExecutionMode",
    "RUN_MANIFEST_SCHEMA_VERSION",
    "RunManifest",
    "RunStatus",
    "STATE_SCHEMA_VERSION",
    "TASK_SCHEMA_VERSION",
    "TRACE_SCHEMA_VERSION",
    "RewindCoderState",
    "TaskBudget",
    "TaskContract",
    "TaskRepository",
    "TraceEvent",
    "make_run_manifest",
    "make_trace_event",
]
