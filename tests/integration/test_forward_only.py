import json
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from rewindcoder.agent.graph import PROJECT_ROOT, run_task
from rewindcoder.providers.base import EditProposal, Plan
from rewindcoder.providers.mock import MockProvider
from rewindcoder.tools.workspace import WorkspaceTools


TASK_NAMES = ("sample_recovery_task.json", "tsv_whitespace.json", "adapter_service.json")


def run_fixture(name, provider=None, budget_changes=None):
    source = PROJECT_ROOT / "evals/tasks" / name
    task_path = source
    if budget_changes:
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["budget"].update(budget_changes)
        task_path = PROJECT_ROOT / "artifacts" / "test-tasks" / f"{uuid.uuid4().hex}.json"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_task(task_path, PROJECT_ROOT / "artifacts" / "test-runs", provider or MockProvider())
    run_dir = Path(result["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return result, manifest, trace, run_dir


class BreakRegressionProvider(MockProvider):
    def propose_edits(self, task, evidence):
        return (EditProposal(
            "src/parser.py", "    return value.strip()",
            "    name = value.strip()\n    if not name:\n        raise ValueError(\"empty\")\n    return \"wrong\"",
        ),)


class ForbiddenProvider(MockProvider):
    def propose_edits(self, task, evidence):
        return (EditProposal("README.md", "# Parser fixture", "# altered"),)


class BreakTargetProvider(MockProvider):
    def propose_edits(self, task, evidence):
        return (EditProposal("src/parser.py", "    return value.strip()", "    return value"),)


class MissingValidationProvider(MockProvider):
    def plan(self, task, evidence):
        return Plan(task["issue"], ("src/parser.py",), "edit", (), ())


class SlowProvider(MockProvider):
    def clarify(self, task, evidence):
        time.sleep(2)
        return super().clarify(task, evidence)


class InspectPayloadProvider(MockProvider):
    def clarify(self, task, evidence):
        self.seen = task
        return super().clarify(task, evidence)


class PublicTestsOnlyProvider(MockProvider):
    def propose_edits(self, task, evidence):
        return (EditProposal(
            "src/service.py", "    return sum(normalize_amount(value) for value in values)",
            "    if any(value < 0 for value in values):\n        raise ValueError(\"negative\")\n    return sum(normalize_amount(value) for value in values)",
        ),)


class ForwardOnlyIntegrationTests(unittest.TestCase):
    def test_all_three_fixtures_finish_with_verifier_and_trace(self):
        for name in TASK_NAMES:
            with self.subTest(name=name):
                result, manifest, trace, run_dir = run_fixture(name)
                self.assertEqual(result["status"], "PASS")
                self.assertTrue(manifest["verifier_result"]["passed"])
                self.assertTrue((run_dir / "diff.patch").read_text(encoding="utf-8"))
                self.assertEqual({event["run_id"] for event in trace}, {result["run_id"]})
                self.assertEqual({event["task_id"] for event in trace}, {manifest["task_id"]})
                self.assertTrue(any(event["event"] == "verifier_result" for event in trace))
                calls = [event for event in trace if event["event"] == "tool_call"]
                self.assertTrue(any(event["details"]["tool"] == "edit_file" for event in calls))
                self.assertTrue(any(event["details"].get("command") == manifest["test_commands"][0] for event in calls))
                self.assertTrue(any(event["details"].get("command") == manifest["test_commands"][1] for event in calls))
                serialized = json.dumps(trace) + json.dumps(manifest)
                self.assertNotIn("evaluator_only", serialized)
                self.assertNotIn("gold_patch", serialized)
                self.assertNotIn("hidden_requirements", serialized)

    def test_regression_failure_is_not_pass(self):
        result, manifest, trace, _ = run_fixture(TASK_NAMES[0], BreakRegressionProvider())
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(manifest["verifier_result"]["regression_tests_passed"])
        self.assertTrue(any(event["event"] == "verifier_result" for event in trace))

    def test_target_failure_is_not_pass(self):
        result, manifest, _, _ = run_fixture(TASK_NAMES[0], BreakTargetProvider())
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(manifest["verifier_result"]["target_tests_passed"])

    def test_hidden_acceptance_rejects_public_test_only_patch(self):
        result, manifest, trace, _ = run_fixture(TASK_NAMES[2], PublicTestsOnlyProvider())
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(manifest["verifier_result"]["target_tests_passed"])
        self.assertTrue(manifest["verifier_result"]["regression_tests_passed"])
        self.assertFalse(manifest["verifier_result"]["hidden_checks_passed"])
        self.assertNotIn("A direct adapter call", json.dumps(trace))

    def test_provider_receives_only_public_task(self):
        provider = InspectPayloadProvider()
        run_fixture(TASK_NAMES[0], provider)
        self.assertNotIn("evaluator_only", provider.seen)
        self.assertNotIn("gold_patch", json.dumps(provider.seen))

    def test_invalid_plan_stops_before_edit(self):
        result, manifest, trace, _ = run_fixture(TASK_NAMES[0], MissingValidationProvider())
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(manifest["stop_reason"], "ValueError")
        self.assertFalse(any(event["details"].get("tool") == "edit_file" for event in trace if event["event"] == "tool_call"))

    def test_forbidden_edit_stops_without_mutation(self):
        result, manifest, trace, _ = run_fixture(TASK_NAMES[0], ForbiddenProvider())
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(manifest["stop_reason"], "forbidden edit")
        self.assertTrue(any(event["event"] == "tool_result" and event["details"].get("reason") == "forbidden edit" for event in trace))
        workspace = PROJECT_ROOT / "artifacts/runs" / result["run_id"]
        self.assertIn("# Parser fixture", (workspace / "README.md").read_text(encoding="utf-8"))

    def test_budget_and_provider_timeout_stop_with_manifest(self):
        for changes, provider, reason in (
            ({"max_agent_steps": 0}, MockProvider(), "max_agent_steps"),
            ({"max_tool_calls": 0}, MockProvider(), "max_tool_calls"),
            ({"max_tokens": 1}, MockProvider(), "max_tokens"),
            (None, MockProvider("timeout"), "TimeoutError"),
            (None, MockProvider("error"), "RuntimeError"),
        ):
            with self.subTest(reason=reason):
                result, manifest, trace, _ = run_fixture(TASK_NAMES[0], provider, changes)
                self.assertEqual(result["status"], "NOT_READY")
                self.assertEqual(manifest["stop_reason"], reason)
                self.assertTrue(trace)

    def test_deadline_stops_a_slow_provider(self):
        started = time.monotonic()
        result, manifest, _, _ = run_fixture(TASK_NAMES[0], SlowProvider(), {"timeout_seconds": 1})
        self.assertLess(time.monotonic() - started, 1.8)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(manifest["stop_reason"], "provider_timeout")

    def test_repeated_run_has_comparable_outcome(self):
        first = run_fixture(TASK_NAMES[0])[1]
        second = run_fixture(TASK_NAMES[0])[1]
        for key in ("task_id", "task_sha256", "fixture_base_commit", "provider", "seed", "budget", "status", "patch_sha256", "workspace_head"):
            self.assertEqual(first[key], second[key], key)
        self.assertEqual(first["verifier_result"], second["verifier_result"])

    def test_workspace_command_denies_output_and_network(self):
        workspace = PROJECT_ROOT / "evals/fixtures/parser-empty-name"
        tools = WorkspaceTools(workspace, ("README.md",))
        from rewindcoder.tools.workspace import ToolDenied
        for command in ("git diff --output=outside", "curl https://example.com", "python -c print(1)"):
            with self.subTest(command=command), self.assertRaises(ToolDenied):
                tools.run_command(command, 1)

    def test_tool_io_error_becomes_structured_observation(self):
        with patch.object(WorkspaceTools, "read_file", side_effect=OSError("disk error")):
            result, manifest, trace, _ = run_fixture(TASK_NAMES[0])
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(manifest["stop_reason"], "tool_error:OSError")
        self.assertTrue(any(event["event"] == "tool_result" and event["details"].get("reason") == "tool_error:OSError" for event in trace))
