"""Persist an offline, disposable CP1 manual-rewind demonstration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from rewindcoder.checkpoint.manager import run_target_test
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.fixtures import PROJECT_ROOT, prepare_fixture


def main() -> None:
    demo = PROJECT_ROOT / "artifacts" / "phase3-demo" / uuid.uuid4().hex
    demo.mkdir(parents=True)
    workspace = PROJECT_ROOT / "artifacts" / "runs" / f"phase3-demo-{uuid.uuid4().hex}"
    prepare_fixture(PROJECT_ROOT / "evals/fixtures/parser-empty-name", workspace)
    storage = demo / "checkpoints"
    state = RewindCoderState(task_id="demo-parser-001", issue="Preserve valid-name behavior",
                             current_goal="Keep valid names", plan=["inspect parser", "run valid-name tests"],
                             current_step=1, context_summary="Baseline is green", budget_remaining=10)
    state_path = demo / "input-agent-state.json"
    state_path.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    test = "python -m unittest tests.test_parser.ValidNameTests"
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}

    def cli(*args: str) -> dict | list:
        result = subprocess.run([sys.executable, "-B", "-m", "rewindcoder.cli", *args],
                                cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise RuntimeError(result.stderr + result.stdout)
        return json.loads(result.stdout)

    baseline = run_target_test(workspace, test, 10)
    created = cli("checkpoint", "create", "--workspace", str(workspace), "--storage", str(storage),
                  "--state", str(state_path), "--target-test", test, "--verified-requirement", "R2")
    cp_id = created["checkpoint_id"]
    listed = cli("checkpoint", "list", "--workspace", str(workspace), "--storage", str(storage))
    inspected = cli("checkpoint", "inspect", "--workspace", str(workspace), "--storage", str(storage),
                    "--checkpoint", cp_id)
    parser = workspace / "src/parser.py"
    parser.write_text("def normalize_name(value):\n    return 'wrong'\n", encoding="utf-8")
    harmful = run_target_test(workspace, test, 10)
    restored = cli("rewind", "--workspace", str(workspace), "--storage", str(storage),
                   "--checkpoint", cp_id, "--state-output", str(demo / "restored-agent-state.json"),
                   "--approve", "--approver", "phase3-demo")
    after = run_target_test(workspace, test, 10)
    summary = {"checkpoint_id": cp_id, "workspace": str(workspace), "storage": str(storage),
               "baseline_passed": baseline["passed"], "harmful_edit_tests_passed": harmful["passed"],
               "restored_tests_passed": after["passed"], "listed": listed, "inspected_id": inspected["checkpoint_id"],
               "rewind_conclusion": restored["conclusion"], "rewind_run_dir": restored["run_dir"],
               "checks": restored["steps"]}
    (demo / "demo-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"demo_dir": str(demo), **summary}, indent=2))


if __name__ == "__main__":
    main()
