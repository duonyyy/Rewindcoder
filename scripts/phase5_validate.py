"""Validate every frozen matrix cell before producing descriptive fixture metrics."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, _runner_source_hash
from rewindcoder.contracts.manifest import validate_run_manifest
from rewindcoder.contracts.trace import validate_trace_event


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protocol_path = PROJECT_ROOT / "evals/protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_hash = sha(protocol_path)
    root = PROJECT_ROOT / "evals/results/raw" / protocol["protocol_id"]
    issues: list[str] = []
    valid: list[dict] = []
    skipped: list[dict] = []
    run_ids: set[str] = set()
    task_files = {task_id: PROJECT_ROOT / relative
                  for task_id, relative in protocol["task_paths"].items()}
    expected = {(task, variant, seed) for task in protocol["task_ids"]
                for variant in protocol["variants"] for seed in protocol["seeds"]}
    for task_id, variant, seed in sorted(expected):
        cell = root / task_id / variant / f"seed-{seed}"
        runs = sorted(cell.glob(f"{task_id}/run-*/manifest.json"))
        run_dirs = sorted(cell.glob(f"{task_id}/run-*"))
        skip_path = cell / "skip.json"
        if any(path.is_dir() and not (path / "manifest.json").is_file() for path in run_dirs):
            issues.append(f"incomplete run without manifest: {task_id}/{variant}/{seed}")
            continue
        if len(runs) > 1 or (runs and skip_path.is_file()):
            issues.append(f"duplicate/mixed cell: {task_id}/{variant}/{seed}")
            continue
        if not runs:
            if not skip_path.is_file():
                issues.append(f"missing cell: {task_id}/{variant}/{seed}")
                continue
            try:
                skip = json.loads(skip_path.read_text(encoding="utf-8"))
                if skip["state"] != "SKIP_UNSUPPORTED" or skip["protocol_sha256"] != protocol_hash:
                    raise ValueError("invalid skip record")
                skipped.append({"task_id": task_id, "variant": variant, "seed": seed,
                                "reason": skip["reason"]})
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                issues.append(f"invalid skip {cell}: {error}")
            continue
        path = runs[0]
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
            validate_run_manifest(m)
            task = json.loads(task_files[task_id].read_text(encoding="utf-8"))
            e = m["evaluation"]
            if (e["protocol_sha256"] != protocol_hash or e["protocol_version"] != protocol["schema_version"]
                    or e["variant"] != variant or m["recovery"]["variant"] != variant
                    or m["task_id"] != task_id or m["seed"] != seed):
                raise ValueError("identity/protocol mismatch")
            if m["run_id"] != path.parent.name or m["run_id"] in run_ids:
                raise ValueError("duplicate or mismatched run ID")
            run_ids.add(m["run_id"])
            if (m["fixture_base_commit"] != task["repository"]["base_commit"] or
                    m["workspace_head"] != task["repository"]["base_commit"] or
                    m["task_sha256"] != sha(task_files[task_id])):
                raise ValueError("base commit or task hash mismatch")
            if (m["budget"] != task["budget"] or
                    m["test_commands"] != task["target_commands"] + task["regression_commands"] or
                    m["tool_policy_version"] != protocol["tool_policy_version"] or
                    m["provider"] != "mock" or
                    m["provider_config"].get("scenario") != protocol["scenario"] or
                    m["runner_source_sha256"] != _runner_source_hash() or
                    e["runner_sha256"] != sha(PROJECT_ROOT / "scripts/phase5_evaluate.py")):
                raise ValueError("budget/provider/tests/source mismatch")
            if not all(isinstance(m["usage"].get(k), (int, float)) and m["usage"][k] >= 0
                       for k in ("steps", "token_estimate", "tool_calls", "elapsed_seconds")):
                raise ValueError("invalid metric usage")
            if (m["usage"]["steps"] > m["budget"]["max_agent_steps"] or
                    m["usage"]["tool_calls"] > m["budget"]["max_tool_calls"] or
                    m["usage"]["token_estimate"] > m["budget"]["max_tokens"]):
                raise ValueError("budget exceeded without fail-closed accounting")
            trace, patch = path.parent / "trace.jsonl", path.parent / "diff.patch"
            if not trace.is_file() or not patch.is_file() or sha(trace) != m["trace_sha256"] or sha(patch) != m["patch_sha256"]:
                raise ValueError("missing artifact or hash mismatch")
            raw_trace = trace.read_text(encoding="utf-8")
            if any(secret in raw_trace for secret in ('"evaluator_only"', '"gold_patch"', '"hidden_requirements"')):
                raise ValueError("evaluator-only data leaked to trace")
            events = [json.loads(line) for line in raw_trace.splitlines() if line.strip()]
            if not events or events[0]["event"] != "run_started" or events[-1]["event"] != "run_finished":
                raise ValueError("incomplete trace")
            for event in events:
                validate_trace_event(event)
                if event["run_id"] != m["run_id"] or event["task_id"] != task_id:
                    raise ValueError("foreign trace event")
            if events[-1]["details"].get("status") != m["status"]:
                raise ValueError("trace/manifest status mismatch")
            if not isinstance(m["verifier_result"].get("passed"), bool):
                raise ValueError("invalid independent verifier result")
            if m["status"] == "PASS" and not m["verifier_result"].get("passed"):
                raise ValueError("PASS without independent verifier")
            if variant in {"agent_state_rewind", "repository_only_rewind"} and m["status"] == "PASS":
                raise ValueError("one-sided restore cannot PASS")
            valid.append({"task_id": task_id, "variant": variant, "seed": seed,
                          "manifest": str(path.relative_to(root)), "run": m})
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            issues.append(f"invalid {path}: {error}")
    actual_cells = {(p.relative_to(root).parts[0], p.relative_to(root).parts[1],
                     int(p.relative_to(root).parts[2].removeprefix("seed-")))
                    for p in root.glob("*/*/seed-*/*/run-*/manifest.json")}
    if actual_cells - expected:
        issues.append(f"unplanned cells: {sorted(actual_cells - expected)}")
    paired = defaultdict(dict)
    for item in valid:
        paired[(item["task_id"], item["seed"])][item["variant"]] = item["run"]["status"]
    metrics = {}
    for variant in protocol["variants"]:
        subset = [x for x in valid if x["variant"] == variant]
        completed = [x for x in subset if x["run"]["status"] in {"PASS", "FAIL"}]
        passed = sum(x["run"]["status"] == "PASS" for x in completed)
        rewound = [x for x in subset if x["run"].get("recovery", {}).get("restore")]
        restore_ok = sum(x["run"]["recovery"]["restore"]["conclusion"] == "PASS" for x in rewound)
        regression_evaluable = [x for x in subset if isinstance(
            x["run"]["verifier_result"].get("regression_tests_passed"), bool)]
        regression = sum(x["run"]["verifier_result"]["regression_tests_passed"] is False
                         for x in regression_evaluable)
        post_rewind_failures = [x for x in rewound if x["run"]["recovery"]["restore"]["conclusion"] == "PASS"
                                and x["run"]["status"] == "FAIL"]
        metrics[variant] = {"planned": len(protocol["task_ids"]) * len(protocol["seeds"]),
            "valid": len(subset), "skipped": sum(x["variant"] == variant for x in skipped),
            "not_ready": sum(x["run"]["status"] == "NOT_READY" for x in subset),
            "task_success": {"numerator": passed, "denominator": len(completed)},
            "task_success_planned": {"numerator": passed,
                                     "denominator": len(protocol["task_ids"]) * len(protocol["seeds"]),
                                     "note": "Descriptive planned-cell yield; SKIP and NOT_READY retain separate statuses"},
            "recovery_success": {"numerator": sum(x["run"]["status"] == "PASS" for x in rewound),
                                 "denominator": len(rewound)},
            "repeated_failure": {"numerator": 0, "denominator": len(post_rewind_failures),
                                 "note": "No post-rewind failure was observed; zero denominator is N/A"},
            "wrong_rewind": {"numerator": len(rewound) - restore_ok, "denominator": len(rewound),
                             "note": "Intentional one-sided ablations count as policy-invalid restores"},
            "restore_integrity": {"numerator": restore_ok, "denominator": len(rewound)},
            "regression": {"numerator": regression, "denominator": len(regression_evaluable)},
            "token_estimate_total": sum(x["run"]["usage"]["token_estimate"] for x in subset),
            "latency_seconds_total": sum(x["run"]["usage"]["elapsed_seconds"] for x in subset),
            "tool_calls_total": sum(x["run"]["usage"]["tool_calls"] for x in subset),
            "rewinds": len(rewound),
            "checkpoint_bytes": sum(sum(p.stat().st_size for p in (root / x["manifest"]).parent.glob("checkpoints/cp-*/*") if p.is_file()) for x in subset)}
    summary = {"schema_version": "evaluation-summary/v1", "protocol_sha256": protocol_hash,
        "scope": "fixture smoke only; RQ1-RQ3 not inferable", "expected_cells": len(expected),
        "valid_cells": len(valid), "skipped_cells": skipped, "invalid_or_missing": issues,
        "paired_outcomes": [{"task_id": task, "seed": seed, "outcomes": outcomes}
                            for (task, seed), outcomes in sorted(paired.items())],
        "metrics": metrics}
    output = PROJECT_ROOT / "evals/results/summary"
    output.mkdir(parents=True, exist_ok=True)
    (output / "phase5-fixture-smoke.json").write_text(json.dumps(summary, indent=2,
        ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"expected": len(expected), "valid": len(valid), "skipped": len(skipped),
                      "invalid_or_missing": len(issues)}, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
