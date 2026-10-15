"""Bounded forward-only coding workflow over disposable fixture repositories."""

from __future__ import annotations

import difflib
import hashlib
import json
import queue
import subprocess
import threading
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from rewindcoder.contracts.manifest import ExecutionMode, RunStatus, make_run_manifest
from rewindcoder.contracts.task import TaskContract
from rewindcoder.fixtures import FIXTURE_NAMES, prepare_fixture
from rewindcoder.observability.trace import JsonlTrace
from rewindcoder.providers.base import Provider
from rewindcoder.runtime.budget import BudgetExceeded, BudgetMeter
from rewindcoder.tools.policy import Permission, command_permission
from rewindcoder.tools.workspace import Observation, ToolDenied, WorkspaceTools
from rewindcoder.verification.definition_of_done import VerificationInput
from rewindcoder.verification.hidden import evaluate_hidden
from rewindcoder.verification.verifier import verify
from rewindcoder.security.approval import ApprovalDecision


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class WorkflowNode(StrEnum):
    PARSE_ISSUE = "parse_issue"
    CLARIFY_REQUIREMENTS = "clarify_requirements"
    REPO_ONBOARDING = "repo_onboarding"
    CREATE_PLAN = "create_plan"
    IMPLEMENT = "implement"
    RUN_TARGET_TESTS = "run_target_tests"
    RUN_REGRESSION_TESTS = "run_regression_tests"
    VERIFY = "verify"
    FINAL_REVIEW = "final_review"
    STOP = "stop"
    # Reserved names retained for the later recovery phases; run_task never visits them.
    CREATE_CHECKPOINT = "create_checkpoint"
    DIAGNOSE_FAILURE = "diagnose_failure"
    SELECT_CHECKPOINT = "select_checkpoint"
    RESTORE = "restore"
    REPLAN = "replan"
    END = "end"


def next_after_verification(*, passed: bool, should_rewind: bool) -> WorkflowNode:
    if passed:
        return WorkflowNode.FINAL_REVIEW
    return WorkflowNode.SELECT_CHECKPOINT if should_rewind else WorkflowNode.DIAGNOSE_FAILURE


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runner_source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((PROJECT_ROOT / "src/rewindcoder").rglob("*.py")):
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _patch(source: Path, workspace: Path) -> str:
    result = []
    for original in sorted(source.rglob("*")):
        if not original.is_file() or original.name == "fixture-manifest.json":
            continue
        relative = original.relative_to(source)
        current = workspace / relative
        if not current.is_file():
            continue
        before = original.read_text(encoding="utf-8").splitlines(keepends=True)
        after = current.read_text(encoding="utf-8").splitlines(keepends=True)
        result.extend(difflib.unified_diff(before, after, fromfile=f"a/{relative.as_posix()}", tofile=f"b/{relative.as_posix()}"))
    return "".join(result)


def _provider_call(fn: Callable, budget: BudgetMeter, *args: Any) -> Any:
    budget.charge_text(json.dumps(args, ensure_ascii=False, default=str))
    channel: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def execute() -> None:
        try:
            channel.put((True, fn(*args)))
        except Exception as error:
            channel.put((False, error))

    threading.Thread(target=execute, daemon=True).start()
    try:
        ok, value = channel.get(timeout=budget.remaining_seconds())
    except queue.Empty as error:
        raise BudgetExceeded("provider_timeout") from error
    if not ok:
        raise value
    budget.charge_text(json.dumps(value, ensure_ascii=False, default=str))
    return value


def _project_commit() -> str:
    command = "git rev-parse HEAD"
    if command_permission(command) != Permission.AUTO:
        raise ToolDenied("metadata command denied")
    return subprocess.run(command.split(), cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10, check=True).stdout.strip()


