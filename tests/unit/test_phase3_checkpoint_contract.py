import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from rewindcoder.checkpoint.manager import CheckpointManager, _reject_evaluator_data
from rewindcoder.checkpoint.metadata import CHECKPOINT_SCHEMA_VERSION, CheckpointMetadata
from rewindcoder.checkpoint.repository_snapshot import SnapshotError, archive_bytes, capture, sha256, validate_name, safe_path
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.fixtures import PROJECT_ROOT


class Phase3ContractTests(unittest.TestCase):
    def test_schema_version_and_agent_identity_validation(self):
        state = RewindCoderState(task_id="t", issue="i").to_dict()
        raw = CheckpointMetadata("cp-1", "node", "head", {}, state, {}).to_dict()
        self.assertEqual(raw["schema_version"], CHECKPOINT_SCHEMA_VERSION)
        with self.assertRaises(ValueError):
            CheckpointMetadata.from_dict({**raw, "schema_version": "checkpoint/v999"})
        with self.assertRaises(ValueError):
            CheckpointMetadata.from_dict({**raw, "unexpected": 1})
        with self.assertRaises(ValueError):
            CheckpointMetadata.from_dict({**raw, "agent_state": {**state, "schema_version": "state/v999"}})
        with self.assertRaises(ValueError):
            CheckpointMetadata.from_dict({**raw, "checkpoint_id": "../outside"})

    def test_path_validation_rejects_traversal_and_symlink(self):
        for name in (".", "a//b", "../outside", "a/../../outside", "/absolute", ".git/index", "C:/outside", "a\\b"):
            with self.subTest(name=name), self.assertRaises(SnapshotError):
                validate_name(name)
        root = Path("C:/fixture").resolve()
        original = Path.is_symlink
        def pretend_symlink(path):
            return path.name == "link" or original(path)
        with patch.object(Path, "is_symlink", pretend_symlink), self.assertRaises(SnapshotError):
            safe_path(root, "link/escape.txt")

    def test_evaluator_fields_never_enter_checkpoint_agent_state(self):
        with self.assertRaises(SnapshotError):
            _reject_evaluator_data({"tool_history": [{"evaluator_only": {"gold_patch": "secret"}}]})

    def test_capture_archives_bytes_and_rejects_race(self):
        base = PROJECT_ROOT / "artifacts" / "phase3-unit" / uuid.uuid4().hex
        root = base / "workspace"
        root.mkdir(parents=True)
        try:
            (root / "source.txt").write_bytes(b"checkpoint bytes")
            manifest = {"tracked": ["source.txt"], "untracked": [],
                        "hashes": {"source.txt": sha256(b"checkpoint bytes")}, "modes": {"source.txt": 0o666}}
            archive = base / "snapshot.zip"
            with patch("rewindcoder.checkpoint.repository_snapshot.inventory", return_value=manifest), \
                 patch("rewindcoder.checkpoint.repository_snapshot.git", return_value=b""):
                self.assertEqual(capture(root, archive), manifest)
            self.assertEqual(archive_bytes(archive, manifest)["source.txt"], b"checkpoint bytes")
            changed = {**manifest, "hashes": {"source.txt": sha256(b"changed")}}
            with patch("rewindcoder.checkpoint.repository_snapshot.inventory", side_effect=[manifest, changed]), \
                 patch("rewindcoder.checkpoint.repository_snapshot.git", return_value=b""):
                with self.assertRaises(SnapshotError):
                    capture(root, base / "race.zip")
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_atomic_publish_failure_never_exposes_checkpoint(self):
        base = PROJECT_ROOT / "artifacts" / "phase3-unit" / uuid.uuid4().hex
        workspace = base / "workspace"
        workspace.mkdir(parents=True)
        try:
            manager = CheckpointManager(base / "storage", workspace)
            state = RewindCoderState(task_id="t", issue="i")
            def fake_capture(_root, archive):
                archive.write_bytes(b"archive")
                return {"tracked": [], "untracked": [], "hashes": {}, "modes": {}}
            with patch("rewindcoder.checkpoint.manager.run_target_test", return_value={"passed": True, "command": "python -m unittest tests.test_parser.ValidNameTests", "exit_code": 0}), \
                 patch("rewindcoder.checkpoint.manager.git", side_effect=[b"head\n", b"", b"head\n"]), \
                 patch("rewindcoder.checkpoint.manager.capture", side_effect=fake_capture), \
                 patch.object(manager, "_validate_bundle", return_value={}), \
                 patch("rewindcoder.checkpoint.manager.os.replace", side_effect=OSError("publish failed")):
                with self.assertRaises(OSError):
                    manager.create(state, test_command="python -m unittest tests.test_parser.ValidNameTests")
            self.assertEqual(list(manager.storage_dir.iterdir()), [])
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
