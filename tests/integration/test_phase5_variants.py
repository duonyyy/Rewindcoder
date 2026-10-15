"""Variant policy and independent restore evidence on disposable fixtures."""

import json
import unittest
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, run_task
from rewindcoder.checkpoint.repository_snapshot import SnapshotError
from rewindcoder.providers.mock import RecoveryMockProvider
from rewindcoder.recovery.executor import manual_rewind
from rewindcoder.security.approval import ApprovalDecision


class Phase5VariantTests(unittest.TestCase):
    def test_six_policies_have_distinct_evidence(self):
        expected = {
            "forward_only": "FAIL", "retry_only": "PASS",
            "agent_state_rewind": "NOT_READY", "repository_only_rewind": "NOT_READY",
            "aligned_no_memory": "PASS", "rewindcoder_full": "PASS",
        }
        tasks = (
            "evals/tasks/sample_recovery_task.json",
            "evals/phase5_tasks/tsv_whitespace.json",
            "evals/phase5_tasks/adapter_service.json",
        )
        for task in tasks:
            for variant, status in expected.items():
                with self.subTest(task=task, variant=variant):
                    result = run_task(PROJECT_ROOT / task,
                        PROJECT_ROOT / "artifacts/phase5-tests", RecoveryMockProvider("target_failure"),
                        recovery=True, variant=variant)
                    manifest = json.loads((Path(result["run_dir"]) / "manifest.json").read_text(encoding="utf-8"))
                    self.assertEqual(manifest["status"], status)
                    self.assertEqual(manifest["recovery"]["variant"], variant)
                    self.assertEqual(manifest["verifier_result"]["passed"], status == "PASS")
                    if variant in {"forward_only", "retry_only"}:
                        self.assertIsNone(manifest["recovery"]["restore"])
                    if variant in {"agent_state_rewind", "repository_only_rewind"}:
                        self.assertEqual(manifest["recovery"]["restore"]["conclusion"], "NOT_READY")
                        self.assertIn("post-restore verification failed", manifest["stop_reason"])
                    if variant == "aligned_no_memory":
                        self.assertIsNone(manifest["recovery"]["memory"])
                    if variant == "rewindcoder_full":
                        self.assertTrue(manifest["recovery"]["memory"])

    def test_one_sided_restore_requires_explicit_fixture_ablation_gate(self):
        from unittest.mock import Mock
        manager = Mock()
        manager.workspace = PROJECT_ROOT / "evals/fixtures/parser-empty-name"
        with self.assertRaises(SnapshotError):
            manual_rewind(manager, "cp-not-used", PROJECT_ROOT / "artifacts/state.json",
                ApprovalDecision(True, "test", "test"), restore_agent_state=False,
                restore_repository_state=True, allow_fixture_ablation=True)


if __name__ == "__main__":
    unittest.main()
