"""Bounded recovery branch for reviewed, disposable offline fixtures."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from rewindcoder.checkpoint.manager import CheckpointManager
from rewindcoder.checkpoint.repository_snapshot import git
from rewindcoder.contracts.manifest import ExecutionMode, RunStatus, make_run_manifest
from rewindcoder.contracts.state import RewindCoderState
from rewindcoder.contracts.task import TaskContract
from rewindcoder.fixtures import PROJECT_ROOT, prepare_fixture
from rewindcoder.observability.trace import JsonlTrace
from rewindcoder.providers.mock import RecoveryMockProvider
from rewindcoder.recovery.detector import FailureSignals, RecoveryDecision, classify_failure, decide_recovery
from rewindcoder.recovery.executor import manual_rewind
from rewindcoder.recovery.memory import RewindMemory, validate_alternative
from rewindcoder.recovery.selector import select_recoverable
from rewindcoder.runtime.budget import BudgetExceeded, BudgetMeter
from rewindcoder.security.approval import ApprovalDecision
from rewindcoder.tools.policy import command_permission
from rewindcoder.tools.workspace import ToolDenied, WorkspaceTools
from rewindcoder.verification.definition_of_done import VerificationInput
from rewindcoder.verification.hidden import evaluate_hidden
from rewindcoder.verification.verifier import verify


EVALUATION_VARIANTS = (
    "forward_only", "retry_only", "agent_state_rewind",
    "repository_only_rewind", "aligned_no_memory", "rewindcoder_full",
)


class EvaluationTerminal(Exception):
    """A baseline reached its independent final verifier."""


def run_recovery_task(task_path: Path, output_base: Path, task: TaskContract, source: Path,
                      provider: RecoveryMockProvider, *, seed: int = 0,
                      approval: ApprovalDecision | None = None,
                      variant: str = "rewindcoder_full") -> dict[str, Any]:
    from rewindcoder.agent.graph import _hash, _patch, _project_commit, _provider_call, _runner_source_hash

    fixture_by_task = {"demo-parser-001": "parser-empty-name",
                       "tsv-whitespace-002": "tsv-whitespace",
                       "adapter-service-003": "adapter-service"}
    if not isinstance(provider, RecoveryMockProvider) or task.task_id not in fixture_by_task:
        raise ValueError("automatic recovery requires a reviewed mock fixture")
    if source.name != fixture_by_task[task.task_id] or task.budget.max_rewinds < 0:
        raise ValueError("fixture recovery policy denied")
    if variant not in EVALUATION_VARIANTS:
        raise ValueError("unknown evaluation variant")
    run_id = f"run-{uuid.uuid4().hex}"
    run_dir = output_base / task.task_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    workspace = PROJECT_ROOT / "artifacts" / "runs" / run_id
    trace_path = run_dir / "trace.jsonl"
    trace = JsonlTrace(trace_path)
    sequence = 0

    def emit(node: str, event: str, details: dict[str, Any]) -> str:
        nonlocal sequence
        sequence += 1
        event_id = f"event-{sequence:04d}"
        trace.emit(run_id=run_id, task_id=task.task_id, node=node, event=event,
                   details={"trace_id": event_id, **details})
        return event_id

    emit("run", "run_started", {"mode": "self_recovery", "provider": provider.name,
                                 "scenario": provider.scenario, "seed": seed, "variant": variant})
    base_commit = prepare_fixture(source, workspace,
        on_command=lambda command, permission: emit("fixture_bootstrap", "command",
            {"command": command, "permission": permission, "scope": "disposable_fixture"}))
    if base_commit != task.repository.base_commit:
        raise ValueError("fixture base_commit mismatch")
    tools = WorkspaceTools(workspace, task.forbidden_paths)
    budget = BudgetMeter(task.budget)
    public_task = task.to_agent_payload()
    manager = CheckpointManager(run_dir / "checkpoints", workspace)
    status = RunStatus.NOT_READY
    stop_reason = ""
    verifier_result: dict[str, Any] = {"passed": False, "failures": ["verification not run"]}
    test_results: dict[str, Any] = {"attempts": []}
    recovery: dict[str, Any] = {"scenario": provider.scenario, "variant": variant, "decisions": [],
                                "checkpoint_id": None, "approval": None, "restore": None,
                                "memory": None, "alternative": None}
    evidence: dict[str, str] = {}
    initial_action = provider.initial_action(task.task_id)
    current_node = "create_checkpoint"

    def call_tool(node: str, name: str, details: dict[str, Any], fn):
        budget.tool()
        emit(node, "tool_call", {"tool": name, **details})
        try:
            result = fn()
        except (ToolDenied, OSError, ValueError) as error:
            emit(node, "tool_result", {"tool": name, "ok": False, "reason": str(error)})
            raise
        emit(node, "tool_result", {"tool": name, "ok": result.ok,
                                   "exit_code": result.exit_code, "summary": result.value[-500:]})
        return result

    def run_tests(label: str) -> tuple[dict[str, list[dict]], list[str], str, str]:
        budget.step()
        results: dict[str, list[dict]] = {"target": [], "regression": []}
        trace_ids: list[str] = []
        for group, commands in (("target", task.target_commands), ("regression", task.regression_commands)):
            for command in commands:
                result = call_tool("run_tests", "run_command",
                                   {"command": command, "permission": command_permission(command).value},
                                   lambda c=command: tools.run_command(c, min(20, budget.remaining_seconds())))
                record = {"command": command, "passed": result.ok, "exit_code": result.exit_code,
                          "summary": result.value[-500:]}
                results[group].append(record)
                trace_ids.append(emit("run_tests", "test_result", {"attempt": label, "group": group, **record}))
        status_observation = call_tool("run_tests", "run_command", {"command": "git status --short"},
                                       lambda: tools.run_command("git status --short", min(10, budget.remaining_seconds())))
        diff_observation = call_tool("run_tests", "run_command", {"command": "git diff --no-ext-diff"},
                                     lambda: tools.run_command("git diff --no-ext-diff", min(10, budget.remaining_seconds())))
        if not status_observation.ok or not diff_observation.ok:
            raise ToolDenied("git evidence unavailable")
        diff_sha = hashlib.sha256(diff_observation.value.encode()).hexdigest()
        changed = [line[3:].strip() for line in status_observation.value.splitlines() if len(line) >= 4]
        trace_ids.append(emit("run_tests", "diff_observation",
                              {"attempt": label, "changed_files": changed, "diff_sha256": diff_sha,
                               "diff_summary": diff_observation.value[-500:]}))
        test_results["attempts"].append({"label": label, **results, "changed_files": changed,
                                          "diff_sha256": diff_sha})
        return results, trace_ids, diff_sha, status_observation.value

    try:
        # The unmodified fixture intentionally fails its target test. Its passing
        # regression command is the recoverability evidence for the clean base.
        budget.step()
        budget.tool()
        state = RewindCoderState(task_id=task.task_id, issue=task.issue,
                                requirements=list(task.explicit_requirements),
                                current_goal=task.issue, plan=[initial_action],
                                context_summary="Clean fixture base; target test is expected to fail before the task fix.",
                                budget_remaining=budget.remaining_seconds())
        checkpoint = manager.create(state, test_command=task.regression_commands[0],
                                    verified_requirements=("clean regression baseline",),
                                    timeout_seconds=min(20, budget.remaining_seconds()))
        recovery["checkpoint_id"] = checkpoint.checkpoint_id
        emit("create_checkpoint", "checkpoint_created",
             {"checkpoint_id": checkpoint.checkpoint_id, "workspace_root": checkpoint.workspace_root,
              "git_head": checkpoint.git_head, "test_evidence": checkpoint.test_status,
              "manifest_sha256": checkpoint.manifest_sha256})

        current_node = "repo_onboarding"
        budget.step()
        evidence_paths = {
            "demo-parser-001": ("src/parser.py", "tests/test_parser.py"),
            "tsv-whitespace-002": ("src/reader.py", "tests/test_reader.py"),
            "adapter-service-003": ("src/adapter.py", "src/service.py", "tests/test_service.py"),
        }[task.task_id]
        for path in evidence_paths:
            evidence[path] = call_tool(current_node, "read_file", {"path": path},
                                       lambda p=path: tools.read_file(p)).value
        current_node = "create_plan"
        budget.step()
        plan = _provider_call(provider.plan, budget, public_task, evidence)
        plan.validate()
        if not set(task.target_commands + task.regression_commands).issubset(set(plan.validation)):
            raise ValueError("plan lacks task validation commands")
        emit(current_node, "plan", {"action": initial_action, "files": list(plan.files),
                                    "validation": list(plan.validation)})

        current_node = "implement"
        budget.step()
        edits = _provider_call(provider.initial_edits, budget, public_task, evidence)
        for edit in edits:
            call_tool(current_node, "edit_file", {"path": edit.path, "action": initial_action,
                "old_sha256": hashlib.sha256(edit.old.encode()).hexdigest(),
                "new_sha256": hashlib.sha256(edit.new.encode()).hexdigest()},
                lambda e=edit: tools.edit_file(e.path, e.old, e.new))
        emit(current_node, "completed", {"action": initial_action, "changed_files": [e.path for e in edits]})

        fingerprint = None
        trace_ids: list[str] = []
        observations: dict[str, list[dict]] = {}
        for attempt in range(2):
            current_node = "run_tests"
            observations, trace_ids, diff_sha, status_text = run_tests(f"failed-{attempt + 1}")
            target_ok = all(item["passed"] for item in observations["target"])
            regression_ok = all(item["passed"] for item in observations["regression"])
            current_fingerprint = (target_ok, regression_ok, diff_sha)
            consecutive = 1 if fingerprint != current_fingerprint else 2
            fingerprint = current_fingerprint
            transient = any(item["exit_code"] == 124 for group in ("target", "regression")
                            for item in observations[group])
            changed_now = test_results["attempts"][-1]["changed_files"]
            unexpected = any(path not in plan.files for path in changed_now)
            signals = FailureSignals(consecutive_same_failure=consecutive,
                                     target_failure=not target_ok, test_regression=not regression_ok,
                                     no_progress_steps=2 if provider.scenario == "no_progress" and attempt else 0,
                                     transient_failure=transient, retries_used=attempt,
                                     unexpected_edit=unexpected, max_rewinds=task.budget.max_rewinds)
            kind = classify_failure(signals)
            decision = decide_recovery(signals)
            if variant == "forward_only":
                decision = RecoveryDecision.STOP
            elif variant == "retry_only":
                decision = RecoveryDecision.RETRY
            record = {"attempt": attempt + 1, "failure_type": kind.value,
                      "decision": decision.value, "consecutive_same_failure": consecutive,
                      "source_trace_ids": trace_ids}
            recovery["decisions"].append(record)
            emit("detect_failure", "recovery_decision", record)
            if target_ok and regression_ok:
                raise ValueError("failure injection did not fail")
            if variant in {"forward_only", "retry_only"}:
                if variant == "retry_only":
                    # Local correction on the damaged workspace; no checkpoint
                    # selection, repository rollback or rewind memory.
                    current_node = "retry"
                    budget.step()
                    corrections = _provider_call(provider.propose_edits, budget, public_task, evidence)
                    if len(corrections) != len(edits):
                        raise ValueError("retry edit count mismatch")
                    for failed, corrected in zip(edits, corrections):
                        if failed.path != corrected.path or failed.old != corrected.old:
                            raise ValueError("retry edit precondition mismatch")
                        call_tool(current_node, "edit_file", {"path": failed.path,
                            "action": "local_retry", "old_sha256": hashlib.sha256(failed.new.encode()).hexdigest(),
                            "new_sha256": hashlib.sha256(corrected.new.encode()).hexdigest()},
                            lambda f=failed, c=corrected: tools.edit_file(f.path, f.new, c.new))
                    observations, _, _, _ = run_tests("local-retry-final")
                changed = test_results["attempts"][-1]["changed_files"]
                target_final = bool(observations["target"]) and all(x["passed"] for x in observations["target"])
                regression_final = bool(observations["regression"]) and all(x["passed"] for x in observations["regression"])
                try:
                    hidden_final = evaluate_hidden(source.name, workspace)
                except Exception:
                    hidden_final = False
                forbidden_final = any(path.casefold() == prefix.rstrip("/").casefold() or
                    path.casefold().startswith(prefix.rstrip("/").casefold() + "/")
                    for path in changed for prefix in task.forbidden_paths)
                checked = verify(VerificationInput(target_final, regression_final, forbidden_final,
                    bool(changed) and hidden_final, False))
                failures = list(checked.failures)
                if not hidden_final:
                    failures.append("hidden acceptance failed")
                verifier_result = {"passed": checked.passed and not failures, "failures": failures,
                    "changed_files": changed, "base_commit": base_commit,
                    "target_tests_passed": target_final, "regression_tests_passed": regression_final,
                    "hidden_checks_passed": hidden_final, "forbidden_files_modified": forbidden_final}
                emit("verify", "verifier_result", verifier_result)
                status = RunStatus.PASS if verifier_result["passed"] else RunStatus.FAIL
                stop_reason = "; ".join(failures)
                raise EvaluationTerminal()
            if decision == RecoveryDecision.STOP:
                raise ValueError("recovery policy stopped: max_rewinds or unsafe failure")
            if decision == RecoveryDecision.DIAGNOSE:
                current_node = "diagnose_failure"
                budget.step()
                emit(current_node, "diagnosis", {"failure_type": kind.value,
                    "test_results": observations, "diff_sha256": diff_sha,
                    "changed_files": test_results["attempts"][-1]["changed_files"],
                    "tool_observation": status_text[-500:], "source_trace_ids": trace_ids})
                continue
            if decision == RecoveryDecision.RETRY:
                emit("retry", "bounded_retry", {"attempt": attempt + 1,
                                                  "source_trace_ids": trace_ids})
                continue
            if decision == RecoveryDecision.REWIND:
                break
            raise ValueError("unsupported recovery decision")
        else:
            raise ValueError("failure did not reach rewind threshold")

        current_node = "select_checkpoint"
        budget.step()
        selected = select_recoverable(manager)
        recovery["checkpoint_id"] = selected.checkpoint_id
        emit(current_node, "checkpoint_selected", {"checkpoint_id": selected.checkpoint_id,
             "git_head": selected.git_head, "manifest_sha256": selected.manifest_sha256})

        current_node = "restore"
        budget.step()
        budget.tool()
        granted = approval or ApprovalDecision(True, "fixture-policy", "automatic restore of reviewed disposable fixture")
        recovery["approval"] = {"approved": granted.approved, "approver": granted.approver,
                                "reason": granted.reason}
        emit(current_node, "approval", recovery["approval"])
        restore_result = manual_rewind(manager, selected.checkpoint_id, run_dir / "restored-state.json",
                                       granted, timeout_seconds=min(30, budget.remaining_seconds()),
                                       restore_agent_state=variant != "repository_only_rewind",
                                       restore_repository_state=variant != "agent_state_rewind",
                                       allow_fixture_ablation=variant in {"agent_state_rewind", "repository_only_rewind"})
        recovery["restore"] = {"conclusion": restore_result["conclusion"],
                               "reason": restore_result["reason"], "steps": restore_result["steps"],
                               "run_dir": restore_result["run_dir"]}
        emit(current_node, "aligned_restore", {"checkpoint_id": selected.checkpoint_id,
            **recovery["restore"]})
        if restore_result["conclusion"] != "PASS":
            raise ValueError(f"aligned restore failed: {restore_result['reason']}")
        restored_state = RewindCoderState.from_dict(json.loads((run_dir / "restored-state.json").read_text(encoding="utf-8")))
        if restored_state.current_checkpoint != selected.checkpoint_id:
            raise ValueError("restored agent checkpoint ID mismatch")

        current_node = "rewind_memory"
        memory = RewindMemory(failure_type=kind.value,
            failed_hypothesis=f"The action {initial_action} would satisfy the public tests.",
            evidence=tuple([f"{group}: {item['summary'][-300:]}" for group in ("target", "regression")
                            for item in observations[group]] + [f"git_diff_sha256:{diff_sha}" ]),
            failed_actions=(initial_action,), avoid_actions=(initial_action,),
            suggested_direction="Use public test evidence to fix the boundary while preserving regression behavior.",
            confidence=1.0, source_trace_ids=tuple(trace_ids))
        memory_data = json.loads(json.dumps(memory.to_dict()))
        if variant == "rewindcoder_full" or variant == "agent_state_rewind":
            recovery["memory"] = memory_data
        restored_state.rewind_count += 1
        if recovery["memory"] is not None:
            restored_state.rewind_memories.append(memory_data)
            emit(current_node, "memory_created", {"checkpoint_id": selected.checkpoint_id,
                                                   "memory": memory_data})

        current_node = "replan"
        budget.step()
        replan_context = memory_data if recovery["memory"] is not None else {"failure_type": kind.value}
        action, alternative, alternative_edits = _provider_call(provider.alternative_plan, budget,
                                                        public_task, evidence, replan_context)
        alternative.validate()
        if recovery["memory"] is not None:
            validate_alternative(action, memory)
        if action == initial_action or alternative.approach == plan.approach:
            raise ValueError("alternative plan repeats the failed core action")
        if not alternative_edits or tuple((item.path, item.old, item.new) for item in alternative_edits) == \
                tuple((item.path, item.old, item.new) for item in edits):
            raise ValueError("alternative plan repeats failed edit bytes")
        if not set(task.target_commands + task.regression_commands).issubset(set(alternative.validation)):
            raise ValueError("alternative plan lacks validation commands")
        recovery["alternative"] = {"action": action, "approach": alternative.approach,
                                    "files": list(alternative.files), "validation": list(alternative.validation)}
        restored_state.plan = [action]
        restored_state.current_step = 0
        emit(current_node, "alternative_plan", {"memory_source_trace_ids": list(memory.source_trace_ids) if recovery["memory"] is not None else [],
                                                 **recovery["alternative"]})

        current_node = "implement"
        budget.step()
        for edit in alternative_edits:
            call_tool(current_node, "edit_file", {"path": edit.path, "action": action,
                "old_sha256": hashlib.sha256(edit.old.encode()).hexdigest(),
                "new_sha256": hashlib.sha256(edit.new.encode()).hexdigest()},
                lambda e=edit: tools.edit_file(e.path, e.old, e.new))
        emit(current_node, "completed", {"action": action,
                                          "changed_files": [e.path for e in alternative_edits]})

        current_node = "verify"
        final_tests, final_trace_ids, final_diff_sha, status_text = run_tests("final")
        changed = test_results["attempts"][-1]["changed_files"]
        forbidden = any(path.casefold() == prefix.rstrip("/").casefold() or
                        path.casefold().startswith(prefix.rstrip("/").casefold() + "/")
                        for path in changed for prefix in task.forbidden_paths)
        target_passed = bool(final_tests["target"]) and all(item["passed"] for item in final_tests["target"])
        regression_passed = bool(final_tests["regression"]) and all(item["passed"] for item in final_tests["regression"])
        try:
            hidden_passed = evaluate_hidden(source.name, workspace)
        except Exception:
            hidden_passed = False
        restored_state.test_results = final_tests
        restored_state.changed_files = changed
        state_after_path = run_dir / "post-recovery-state.json"
        state_after_path.write_text(json.dumps(restored_state.to_dict(), ensure_ascii=False,
            indent=2) + "\n", encoding="utf-8")
        state_after = RewindCoderState.from_dict(json.loads(state_after_path.read_text(encoding="utf-8")))
        unexpected_final = any(path not in alternative.files for path in changed)
        aligned = (restore_result["conclusion"] == "PASS" and
                   all(item["passed"] for item in restore_result["steps"].values()) and
                   state_after.current_checkpoint == selected.checkpoint_id and
                    (state_after.rewind_memories[-1] == memory_data if recovery["memory"] is not None else not state_after.rewind_memories) and
                   state_after.plan == [action] and
                   git(workspace, "rev-parse", "HEAD").decode().strip() == selected.git_head)
        result = verify(VerificationInput(target_passed, regression_passed, forbidden,
                    bool(changed) and hidden_passed and aligned, unexpected_final))
        failures = list(result.failures)
        if not hidden_passed:
            failures.append("hidden acceptance failed")
        if not aligned:
            failures.append("checkpoint alignment failed")
        if unexpected_final:
            failures.append("unexpected edit outside alternative plan")
        verifier_result = {"passed": result.passed and not failures, "failures": failures,
            "changed_files": changed, "base_commit": base_commit, "checkpoint_id": selected.checkpoint_id,
            "agent_checkpoint_id": state_after.current_checkpoint,
            "agent_state_path": str(state_after_path),
            "restore_checks": restore_result["steps"], "git_diff_sha256": final_diff_sha,
            "target_tests_passed": target_passed, "regression_tests_passed": regression_passed,
            "hidden_checks_passed": hidden_passed, "forbidden_files_modified": forbidden,
            "security_rule_violated": unexpected_final, "source_trace_ids": final_trace_ids}
        emit(current_node, "verifier_result", verifier_result)
        status = RunStatus.PASS if verifier_result["passed"] else RunStatus.FAIL
        if status != RunStatus.PASS:
            stop_reason = "; ".join(failures)
    except EvaluationTerminal:
        pass
    except (BudgetExceeded, ToolDenied, TimeoutError, RuntimeError, ValueError, OSError) as error:
        stop_reason = str(error) if isinstance(error, (BudgetExceeded, ToolDenied, ValueError)) else type(error).__name__
        stop_kind = "budget_exhausted" if isinstance(error, BudgetExceeded) else (
            "security_violation" if isinstance(error, ToolDenied) else "recovery_stop")
        stop_decision = {"failure_type": stop_kind, "decision": RecoveryDecision.STOP.value,
                         "reason": stop_reason}
        recovery["decisions"].append(stop_decision)
        emit("detect_failure", "recovery_decision", stop_decision)
        emit("stop", "stopped", {"from_node": current_node, "reason": stop_reason})
    finally:
        patch_path = run_dir / "diff.patch"
        patch_path.write_text(_patch(source, workspace), encoding="utf-8", newline="\n")
        emit("final_review" if status == RunStatus.PASS else "stop", "run_finished",
             {"status": status.value, "reason": stop_reason, "verifier": verifier_result})
        manifest = make_run_manifest(run_id=run_id, task_id=task.task_id,
            rewindcoder_commit=_project_commit(), fixture_base_commit=base_commit,
            python_version=subprocess.sys.version.split()[0], execution_mode=ExecutionMode.LOCAL,
            test_commands=task.target_commands + task.regression_commands,
            test_results=test_results, status=status, provider=provider.name,
            provider_config=provider.public_config, seed=seed, budget=task.budget.to_dict(),
            usage=budget.usage(), verifier_result=verifier_result, stop_reason=stop_reason,
            patch_sha256=_hash(patch_path), workspace_head=base_commit,
            trace_sha256=_hash(trace_path), runner_source_sha256=_runner_source_hash(),
            task_sha256=_hash(task_path), recovery=recovery)
        (run_dir / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2,
             ensure_ascii=False) + "\n", encoding="utf-8")
    return {"run_id": run_id, "status": status.value, "verifier_result": verifier_result,
            "run_dir": str(run_dir), "stop_reason": stop_reason}
