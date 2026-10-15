"""Replay one manifest against its frozen fixture and compare verifier outcome."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, _runner_source_hash, run_task
from rewindcoder.contracts.manifest import validate_run_manifest
from rewindcoder.providers.mock import RecoveryMockProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    original = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_run_manifest(original)
    protocol_path = PROJECT_ROOT / "evals/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (original["evaluation"]["protocol_sha256"] != hashlib.sha256(protocol_path.read_bytes()).hexdigest()
            or original["runner_source_sha256"] != _runner_source_hash()):
        raise ValueError("protocol or source drift")
    task_path = PROJECT_ROOT / protocol["task_paths"][original["task_id"]]
    if hashlib.sha256(task_path.read_bytes()).hexdigest() != original["task_sha256"]:
        raise ValueError("task drift")
    if original["evaluation"]["variant"] not in protocol["variants"]:
        raise ValueError("unplanned variant")
    replay = run_task(task_path, PROJECT_ROOT / "artifacts/phase5-replay",
        RecoveryMockProvider(protocol["scenario"]), seed=original["seed"],
        recovery=True, variant=original["evaluation"]["variant"])
    current = json.loads((Path(replay["run_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    checks = {
        "base_commit": current["fixture_base_commit"] == original["fixture_base_commit"],
        "budget": current["budget"] == original["budget"],
        "tests": current["test_commands"] == original["test_commands"],
        "status": current["status"] == original["status"],
        "verifier_passed": current["verifier_result"]["passed"] == original["verifier_result"]["passed"],
        "restore_conclusion": (current["recovery"].get("restore") or {}).get("conclusion") ==
                              (original["recovery"].get("restore") or {}).get("conclusion"),
    }
    print(json.dumps({"replay_manifest": str(Path(replay["run_dir"]) / "manifest.json"),
                      "checks": checks, "passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
