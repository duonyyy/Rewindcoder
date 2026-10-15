"""Phase 3 disposable Git workspaces; never rewinds the project checkout."""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from rewindcoder.checkpoint.manager import CheckpointManager, run_target_test
from rewindcoder.checkpoint.repository_snapshot import SnapshotError, git, inventory, safe_path
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.fixtures import PROJECT_ROOT, prepare_fixture
from rewindcoder.recovery.executor import manual_rewind
from rewindcoder.security.approval import ApprovalDecision
from rewindcoder.verification.checkpoint import verify_restored


TEST = "python -m unittest tests.test_parser.ValidNameTests"


class Phase3CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.base = PROJECT_ROOT / "artifacts" / "phase3-tests" / uuid.uuid4().hex
        self.base.mkdir(parents=True)
        self.workspace = PROJECT_ROOT / "artifacts" / "runs" / f"phase3-{uuid.uuid4().hex}"
        prepare_fixture(PROJECT_ROOT / "evals/fixtures/parser-empty-name", self.workspace)
        self.manager = CheckpointManager(self.base / "checkpoints", self.workspace)
        self.state = RewindCoderState(task_id="demo-parser-001", issue="Keep valid names",
                                      current_goal="preserve valid names", plan=["inspect", "test"],
                                      current_step=1, context_summary="clean baseline", budget_remaining=7)
        self.output = self.base / "restored-state.json"
        self.approval = ApprovalDecision(True, "fixture-test", "disposable fixture approved")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)
        shutil.rmtree(self.base, ignore_errors=True)

    def checkpoint(self):
        return self.manager.create(self.state, test_command=TEST, verified_requirements=("R2",))

    def rewind(self, cp, approval=None, timeout=10):
        return manual_rewind(self.manager, cp.checkpoint_id, self.output,
                             approval or self.approval, timeout_seconds=timeout)

    def test_cp1_harmful_edit_failed_tests_aligned_restore(self):
        self.assertTrue(run_target_test(self.workspace, TEST, 10)["passed"])
        cp = self.checkpoint()
        self.assertEqual([item.checkpoint_id for item in self.manager.list_safe()], [cp.checkpoint_id])
        parser = self.workspace / "src/parser.py"
        parser.write_text("def normalize_name(value):\n    return 'wrong'\n", encoding="utf-8")
        self.assertFalse(run_target_test(self.workspace, TEST, 10)["passed"])
        result = self.rewind(cp)
        self.assertEqual(result["conclusion"], "PASS", result)
        self.assertEqual(inventory(self.workspace)["hashes"], cp.workspace_manifest)
        self.assertTrue(run_target_test(self.workspace, TEST, 10)["passed"])
        restored = RewindCoderState.from_dict(json.loads(self.output.read_text(encoding="utf-8")))
        self.assertEqual((restored.current_goal, restored.plan, restored.current_step,
                          restored.budget_remaining, restored.context_summary, restored.current_checkpoint),
                         (self.state.current_goal, self.state.plan, self.state.current_step,
                          self.state.budget_remaining, self.state.context_summary, cp.checkpoint_id))
        self.assertTrue((Path(result["run_dir"]) / "trace.jsonl").is_file())
        self.assertTrue(all(result["steps"][f"verify_{key}"]["passed"] for key in
                            ("workspace_manifest", "git_diff", "agent_state", "target_tests")))

    def test_tracked_edit_delete_and_untracked_create_edit_delete(self):
        tracked = self.workspace / "src/parser.py"
        tracked.write_text(tracked.read_text(encoding="utf-8") + "\n# checkpoint edit\n", encoding="utf-8")
        original = self.workspace / "README.md"
        original.unlink()
        untracked = self.workspace / "notes.txt"
        untracked.write_text("first", encoding="utf-8")
        deleted_untracked = self.workspace / "restore-me.txt"
        deleted_untracked.write_text("at checkpoint", encoding="utf-8")
        cp = self.checkpoint()
        tracked.write_text("broken", encoding="utf-8")
        original.write_text("broken", encoding="utf-8")
        untracked.write_text("changed", encoding="utf-8")
        deleted_untracked.unlink()
        extra = self.workspace / "extra.txt"
        extra.write_text("new", encoding="utf-8")
        result = self.rewind(cp)
        self.assertEqual(result["conclusion"], "PASS", result)
        self.assertFalse(original.exists())
        self.assertFalse(extra.exists())
        self.assertEqual(untracked.read_text(encoding="utf-8"), "first")
        self.assertEqual(deleted_untracked.read_text(encoding="utf-8"), "at checkpoint")
        self.assertEqual(inventory(self.workspace)["hashes"], cp.workspace_manifest)

    def test_one_sided_restore_is_rejected(self):
        cp = self.checkpoint()
        manifest = self.manager._validate_bundle(self.manager._path(cp.checkpoint_id), cp)
        (self.workspace / "src/parser.py").write_text("broken", encoding="utf-8")
        self.output.write_text(json.dumps(cp.agent_state), encoding="utf-8")
        agent_only = verify_restored(self.workspace, self.output, cp, manifest, timeout_seconds=10)
        self.assertFalse(agent_only["passed"])
        self.assertFalse(agent_only["checks"]["workspace_manifest"]["passed"])
        from rewindcoder.checkpoint.repository_snapshot import restore
        restore(self.workspace, self.manager._path(cp.checkpoint_id) / "workspace.zip", manifest)
        self.output.write_text(json.dumps({**cp.agent_state, "current_goal": "stale"}), encoding="utf-8")
        repo_only = verify_restored(self.workspace, self.output, cp, manifest, timeout_seconds=10)
        self.assertFalse(repo_only["passed"])
        self.assertFalse(repo_only["checks"]["agent_state"]["passed"])

    def test_missing_corrupt_and_pending_bundles_are_not_safe(self):
        cp = self.checkpoint()
        bundle = self.manager._path(cp.checkpoint_id)
        (self.manager.storage_dir / ".pending-crash").mkdir()
        self.assertEqual(len(self.manager.list_safe()), 1)
        (bundle / "workspace.zip").write_bytes(b"corrupt")
        self.assertFalse(self.manager.list_safe())
        self.assertEqual(self.rewind(cp)["conclusion"], "NOT_READY")
        cp2 = self.checkpoint()
        (self.manager._path(cp2.checkpoint_id) / "test-evidence.json").unlink()
        self.assertFalse(self.manager.list_safe())
        cp3 = self.checkpoint()
        (self.manager._path(cp3.checkpoint_id) / "manifest.json").unlink()
        self.assertFalse(self.manager.list_safe())
        cp4 = self.checkpoint()
        (self.manager._path(cp4.checkpoint_id) / "workspace.zip").unlink()
        self.assertFalse(self.manager.list_safe())

    def test_atomic_publish_failure_never_lists_pending_checkpoint(self):
        with patch("rewindcoder.checkpoint.manager.capture", side_effect=OSError("injected write failure")):
            with self.assertRaises(OSError):
                self.checkpoint()
        self.assertEqual(self.manager.list_safe(), [])
        self.assertEqual(list(self.manager.storage_dir.glob("cp-*")), [])

    def test_checkpoint_cannot_be_restored_into_other_workspace(self):
        cp = self.checkpoint()
        other = PROJECT_ROOT / "artifacts" / "runs" / f"phase3-{uuid.uuid4().hex}"
        try:
            prepare_fixture(PROJECT_ROOT / "evals/fixtures/parser-empty-name", other)
            foreign = CheckpointManager(self.manager.storage_dir, other)
            result = manual_rewind(foreign, cp.checkpoint_id, self.output, self.approval)
            self.assertEqual(result["conclusion"], "NOT_READY")
            self.assertIn("another workspace", result["reason"])
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_head_mismatch_approval_denial_and_budget(self):
        cp = self.checkpoint()
        (self.workspace / "src/parser.py").write_text("broken", encoding="utf-8")
        denied = self.rewind(cp, ApprovalDecision(False, None, "denied"))
        self.assertEqual(denied["conclusion"], "NOT_READY")
        self.assertEqual((self.workspace / "src/parser.py").read_text(encoding="utf-8"), "broken")
        self.assertEqual(self.rewind(cp, timeout=0)["conclusion"], "NOT_READY")
        git(self.workspace, "-c", "user.name=Fixture", "-c", "user.email=fixture@invalid", "commit", "--allow-empty", "-m", "other")
        result = self.rewind(cp)
        self.assertEqual(result["conclusion"], "NOT_READY")
        self.assertIn("Git HEAD mismatch", result["reason"])

    def test_symlink_traversal_and_storage_boundary(self):
        for name in ("../escape", "/absolute", ".git/config", "a/../../escape"):
            with self.subTest(name=name), self.assertRaises(SnapshotError):
                safe_path(self.workspace, name)
        with self.assertRaises(SnapshotError):
            CheckpointManager(self.workspace / "checkpoints", self.workspace)
        link = self.workspace / "link.txt"
        try:
            link.symlink_to(self.base / "outside.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(SnapshotError):
            self.checkpoint()


if __name__ == "__main__":
    unittest.main()
