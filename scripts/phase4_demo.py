"""Persist three reviewed offline failure-injection recovery trajectories."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, run_task
from rewindcoder.providers.mock import RecoveryMockProvider


def main() -> int:
    output = PROJECT_ROOT / "evals/results/self_recovery"
    task = PROJECT_ROOT / "evals/tasks/sample_recovery_task.json"
    summary: dict[str, dict] = {}
    for scenario in ("target_failure", "regression_failure", "no_progress"):
        result = run_task(task, output, RecoveryMockProvider(scenario), recovery=True)
        run_dir = Path(result["run_dir"])
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        recovery = manifest["recovery"]
        required = (run_dir / "trace.jsonl", run_dir / "manifest.json",
                    run_dir / "diff.patch", run_dir / "post-recovery-state.json",
                    run_dir / "checkpoints" / recovery["checkpoint_id"] / "workspace.zip",
                    run_dir / "checkpoints" / recovery["checkpoint_id"] / "test-evidence.json")
        if not all(path.is_file() for path in required):
            raise RuntimeError(f"incomplete demo artifacts for {scenario}")
        if hashlib.sha256((run_dir / "trace.jsonl").read_bytes()).hexdigest() != manifest["trace_sha256"]:
            raise RuntimeError(f"trace hash mismatch for {scenario}")
        if hashlib.sha256((run_dir / "diff.patch").read_bytes()).hexdigest() != manifest["patch_sha256"]:
            raise RuntimeError(f"patch hash mismatch for {scenario}")
        if (json.loads((run_dir / "post-recovery-state.json").read_text(encoding="utf-8"))
                ["current_checkpoint"] != recovery["checkpoint_id"]):
            raise RuntimeError(f"agent state checkpoint mismatch for {scenario}")
        summary[scenario] = {
            "status": result["status"],
            "run_id": result["run_id"],
            "checkpoint_id": recovery["checkpoint_id"],
            "decisions": recovery["decisions"],
            "initial_action": recovery["memory"]["failed_actions"][0] if recovery["memory"] else None,
            "alternative_action": recovery["alternative"]["action"] if recovery["alternative"] else None,
            "restore_conclusion": recovery["restore"]["conclusion"] if recovery["restore"] else None,
            "verifier_passed": manifest["verifier_result"]["passed"],
            "trace": str(run_dir / "trace.jsonl"),
            "run_manifest": str(run_dir / "manifest.json"),
            "patch": str(run_dir / "diff.patch"),
            "agent_state": str(run_dir / "post-recovery-state.json"),
            "rewind_trace": str(Path(recovery["restore"]["run_dir"]) / "trace.jsonl") if recovery["restore"] else None,
        }
    output.mkdir(parents=True, exist_ok=True)
    (output / "demo-summary.json").write_text(json.dumps(summary, indent=2,
        ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all(item["status"] == "PASS" and item["verifier_passed"] and
                    item["restore_conclusion"] == "PASS" and
                    item["decisions"][-1]["failure_type"] == scenario
                    for scenario, item in summary.items()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
