import json
import unittest
from pathlib import Path

from rewindcoder.contracts.task import TaskContract
from rewindcoder.providers.mock import MockProvider
from rewindcoder.tools.policy import Permission, command_permission
from rewindcoder.tools.workspace import ToolDenied, WorkspaceTools


ROOT = Path(__file__).resolve().parents[2]


class Phase1FoundationTests(unittest.TestCase):
    def test_provider_success_error_timeout_are_distinct(self):
        task = TaskContract.from_dict(json.loads((ROOT / "evals/tasks/sample_recovery_task.json").read_text(encoding="utf-8")))
        payload = task.to_agent_payload()
        self.assertEqual(len(MockProvider().clarify(payload, {})), 6)
        with self.assertRaises(RuntimeError):
            MockProvider("error").clarify(payload, {})
        with self.assertRaises(TimeoutError):
            MockProvider("timeout").clarify(payload, {})

    def test_command_policy_denies_unknown_network_and_execution_flags(self):
        for command in ("curl example.com", "python -c print(1)", "git diff --output=outside", "pytest --pyargs os", "python -m unittest tests.test_parser.EmptyNameTests; echo x"):
            self.assertEqual(command_permission(command), Permission.DENY if not command.startswith("git") else Permission.APPROVAL)
        self.assertEqual(command_permission("git reset --hard"), Permission.APPROVAL)
        self.assertEqual(command_permission("python -m unittest tests.test_parser.EmptyNameTests"), Permission.AUTO)

    def test_workspace_rejects_escape_forbidden_and_internal_paths(self):
        root = ROOT / "evals/fixtures/parser-empty-name"
        tools = WorkspaceTools(root, ("README.md", ".git/"))
        for path in ("../README.md", "C:/Windows/win.ini", ".git/config"):
            with self.assertRaises(ToolDenied):
                tools.read_file(path)
        with self.assertRaises(ToolDenied):
            tools.edit_file("README.md", "x", "y")
        self.assertIn("parse_name", tools.search("parse_name").value)

    def test_plan_needs_validation(self):
        from rewindcoder.providers.base import Plan
        with self.assertRaisesRegex(ValueError, "validation"):
            Plan("goal", ("src/a.py",), "edit", (), ()).validate()
