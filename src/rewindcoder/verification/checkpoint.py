"""Independent post-restore checks. The restore adapter cannot declare success."""

from __future__ import annotations

import json
from pathlib import Path

from rewindcoder.checkpoint.manager import run_target_test
from rewindcoder.checkpoint.metadata import CheckpointMetadata
from rewindcoder.checkpoint.repository_snapshot import canonical, git_diff_hash, inventory, sha256
from rewindcoder.contracts.state import RewindCoderState


def verify_restored(workspace: Path, state_path: Path, metadata: CheckpointMetadata,
                    manifest: dict, *, timeout_seconds: float) -> dict:
    checks: dict = {}
    try:
        current = inventory(workspace)
        checks["workspace_manifest"] = {"passed": current == manifest,
                                        "expected_sha256": metadata.manifest_sha256,
                                        "actual_sha256": sha256(canonical(current))}
    except Exception as error:
        checks["workspace_manifest"] = {"passed": False, "reason": str(error)}
    try:
        actual = git_diff_hash(workspace)
        checks["git_diff"] = {"passed": actual == metadata.git_diff_sha256,
                              "expected_sha256": metadata.git_diff_sha256, "actual_sha256": actual}
    except Exception as error:
        checks["git_diff"] = {"passed": False, "reason": str(error)}
    try:
        state = RewindCoderState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
        checks["agent_state"] = {"passed": state.to_dict() == metadata.agent_state and state.current_checkpoint == metadata.checkpoint_id}
    except Exception as error:
        checks["agent_state"] = {"passed": False, "reason": str(error)}
    try:
        test = run_target_test(workspace, metadata.test_status["command"], timeout_seconds)
        checks["target_tests"] = {"passed": test["passed"] == metadata.test_status["passed"] and test["exit_code"] == metadata.test_status["exit_code"],
                                  "result": test}
    except Exception as error:
        checks["target_tests"] = {"passed": False, "reason": str(error)}
    return {"passed": all(item["passed"] for item in checks.values()), "checks": checks}