def run_task(task_path: Path, output_base: Path, provider: Provider, *, seed: int = 0,
             recovery: bool = False, approval: ApprovalDecision | None = None,
             variant: str = "rewindcoder_full") -> dict[str, Any]:
    """Run one reviewed fixture; recovery is an explicit bounded workflow branch."""
    task = TaskContract.from_dict(json.loads(task_path.read_text(encoding="utf-8")))
    if task.repository.kind != "fixture":
        raise ValueError("Phase 2 accepts controlled fixtures only")
    source = (PROJECT_ROOT / task.repository.path).resolve(strict=True)
    fixture_root = (PROJECT_ROOT / "evals" / "fixtures").resolve(strict=True)
    if source.parent != fixture_root or source.name not in FIXTURE_NAMES:
        raise ValueError("task repository is not a controlled fixture")
    output_base = output_base.resolve()
    allowed_outputs = (PROJECT_ROOT / "artifacts", PROJECT_ROOT / "evals/baselines/forward_only",
                       PROJECT_ROOT / "evals/results/self_recovery", PROJECT_ROOT / "evals/results/raw")
    if not any(output_base == root or output_base.is_relative_to(root) for root in allowed_outputs):
        raise ValueError("output must be under artifacts or evals/baselines/forward_only")
    if recovery:
        from rewindcoder.recovery.workflow import run_recovery_task
        return run_recovery_task(task_path, output_base, task, source, provider,
                                 seed=seed, approval=approval, variant=variant)
    run_id = f"run-{uuid.uuid4().hex}"
    run_dir = output_base / task.task_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    workspace = PROJECT_ROOT / "artifacts" / "runs" / run_id
    workspace.parent.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.jsonl"
    trace = JsonlTrace(trace_path)
    provider_config = getattr(provider, "public_config", {})
    trace.emit(run_id=run_id, task_id=task.task_id, node="run", event="run_started", details={"provider": provider.name, "provider_config": provider_config, "seed": seed})
    base_commit = prepare_fixture(
        source, workspace,
        on_command=lambda command, permission: trace.emit(
            run_id=run_id, task_id=task.task_id, node="fixture_bootstrap",
            event="command", details={"command": command, "permission": permission, "scope": "disposable_fixture"},
        ),
    )
    if base_commit != task.repository.base_commit:
        raise ValueError("fixture base_commit mismatch")
    patch_path = run_dir / "diff.patch"
    manifest_path = run_dir / "manifest.json"
    public_task = task.to_agent_payload()
    tools = WorkspaceTools(workspace, task.forbidden_paths)
    budget = BudgetMeter(task.budget)
    test_results: dict[str, Any] = {"target": [], "regression": []}
    verifier_result: dict[str, Any] = {"passed": False, "failures": ["verification not run"]}
    stop_reason = ""
    current_node = WorkflowNode.PARSE_ISSUE
    status = RunStatus.NOT_READY
    evidence: dict[str, str] = {}
    edit_paths: list[str] = []

    def emit(node: WorkflowNode, event: str, details: dict[str, Any]) -> None:
        trace.emit(run_id=run_id, task_id=task.task_id, node=node.value, event=event, details=details)

    def tool_call(node: WorkflowNode, name: str, details: dict[str, Any], fn: Callable[[], Observation]) -> Observation:
        budget.tool()
        emit(node, "tool_call", {"tool": name, **details})
        try:
            result = fn()
        except ToolDenied as error:
            emit(node, "tool_result", {"tool": name, "ok": False, "reason": str(error)})
            raise
        except Exception as error:
            reason = f"tool_error:{type(error).__name__}"
            emit(node, "tool_result", {"tool": name, "ok": False, "reason": reason})
            raise ToolDenied(reason) from error
        emit(node, "tool_result", {"tool": name, "ok": result.ok, "exit_code": result.exit_code, "size": len(result.value)})
        return result

    def start(node: WorkflowNode) -> None:
        nonlocal current_node
        current_node = node
        budget.step()
        emit(node, "started", {})

    try:
        start(WorkflowNode.PARSE_ISSUE)
        emit(current_node, "completed", {"issue_length": len(task.issue)})

        start(WorkflowNode.CLARIFY_REQUIREMENTS)
        clarified = _provider_call(provider.clarify, budget, public_task, evidence)
        if not clarified:
            raise ValueError("empty clarified requirements")
        emit(current_node, "completed", {"requirements": list(clarified)})

        start(WorkflowNode.REPO_ONBOARDING)
        for needle in ("def ", "test_"):
            found = tool_call(current_node, "search", {"needle": needle}, lambda n=needle: tools.search(n))
            for line in found.value.splitlines():
                path = line.split(":", 1)[0]
                if path not in evidence:
                    evidence[path] = tool_call(current_node, "read_file", {"path": path}, lambda p=path: tools.read_file(p)).value
        if not evidence:
            raise ValueError("no repository evidence")
        emit(current_node, "completed", {"files": sorted(evidence)})

        start(WorkflowNode.CREATE_PLAN)
        plan = _provider_call(provider.plan, budget, public_task, evidence)
        plan.validate()
        if not set(task.target_commands + task.regression_commands).issubset(set(plan.validation)):
            raise ValueError("plan lacks task validation commands")
        emit(current_node, "completed", {"goal": plan.goal, "files": list(plan.files), "validation": list(plan.validation)})

        start(WorkflowNode.IMPLEMENT)
        edits = _provider_call(provider.propose_edits, budget, public_task, evidence)
        if not edits:
            raise ValueError("provider proposed no edits")
        for edit in edits:
            tool_call(current_node, "edit_file", {"path": edit.path, "old_sha256": hashlib.sha256(edit.old.encode()).hexdigest(), "new_sha256": hashlib.sha256(edit.new.encode()).hexdigest()}, lambda e=edit: tools.edit_file(e.path, e.old, e.new))
            edit_paths.append(edit.path)
        emit(current_node, "completed", {"changed_files": edit_paths})

        for node, commands, key in (
            (WorkflowNode.RUN_TARGET_TESTS, task.target_commands, "target"),
            (WorkflowNode.RUN_REGRESSION_TESTS, task.regression_commands, "regression"),
        ):
            start(node)
            for command in commands:
                result = tool_call(node, "run_command", {"command": command, "permission": command_permission(command).value}, lambda c=command: tools.run_command(c, min(20, budget.remaining_seconds())))
                test_results[key].append({"command": command, "passed": result.ok, "exit_code": result.exit_code, "summary": result.value[-500:]})
            emit(node, "completed", {"passed": all(item["passed"] for item in test_results[key])})

        start(WorkflowNode.VERIFY)
        status_output = tool_call(current_node, "run_command", {"command": "git status --short", "permission": "auto"}, lambda: tools.run_command("git status --short", min(10, budget.remaining_seconds())))
        diff_output = tool_call(current_node, "run_command", {"command": "git diff --no-ext-diff", "permission": "auto"}, lambda: tools.run_command("git diff --no-ext-diff", min(10, budget.remaining_seconds())))
        changed = [line[3:].strip() for line in status_output.value.splitlines() if len(line) >= 4]
        forbidden = any(path.casefold() == prefix.rstrip("/").casefold() or path.casefold().startswith(prefix.rstrip("/").casefold() + "/") for path in changed for prefix in task.forbidden_paths)
        target_passed = bool(test_results["target"]) and all(item["passed"] for item in test_results["target"])
        regression_passed = bool(test_results["regression"]) and all(item["passed"] for item in test_results["regression"])
        try:
            hidden_passed = evaluate_hidden(source.name, workspace)
        except Exception:
            hidden_passed = False
        result = verify(VerificationInput(target_passed, regression_passed, forbidden, bool(changed) and target_passed and regression_passed and hidden_passed, False))
        failures = list(result.failures)
        if not hidden_passed:
            failures.append("hidden acceptance failed")
        if not status_output.ok or not diff_output.ok:
            failures.append("git evidence unavailable")
        verifier_result = {"passed": result.passed and not failures, "failures": failures, "changed_files": changed, "base_commit": base_commit, "target_tests_passed": target_passed, "regression_tests_passed": regression_passed, "hidden_checks_passed": hidden_passed}
        emit(current_node, "verifier_result", verifier_result)
        status = RunStatus.PASS if verifier_result["passed"] else RunStatus.FAIL

        start(WorkflowNode.FINAL_REVIEW if verifier_result["passed"] else WorkflowNode.STOP)
        emit(current_node, "completed", {"status": status.value})
    except (BudgetExceeded, ToolDenied, TimeoutError, RuntimeError, ValueError, OSError) as error:
        stop_reason = str(error) if isinstance(error, (BudgetExceeded, ToolDenied)) else type(error).__name__
        status = RunStatus.NOT_READY
        emit(WorkflowNode.STOP, "stopped", {"from_node": current_node.value, "reason": stop_reason})
    finally:
        patch_path.write_text(_patch(source, workspace), encoding="utf-8", newline="\n")
        emit(WorkflowNode.STOP if status != RunStatus.PASS else WorkflowNode.FINAL_REVIEW, "run_finished", {"status": status.value, "verifier": verifier_result})
        manifest = make_run_manifest(
            run_id=run_id, task_id=task.task_id, rewindcoder_commit=_project_commit(),
            fixture_base_commit=base_commit, python_version=subprocess.sys.version.split()[0],
            execution_mode=ExecutionMode.LOCAL, test_commands=task.target_commands + task.regression_commands,
            test_results=test_results, status=status, provider=provider.name, provider_config=provider_config, seed=seed,
            budget=task.budget.to_dict(), usage=budget.usage(), verifier_result=verifier_result,
            stop_reason=stop_reason, patch_sha256=_hash(patch_path), workspace_head=base_commit,
            trace_sha256=_hash(trace_path), runner_source_sha256=_runner_source_hash(),
            task_sha256=_hash(task_path),
        )
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"run_id": run_id, "status": status.value, "verifier_result": verifier_result, "run_dir": str(run_dir)}
