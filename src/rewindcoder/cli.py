"""Forward-only fixture runner and explicit Phase 3 checkpoint/rewind commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rewindcoder.agent.graph import PROJECT_ROOT, run_task
from rewindcoder.checkpoint.manager import CheckpointManager
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.providers.factory import create_provider
from rewindcoder.providers.mock import RecoveryMockProvider
from rewindcoder.recovery.executor import manual_rewind
from rewindcoder.security.approval import ApprovalDecision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rewindcoder")
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("run")
    run.add_argument("--task", required=True, type=Path)
    run.add_argument("--output", type=Path, default=PROJECT_ROOT / "evals/baselines/forward_only")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--recovery-scenario", choices=("target_failure", "regression_failure", "no_progress"))
    checkpoint = actions.add_parser("checkpoint")
    cp_actions = checkpoint.add_subparsers(dest="checkpoint_action", required=True)
    for name in ("create", "list", "inspect"):
        action = cp_actions.add_parser(name)
        action.add_argument("--workspace", required=True, type=Path)
        action.add_argument("--storage", required=True, type=Path)
        if name == "create":
            action.add_argument("--state", required=True, type=Path)
            action.add_argument("--target-test", required=True)
            action.add_argument("--verified-requirement", action="append", default=[])
            action.add_argument("--timeout", type=float, default=30)
        if name == "inspect":
            action.add_argument("--checkpoint", required=True)
    rewind = actions.add_parser("rewind")
    rewind.add_argument("--workspace", required=True, type=Path)
    rewind.add_argument("--storage", required=True, type=Path)
    rewind.add_argument("--checkpoint", required=True)
    rewind.add_argument("--state-output", required=True, type=Path)
    rewind.add_argument("--approve", action="store_true")
    rewind.add_argument("--approver")
    rewind.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            task_path = args.task if args.task.is_absolute() else PROJECT_ROOT / args.task
            if not task_path.resolve().is_relative_to((PROJECT_ROOT / "evals/tasks").resolve()):
                parser.error("task must be in evals/tasks")
            output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
            provider = RecoveryMockProvider(args.recovery_scenario) if args.recovery_scenario else create_provider()
            if args.recovery_scenario and args.output == PROJECT_ROOT / "evals/baselines/forward_only":
                output = PROJECT_ROOT / "evals/results/self_recovery"
            result = run_task(task_path, output, provider, seed=args.seed,
                              recovery=bool(args.recovery_scenario))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        manager = CheckpointManager(args.storage, args.workspace)
        if args.action == "checkpoint":
            if args.checkpoint_action == "create":
                state = RewindCoderState.from_dict(json.loads(args.state.read_text(encoding="utf-8")))
                result = manager.create(state, test_command=args.target_test,
                                        verified_requirements=tuple(args.verified_requirement),
                                        timeout_seconds=args.timeout).to_dict()
            elif args.checkpoint_action == "list":
                result = [{"checkpoint_id": item.checkpoint_id, "created_at": item.created_at,
                           "git_head": item.git_head, "safe": item.safe} for item in manager.list_safe()]
            else:
                result = manager.load(args.checkpoint).to_dict()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        approval = ApprovalDecision(args.approve, args.approver, "CLI explicit approval" if args.approve else "approval denied")
        result = manual_rewind(manager, args.checkpoint, args.state_output, approval,
                               timeout_seconds=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["conclusion"] == "PASS" else 1
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
