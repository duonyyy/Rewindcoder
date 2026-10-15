"""Offline fixture integrity check; gold files are evaluator-only."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from rewindcoder.contracts.task import TaskContract
from rewindcoder.fixtures import prepare_fixture


ROOT = Path(__file__).resolve().parents[1]
TASKS = ("sample_recovery_task.json", "tsv_whitespace.json", "adapter_service.json")


def _run(command: str, cwd: Path) -> bool:
    result = subprocess.run(
        command.split(), cwd=cwd, capture_output=True, text=True, timeout=20,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""},
    )
    return result.returncode == 0


def validate() -> dict:
    evidence = {}
    run_root = ROOT / "artifacts" / f"phase1-{uuid.uuid4().hex}"
    run_root.mkdir(parents=True)
    for name in TASKS:
        task = TaskContract.from_dict(json.loads((ROOT / "evals" / "tasks" / name).read_text(encoding="utf-8")))
        source = ROOT / task.repository.path
        fixture_manifest = json.loads((source / "fixture-manifest.json").read_text(encoding="utf-8"))
        base = run_root / f"{task.task_id}-base"
        gold = run_root / f"{task.task_id}-gold"
        first = prepare_fixture(source, base)
        second = prepare_fixture(source, gold)
        expected = task.repository.base_commit
        gold_file = ROOT / task.evaluator_only["gold_patch"]
        relative = gold_file.relative_to(ROOT / "evals" / "evaluator" / source.name)
        shutil.copyfile(gold_file, gold / relative)
        target = task.target_commands[0]
        regression = task.regression_commands[0]
        base_target = _run(target, base)
        base_regression = _run(regression, base)
        gold_target = _run(target, gold)
        gold_regression = _run(regression, gold)
        (gold / "README.md").write_text("forbidden edit\n", encoding="utf-8")
        changed = subprocess.run(
            ["git", "diff", "--name-only"], cwd=gold, capture_output=True,
            text=True, timeout=15, check=True,
        ).stdout.splitlines()
        result = {
            "base_commit_expected": expected, "base_commit_first": first,
            "base_commit_second": second, "base_target_passed": base_target,
            "base_regression_passed": base_regression,
            "gold_target_passed": gold_target, "gold_regression_passed": gold_regression,
            "forbidden_edit_detected": "README.md" in changed,
        }
        result["passed"] = (
            first == second == expected == fixture_manifest["base_commit"]
            and not base_target and base_regression and gold_target and gold_regression
            and result["forbidden_edit_detected"]
        )
        evidence[task.task_id] = result
    return {"fixtures": evidence, "passed": all(item["passed"] for item in evidence.values())}


if __name__ == "__main__":
    result = validate()
    output = ROOT / "evals" / "results" / "phase-1" / "fixture-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
