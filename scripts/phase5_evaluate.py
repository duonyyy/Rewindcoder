"""Frozen Phase 5 fixture smoke matrix. Run only reviewed disposable fixtures."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, _runner_source_hash, run_task
from rewindcoder.contracts.manifest import validate_run_manifest
from rewindcoder.providers.mock import RecoveryMockProvider


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protocol_path = PROJECT_ROOT / "evals/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_hash = digest(protocol_path)
    if protocol["schema_version"] != "evaluation-protocol/v1":
        raise ValueError("unsupported protocol")
    output = PROJECT_ROOT / "evals/results/raw" / protocol["protocol_id"]
    output.mkdir(parents=True, exist_ok=True)
    task_files = {task_id: PROJECT_ROOT / relative
                  for task_id, relative in protocol["task_paths"].items()}
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True).stdout.strip())
    cells = []
    for task_id in protocol["task_ids"]:
        task_path = task_files[task_id]
        for variant in protocol["variants"]:
            for seed in protocol["seeds"]:
                cell_dir = output / task_id / variant / f"seed-{seed}"
                cell_dir.mkdir(parents=True, exist_ok=True)
                existing = sorted(cell_dir.glob(f"{task_id}/run-*/manifest.json"))
                if existing:
                    if len(existing) != 1:
                        raise RuntimeError(f"duplicate run: {cell_dir}")
                    manifest = json.loads(existing[0].read_text(encoding="utf-8"))
                    validate_run_manifest(manifest)
                    if (manifest.get("evaluation", {}).get("protocol_sha256") != protocol_hash or
                            manifest.get("evaluation", {}).get("variant") != variant or
                            manifest.get("evaluation", {}).get("runner_sha256") != digest(Path(__file__)) or
                            manifest.get("runner_source_sha256") != _runner_source_hash() or
                            manifest.get("task_sha256") != digest(task_path) or
                            manifest.get("seed") != seed):
                        raise RuntimeError(f"resume mismatch: {cell_dir}")
                    cells.append({"task_id": task_id, "variant": variant, "seed": seed,
                        "state": "RECORDED", "manifest": str(existing[0].relative_to(output))})
                    continue
                result = run_task(task_path, cell_dir, RecoveryMockProvider(protocol["scenario"]),
                                  seed=seed, recovery=True, variant=variant)
                manifest_path = Path(result["run_dir"]) / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["evaluation"] = {
                    "protocol_id": protocol["protocol_id"], "protocol_version": protocol["schema_version"],
                    "protocol_sha256": protocol_hash, "variant": variant,
                    "runner_sha256": digest(Path(__file__)), "source_dirty": dirty,
                }
                validate_run_manifest(manifest)
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
                cells.append({"task_id": task_id, "variant": variant, "seed": seed,
                    "state": "RECORDED", "manifest": str(manifest_path.relative_to(output))})
                print(f"{task_id} {variant} seed={seed}: {manifest['status']}", flush=True)
    index = {"schema_version": "evaluation-index/v1", "protocol_sha256": protocol_hash,
             "protocol_id": protocol["protocol_id"], "expected_cells": len(cells), "cells": cells}
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"expected": len(cells), "recorded": sum(c["state"] == "RECORDED" for c in cells),
                      "skipped": sum(c["state"] == "SKIP_UNSUPPORTED" for c in cells)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
