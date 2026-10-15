import json
import unittest
from copy import deepcopy
from pathlib import Path

from rewindcoder.contracts.manifest import (
    ExecutionMode,
    RunManifest,
    RunStatus,
    make_run_manifest,
)
from rewindcoder.contracts.state import STATE_SCHEMA_VERSION, RewindCoderState
from rewindcoder.contracts.task import TaskContract
from rewindcoder.contracts.trace import TraceEvent
from rewindcoder.contracts.validation import ContractValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_TASK_PATH = PROJECT_ROOT / "evals" / "tasks" / "sample_recovery_task.json"


def load_sample_task() -> dict:
    return json.loads(SAMPLE_TASK_PATH.read_text(encoding="utf-8"))


class ContractTests(unittest.TestCase):
    def test_schema_files_are_valid_json(self) -> None:
        for schema_name in ("task.schema.json", "run_manifest.schema.json"):
            schema_path = PROJECT_ROOT / "evals" / "schemas" / schema_name
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertIn("$schema", schema)
            self.assertEqual(schema["type"], "object")

    def test_task_contract_validates_sample_and_rejects_missing_base_commit(self) -> None:
        task = TaskContract.from_dict(load_sample_task())
        self.assertEqual(task.schema_version, "task/v1")
        self.assertEqual(task.repository.base_commit, "704e442013b980e52ecb23e9e75ac9ee1dcfe48c")

        invalid = load_sample_task()
        del invalid["repository"]["base_commit"]
        with self.assertRaisesRegex(ContractValidationError, "base_commit"):
            TaskContract.from_dict(invalid)

    def test_task_contract_hides_evaluator_only_fields_from_agent(self) -> None:
        task = TaskContract.from_dict(load_sample_task())
        self.assertIn("evaluator_only", task.to_dict(include_evaluator_only=True))
        agent_payload = task.to_agent_payload()
        self.assertNotIn("evaluator_only", agent_payload)
        self.assertNotIn("gold_patch", json.dumps(agent_payload))
        self.assertNotIn("hidden_requirements", json.dumps(agent_payload))

    def test_state_round_trip_preserves_version_and_data(self) -> None:
        original = RewindCoderState(
            task_id="task-contract-001",
            issue="Preserve state through a checkpoint.",
            requirements=["R1"],
            plan=["Read test", "Run test"],
            current_checkpoint="cp-001",
        )
        restored = RewindCoderState.from_dict(json.loads(json.dumps(original.to_dict())))
        self.assertEqual(restored.to_dict(), original.to_dict())
        self.assertEqual(restored.schema_version, STATE_SCHEMA_VERSION)

    def test_trace_contract_requires_task_id_and_rejects_sensitive_details(self) -> None:
        raw = {
            "schema_version": "trace/v1",
            "timestamp": "2026-10-01T00:00:00+00:00",
            "run_id": "run-001",
            "task_id": "task-001",
            "node": "verify",
            "event": "started",
            "details": {"attempt": 1},
        }
        self.assertEqual(TraceEvent.from_dict(raw).task_id, "task-001")

        missing_task = deepcopy(raw)
        del missing_task["task_id"]
        with self.assertRaisesRegex(ContractValidationError, "task_id"):
            TraceEvent.from_dict(missing_task)

        sensitive = deepcopy(raw)
        sensitive["details"] = {"api_key": "sk-example"}
        with self.assertRaisesRegex(ContractValidationError, "sensitive"):
            TraceEvent.from_dict(sensitive)

    def test_manifest_supports_not_run_without_claiming_success(self) -> None:
        manifest = make_run_manifest(
            run_id="run-not-run-001",
            task_id="task-001",
            rewindcoder_commit="27bdab5",
            fixture_base_commit="fixture-base-001",
            python_version="3.11",
            execution_mode=ExecutionMode.NOT_RUN,
            status=RunStatus.NOT_RUN,
        )
        restored = RunManifest.from_dict(json.loads(json.dumps(manifest.to_dict())))
        self.assertEqual(restored.status, RunStatus.NOT_RUN)
        self.assertEqual(restored.execution_mode, ExecutionMode.NOT_RUN)

    def test_sensitive_data_is_rejected_from_trace_and_manifest(self) -> None:
        manifest = make_run_manifest(
            run_id="run-001",
            task_id="task-001",
            rewindcoder_commit="27bdab5",
            fixture_base_commit="fixture-base-001",
            python_version="3.11",
            execution_mode=ExecutionMode.LOCAL,
            test_commands=("python -m unittest",),
            test_results={"result": "PASS"},
            status=RunStatus.PASS,
        ).to_dict()
        manifest["test_results"] = {"env_file": ".env"}
        with self.assertRaisesRegex(ContractValidationError, r"\.env"):
            RunManifest.from_dict(manifest)

    def test_contracts_reject_unknown_fields_and_versions(self) -> None:
        invalid_task = load_sample_task()
        invalid_task["typo_requirement"] = True
        with self.assertRaisesRegex(ContractValidationError, "unknown"):
            TaskContract.from_dict(invalid_task)

        invalid_trace = {
            "schema_version": "trace/v2",
            "timestamp": "2026-10-01T00:00:00+00:00",
            "run_id": "run-001",
            "task_id": "task-001",
            "node": "verify",
            "event": "started",
            "details": {},
        }
        with self.assertRaisesRegex(ContractValidationError, "schema_version"):
            TraceEvent.from_dict(invalid_trace)
