"""Manual aligned restore with explicit approval and independent verification."""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from rewindcoder.checkpoint.manager import CheckpointManager
from rewindcoder.checkpoint.metadata import CheckpointMetadata
from rewindcoder.checkpoint.repository_snapshot import SnapshotError, canonical, git, restore
from rewindcoder.observability.trace import JsonlTrace
from rewindcoder.security.approval import ApprovalDecision
from rewindcoder.verification.checkpoint import verify_restored


@dataclass(frozen=True, slots=True)
class RestorePlan:
    checkpoint_id: str
    restore_agent_state: bool
    restore_repository_state: bool
    requires_approval: bool
    post_restore_checks: tuple[str, ...]


def prepare_restore(checkpoint: CheckpointMetadata) -> RestorePlan:
    if not checkpoint.safe:
        raise ValueError("Unsafe checkpoints cannot be restored")
    return RestorePlan(
        checkpoint_id=checkpoint.checkpoint_id,
        restore_agent_state=True,
        restore_repository_state=True,
        requires_approval=True,
        post_restore_checks=("workspace manifest", "git diff", "target tests"),
    )


def manual_rewind(manager: CheckpointManager, checkpoint_id: str, state_output: Path,
                  approval: ApprovalDecision, *, timeout_seconds: float = 30,
                  restore_agent_state: bool = True,
                  restore_repository_state: bool = True,
                  allow_fixture_ablation: bool = False) -> dict:
    if manager.workspace is None:
        raise SnapshotError("workspace required")
    workspace = manager.workspace
    if not (restore_agent_state and restore_repository_state):
        # Ablations are intentionally invalid restores. Restrict them to a
        # freshly generated fixture so this cannot become a production escape.
        fixture_runs = (Path(__file__).resolve().parents[3] / "artifacts" / "runs").resolve()
        if (not allow_fixture_ablation or not workspace.is_relative_to(fixture_runs) or
                not workspace.name.startswith("run-") or
                not (restore_agent_state or restore_repository_state)):
            raise SnapshotError("one-sided restore is restricted to disposable fixture runs")
    output = state_output.resolve()
    if output.is_relative_to(workspace) or output.is_symlink():
        raise SnapshotError("agent state output must be outside workspace")
    run_id = f"rewind-{uuid.uuid4().hex}"
    run_dir = manager.storage_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    trace = JsonlTrace(run_dir / "trace.jsonl")
    steps: dict = {}
    conclusion = "NOT_READY"
    reason = ""
    deadline = time.monotonic() + timeout_seconds

    def record(step: str, passed: bool, detail: str) -> None:
        steps[step] = {"passed": passed, "detail": detail}
        trace.emit(run_id=run_id, task_id=checkpoint_id, node="manual_rewind",
                   event=step, details={"checkpoint_id": checkpoint_id, "passed": passed, "detail": detail})

    try:
        record("approval", approval.approved, approval.reason)
        if not approval.approved or not approval.approver:
            raise SnapshotError("explicit restore approval required")
        if timeout_seconds <= 0:
            raise SnapshotError("restore timeout budget exhausted")
        metadata = manager.load(checkpoint_id)
        manifest = manager._validate_bundle(manager._path(checkpoint_id), metadata)
        record("checkpoint_integrity", True, "archive, manifest, state and test evidence validated")
        actual_head = git(workspace, "rev-parse", "HEAD").decode().strip()
        record("git_head", actual_head == metadata.git_head, actual_head)
        if actual_head != metadata.git_head:
            raise SnapshotError("Git HEAD mismatch")
        if time.monotonic() >= deadline:
            raise SnapshotError("restore timeout budget exhausted")
        if restore_repository_state:
            restore(workspace, manager._path(checkpoint_id) / "workspace.zip", manifest)
            record("repository_restore", True, "snapshot bytes applied")
        else:
            record("repository_restore", False, "intentionally omitted by fixture ablation")
        if restore_agent_state:
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".agent-state-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(canonical(metadata.agent_state))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
            record("agent_state_restore", True, str(output))
        else:
            record("agent_state_restore", False, "intentionally omitted by fixture ablation")
        verified = verify_restored(workspace, output, metadata, manifest,
                                   timeout_seconds=max(0, deadline - time.monotonic()))
        for step, value in verified["checks"].items():
            record(f"verify_{step}", value["passed"], json.dumps(value, ensure_ascii=False))
        if not verified["passed"]:
            raise SnapshotError("post-restore verification failed")
        conclusion = "PASS"
    except Exception as error:
        reason = str(error)
        record("stop", False, reason)
    finally:
        manifest_out = {"schema_version": "rewind-run/v1", "run_id": run_id,
                        "checkpoint_id": checkpoint_id, "action": "manual_rewind",
                        "approval": {"approved": approval.approved, "approver": approval.approver, "reason": approval.reason},
                        "steps": steps, "conclusion": conclusion, "reason": reason}
        (run_dir / "manifest.json").write_bytes(canonical(manifest_out))
    return {**manifest_out, "run_dir": str(run_dir)}

