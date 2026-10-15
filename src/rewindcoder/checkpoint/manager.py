"""Publish complete checkpoint bundles atomically outside the target repository."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.tools.policy import Permission, command_permission
from rewindcoder.tools.workspace import WorkspaceTools

from .metadata import CheckpointMetadata
from .repository_snapshot import SnapshotError, archive_bytes, canonical, capture, git, sha256

_ID = re.compile(r"cp-[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _reject_evaluator_data(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"evaluator_only", "hidden_requirements", "gold_patch"}:
                raise SnapshotError("evaluator-only data cannot enter agent state")
            _reject_evaluator_data(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_evaluator_data(nested)


def run_target_test(workspace: Path, command: str, timeout_seconds: float) -> dict:
    if command_permission(command) != Permission.AUTO or not command.startswith("python -m unittest "):
        raise SnapshotError("target test command is not allowlisted")
    if timeout_seconds <= 0:
        raise SnapshotError("test timeout budget exhausted")
    result = WorkspaceTools(workspace, ()).run_command(command, timeout_seconds)
    return {"command": command, "passed": result.ok, "exit_code": result.exit_code,
            "summary": result.value[-1000:]}


class CheckpointManager:
    def __init__(self, storage_dir: Path, workspace: Path | None = None) -> None:
        self.storage_dir = storage_dir.resolve()
        self.workspace = workspace.resolve(strict=True) if workspace else None
        if self.workspace and (self.storage_dir == self.workspace or self.storage_dir.is_relative_to(self.workspace)
                               or self.workspace.is_relative_to(self.storage_dir)):
            raise SnapshotError("checkpoint storage must be outside target workspace")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create(self, state: RewindCoderState, *, test_command: str,
               verified_requirements: tuple[str, ...] = (), timeout_seconds: float = 30) -> CheckpointMetadata:
        if self.workspace is None:
            raise SnapshotError("workspace required")
        cp_id = f"cp-{uuid.uuid4().hex}"
        test = run_target_test(self.workspace, test_command, timeout_seconds)
        if not test["passed"]:
            raise SnapshotError("target tests failed; no safe checkpoint published")
        head = git(self.workspace, "rev-parse", "HEAD").decode().strip()
        state_copy = RewindCoderState.from_dict({**state.to_dict(), "current_checkpoint": cp_id})
        _reject_evaluator_data(state_copy.to_dict())
        staging = self.storage_dir / f".pending-{uuid.uuid4().hex}"
        staging.mkdir(exist_ok=False)
        try:
            archive = staging / "workspace.zip"
            manifest = capture(self.workspace, archive)
            diff_hash = sha256(git(self.workspace, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"))
            if git(self.workspace, "rev-parse", "HEAD").decode().strip() != head:
                raise SnapshotError("Git HEAD changed during capture")
            (staging / "manifest.json").write_bytes(canonical(manifest))
            (staging / "test-evidence.json").write_bytes(canonical(test))
            (staging / "agent-state.json").write_bytes(canonical(state_copy.to_dict()))
            metadata = CheckpointMetadata(
                checkpoint_id=cp_id, node="manual_checkpoint", git_head=head,
                workspace_manifest=manifest["hashes"], agent_state=state_copy.to_dict(),
                test_status=test, verified_requirements=verified_requirements,
                safe=True, risk_score=0.0, tracked_paths=tuple(manifest["tracked"]),
                untracked_paths=tuple(manifest["untracked"]),
                manifest_sha256=sha256((staging / "manifest.json").read_bytes()),
                archive_sha256=sha256(archive.read_bytes()),
                evidence_sha256=sha256((staging / "test-evidence.json").read_bytes()),
                agent_state_sha256=sha256((staging / "agent-state.json").read_bytes()),
                git_diff_sha256=diff_hash,
                workspace_root=str(self.workspace),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            (staging / "metadata.json").write_bytes(canonical(metadata.to_dict()))
            self._validate_bundle(staging, metadata)
            os.replace(staging, self.storage_dir / cp_id)
            return metadata
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _path(self, checkpoint_id: str) -> Path:
        if not _ID.fullmatch(checkpoint_id):
            raise SnapshotError("invalid checkpoint ID")
        path = self.storage_dir / checkpoint_id
        if path.is_symlink():
            raise SnapshotError("checkpoint symlink denied")
        return path

    @staticmethod
    def _validate_bundle(path: Path, metadata: CheckpointMetadata) -> dict:
        files = {name: path / name for name in ("manifest.json", "workspace.zip", "test-evidence.json", "agent-state.json")}
        expected = (metadata.manifest_sha256, metadata.archive_sha256,
                    metadata.evidence_sha256, metadata.agent_state_sha256)
        for (name, artifact), digest in zip(files.items(), expected):
            if artifact.is_symlink() or not artifact.is_file() or not _HASH.fullmatch(digest) or sha256(artifact.read_bytes()) != digest:
                raise SnapshotError(f"missing or corrupt {name}")
        manifest = json.loads(files["manifest.json"].read_text(encoding="utf-8"))
        evidence = json.loads(files["test-evidence.json"].read_text(encoding="utf-8"))
        agent = json.loads(files["agent-state.json"].read_text(encoding="utf-8"))
        if not metadata.safe or not evidence.get("passed") or not evidence.get("command"):
            raise SnapshotError("checkpoint lacks passing test evidence")
        if not isinstance(evidence["command"], str) or command_permission(evidence["command"]) != Permission.AUTO:
            raise SnapshotError("checkpoint test command denied")
        tracked, untracked, hashes, modes = (manifest[key] for key in ("tracked", "untracked", "hashes", "modes"))
        if not isinstance(tracked, list) or not isinstance(untracked, list) or not isinstance(hashes, dict) or not isinstance(modes, dict):
            raise SnapshotError("invalid workspace manifest")
        names = tracked + untracked
        if (any(not isinstance(name, str) for name in names) or len(names) != len(set(names))
                or len(names) != len({name.casefold() for name in names}) or set(names) != set(hashes)
                or set(modes) != {name for name, digest in hashes.items() if digest is not None}
                or any(digest is not None and (not isinstance(digest, str) or not _HASH.fullmatch(digest)) for digest in hashes.values())
                or any(not isinstance(mode, int) or mode < 0 or mode > 0o777 for mode in modes.values())):
            raise SnapshotError("invalid workspace manifest")
        _reject_evaluator_data(agent)
        if manifest["hashes"] != metadata.workspace_manifest or tuple(manifest["tracked"]) != metadata.tracked_paths or tuple(manifest["untracked"]) != metadata.untracked_paths:
            raise SnapshotError("manifest metadata mismatch")
        if agent != metadata.agent_state or RewindCoderState.from_dict(agent).current_checkpoint != metadata.checkpoint_id:
            raise SnapshotError("agent state alignment mismatch")
        if evidence != metadata.test_status:
            raise SnapshotError("test evidence mismatch")
        for name in manifest["hashes"]:
            from .repository_snapshot import validate_name
            validate_name(name)
        archive_bytes(files["workspace.zip"], manifest)
        return manifest

    def load(self, checkpoint_id: str) -> CheckpointMetadata:
        path = self._path(checkpoint_id)
        if not (path / "metadata.json").is_file() or (path / "metadata.json").is_symlink():
            raise SnapshotError("checkpoint metadata missing")
        metadata = CheckpointMetadata.from_dict(json.loads((path / "metadata.json").read_text(encoding="utf-8")))
        if metadata.checkpoint_id != checkpoint_id:
            raise SnapshotError("checkpoint identity mismatch")
        if self.workspace and Path(metadata.workspace_root).resolve() != self.workspace:
            raise SnapshotError("checkpoint belongs to another workspace")
        self._validate_bundle(path, metadata)
        return metadata

    def list_safe(self) -> list[CheckpointMetadata]:
        items = []
        for path in sorted(self.storage_dir.glob("cp-*")):
            try:
                items.append(self.load(path.name))
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
                continue
        return items
