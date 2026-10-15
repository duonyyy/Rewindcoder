"""Full offline recovery trajectories and fail-closed injections."""

import json
import hashlib
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from rewindcoder.agent.graph import PROJECT_ROOT, run_task
from rewindcoder.checkpoint.manager import CheckpointManager
from rewindcoder.checkpoint.repository_snapshot import SnapshotError
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.fixtures import prepare_fixture
from rewindcoder.providers.base import EditProposal
from rewindcoder.providers.mock import RecoveryMockProvider
from rewindcoder.recovery.selector import select_recoverable
from rewindcoder.security.approval import ApprovalDecision


TASK = PROJECT_ROOT / "evals/tasks/sample_recovery_task.json"
OUTPUT = PROJECT_ROOT / "artifacts/phase4-tests"


def execute(scenario="target_failure", provider=None, approval=None, budget=None):
    task_path = TASK
    if budget:
        payload = json.loads(TASK.read_text(encoding="utf-8"))
        payload["budget"].update(budget)
        task_path = PROJECT_ROOT / "artifacts/test-tasks" / f"phase4-{uuid.uuid4().hex}.json"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_task(task_path, OUTPUT, provider or RecoveryMockProvider(scenario),
                      recovery=True, approval=approval)
    run_dir = Path(result["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return result, manifest, trace, run_dir


class RepeatAlternativeProvider(RecoveryMockProvider):
    def alternative_plan(self, task, evidence, memory):
        action, plan, edits = super().alternative_plan(task, evidence, memory)
        return self.initial_action(), plan, edits


class RelabelFailedEditProvider(RecoveryMockProvider):
    def alternative_plan(self, task, evidence, memory):
        action, plan, _ = super().alternative_plan(task, evidence, memory)
        return action, plan, self.initial_edits(task, evidence)


class ForbiddenRecoveryProvider(RecoveryMockProvider):
    def initial_edits(self, task, evidence):
        return (EditProposal("README.md", "# Parser fixture", "# forbidden"),)


class UnexpectedRecoveryProvider(RecoveryMockProvider):
    def initial_edits(self, task, evidence):
        return super().initial_edits(task, evidence) + (
            EditProposal("tests/test_parser.py", "import unittest", "import unittest  # unexpected"),)

    def plan(self, task, evidence):
        plan = super().plan(task, evidence)
        from rewindcoder.providers.base import Plan
        return Plan(plan.goal, ("src/parser.py",), plan.approach, plan.constraints, plan.validation)


class Phase4RecoveryTests(unittest.TestCase):
    def test_three_failure_scenarios_have_aligned_e2e_evidence(self):
        for scenario in ("target_failure", "regression_failure", "no_progress"):
            with self.subTest(scenario=scenario):
                result, manifest, trace, run_dir = execute(scenario)
                self.assertEqual(result["status"], "PASS", result)
                recovery = manifest["recovery"]
                self.assertEqual([item["decision"] for item in recovery["decisions"]],
                                 ["diagnose", "rewind"])
                self.assertEqual(recovery["decisions"][-1]["failure_type"], scenario)
                self.assertTrue(recovery["restore"]["conclusion"] == "PASS")
                self.assertTrue(all(item["passed"] for item in recovery["restore"]["steps"].values()))
                self.assertEqual(manifest["verifier_result"]["checkpoint_id"],
                                 manifest["verifier_result"]["agent_checkpoint_id"])
                self.assertNotEqual(recovery["memory"]["failed_actions"][0],
                                    recovery["alternative"]["action"])
                self.assertNotIn(recovery["alternative"]["action"], recovery["memory"]["avoid_actions"])
                self.assertTrue(all(manifest["verifier_result"][key] for key in
                                    ("target_tests_passed", "regression_tests_passed", "hidden_checks_passed")))
                self.assertTrue((run_dir / "post-recovery-state.json").is_file())
                self.assertTrue((run_dir / "checkpoints" / recovery["checkpoint_id"] / "workspace.zip").is_file())
                self.assertTrue((run_dir / "checkpoints" / recovery["checkpoint_id"] / "test-evidence.json").is_file())
                self.assertEqual(hashlib.sha256((run_dir / "trace.jsonl").read_bytes()).hexdigest(),
                                 manifest["trace_sha256"])
                self.assertEqual(hashlib.sha256((run_dir / "diff.patch").read_bytes()).hexdigest(),
                                 manifest["patch_sha256"])
                self.assertEqual(json.loads((run_dir / "post-recovery-state.json").read_text())
                                 ["current_checkpoint"], recovery["checkpoint_id"])
                self.assertTrue(any(item["event"] == "memory_created" for item in trace))
                self.assertTrue(any(item["event"] == "alternative_plan" for item in trace))
                self.assertNotIn("evaluator_only", json.dumps(trace) + json.dumps(manifest))
                self.assertNotIn("gold_patch", json.dumps(trace) + json.dumps(manifest))
                self.assertNotIn("hidden_requirements", json.dumps(trace) + json.dumps(manifest))

    def test_security_budget_checkpoint_and_approval_fail_closed(self):
        with self.subTest("forbidden edit"):
            result, manifest, _, _ = execute(provider=ForbiddenRecoveryProvider("target_failure"))
            self.assertNotEqual(result["status"], "PASS")
            self.assertIn("forbidden edit", manifest["stop_reason"])
        with self.subTest("unexpected edit"):
            result, manifest, _, _ = execute(provider=UnexpectedRecoveryProvider("target_failure"))
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(manifest["recovery"]["decisions"][0]["decision"], "stop")
        with self.subTest("step budget"):
            result, manifest, _, _ = execute(budget={"max_agent_steps": 1})
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(manifest["stop_reason"], "max_agent_steps")
        with self.subTest("tool budget"):
            result, manifest, _, _ = execute(budget={"max_tool_calls": 0})
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(manifest["stop_reason"], "max_tool_calls")
        with self.subTest("token budget"):
            result, manifest, _, _ = execute(budget={"max_tokens": 1})
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(manifest["stop_reason"], "max_tokens")
        with self.subTest("rewind budget"):
            result, manifest, _, _ = execute(budget={"max_rewinds": 0})
            self.assertNotEqual(result["status"], "PASS")
            self.assertEqual(manifest["recovery"]["decisions"][-1]["decision"], "stop")
        with self.subTest("approval denied"):
            result, manifest, _, _ = execute(approval=ApprovalDecision(False, None, "denied"))
            self.assertNotEqual(result["status"], "PASS")
            self.assertFalse(manifest["recovery"]["approval"]["approved"])

    def test_missing_checkpoint_partial_restore_and_repeat_plan_stop(self):
        with patch.object(CheckpointManager, "list_safe", return_value=[]):
            result, manifest, _, _ = execute()
        self.assertNotEqual(result["status"], "PASS")
        self.assertIn("no recoverable checkpoint", manifest["stop_reason"])
        # Repository bytes have been restored, but writing agent state fails.
        with patch("rewindcoder.recovery.executor.tempfile.NamedTemporaryFile",
                   side_effect=OSError("agent state write failure")):
            result, manifest, _, _ = execute()
        self.assertNotEqual(result["status"], "PASS")
        self.assertIn("agent state write failure", manifest["stop_reason"])
        result, manifest, _, _ = execute(provider=RepeatAlternativeProvider("target_failure"))
        self.assertNotEqual(result["status"], "PASS")
        self.assertIn("avoid_action", manifest["stop_reason"])
        result, manifest, _, _ = execute(provider=RelabelFailedEditProvider("target_failure"))
        self.assertNotEqual(result["status"], "PASS")
        self.assertIn("failed edit bytes", manifest["stop_reason"])

    def test_selector_rejects_corruption_missing_evidence_and_head_mismatch(self):
        workspace = PROJECT_ROOT / "artifacts/runs" / f"phase4-selector-{uuid.uuid4().hex}"
        storage = PROJECT_ROOT / "artifacts/phase4-selector" / uuid.uuid4().hex
        prepare_fixture(PROJECT_ROOT / "evals/fixtures/parser-empty-name", workspace)
        manager = CheckpointManager(storage, workspace)
        state = RewindCoderState(task_id="demo-parser-001", issue="Fix parser")
        cp = manager.create(state, test_command="python -m unittest tests.test_parser.ValidNameTests")
        self.assertEqual(select_recoverable(manager).checkpoint_id, cp.checkpoint_id)
        (storage / cp.checkpoint_id / "workspace.zip").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "no recoverable"):
            select_recoverable(manager)
        cp2 = manager.create(state, test_command="python -m unittest tests.test_parser.ValidNameTests")
        (storage / cp2.checkpoint_id / "test-evidence.json").unlink()
        with self.assertRaisesRegex(ValueError, "no recoverable"):
            select_recoverable(manager)
        cp3 = manager.create(state, test_command="python -m unittest tests.test_parser.ValidNameTests")
        with patch("rewindcoder.recovery.selector.git", return_value=b"different-head\n"):
            with self.assertRaisesRegex(ValueError, "Git HEAD"):
                select_recoverable(manager)

    def test_elapsed_timeout_stops_without_pass(self):
        result, manifest, _, _ = execute(budget={"timeout_seconds": 1})
        self.assertNotEqual(result["status"], "PASS")
        self.assertTrue(manifest["stop_reason"])


if __name__ == "__main__":
    unittest.main()
