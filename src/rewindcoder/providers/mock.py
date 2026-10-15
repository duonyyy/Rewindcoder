"""Scripted deterministic fixture provider for offline harness tests.

This provider is deliberately limited to three known fixtures. It demonstrates
the workflow and tool boundaries, not general coding ability.
"""

from __future__ import annotations

from .base import EditProposal, Plan


class MockProvider:
    name = "mock"

    def __init__(self, scenario: str = "success") -> None:
        self.scenario = scenario
        self.public_config = {"scenario": scenario}

    def _check(self) -> None:
        if self.scenario == "error":
            raise RuntimeError("mock provider error")
        if self.scenario == "timeout":
            raise TimeoutError("mock provider timeout")

    def clarify(self, task: dict, evidence: dict[str, str]) -> tuple[str, ...]:
        self._check()
        return (
            f"Intent: {task['issue']}",
            "Technical context: inspect source and public tests in the fixture.",
            "Interface: preserve existing callable names and signatures.",
            "Structure: modify source files only; retain repository conventions.",
            "Data semantics: honor boundary cases shown by public tests.",
            "Constraints and validation: run target and regression commands.",
        )

    def plan(self, task: dict, evidence: dict[str, str]) -> Plan:
        self._check()
        edits = self.propose_edits(task, evidence)
        plan = Plan(
            goal=task["issue"],
            files=tuple(edit.path for edit in edits),
            approach="Apply one scoped source change from public issue and tests.",
            constraints=tuple(task["forbidden_paths"]),
            validation=tuple(task["target_commands"] + task["regression_commands"]),
        )
        plan.validate()
        return plan

    def propose_edits(self, task: dict, evidence: dict[str, str]) -> tuple[EditProposal, ...]:
        self._check()
        task_id = task["task_id"]
        if task_id == "demo-parser-001":
            return (EditProposal(
                "src/parser.py", "    return value.strip()",
                "    name = value.strip()\n    if not name:\n        raise ValueError(\"name must not be empty\")\n    return name",
            ),)
        if task_id == "tsv-whitespace-002":
            return (EditProposal(
                "src/reader.py", "    return [[cell.strip() for cell in row] for row in rows]",
                "    return rows if delimiter == \"\\t\" else [[cell.strip() for cell in row] for row in rows]",
            ),)
        if task_id == "adapter-service-003":
            return (EditProposal(
                "src/adapter.py", "    return value",
                "    if value < 0:\n        raise ValueError(\"negative amount\")\n    return value",
            ),)
        raise ValueError(f"mock provider has no script for {task_id}")


class RecoveryMockProvider(MockProvider):
    """Offline fault injection with a distinct recovery action per scenario."""

    def __init__(self, scenario: str) -> None:
        if scenario not in {"target_failure", "regression_failure", "no_progress"}:
            raise ValueError("unknown recovery fixture scenario")
        super().__init__(scenario)

    def initial_action(self, task_id: str = "demo-parser-001") -> str:
        if task_id == "tsv-whitespace-002":
            return "retain_tsv_trimming"
        if task_id == "adapter-service-003":
            return "retain_negative_amounts"
        return {
            "target_failure": "return_raw_name",
            "regression_failure": "replace_valid_name_with_constant",
            "no_progress": "annotate_unchanged_behavior",
        }[self.scenario]

    def plan(self, task: dict, evidence: dict[str, str]) -> Plan:
        edits = self.initial_edits(task, evidence)
        plan = Plan(task["issue"], tuple(edit.path for edit in edits), self.initial_action(task["task_id"]),
                    tuple(task["forbidden_paths"]),
                    tuple(task["target_commands"] + task["regression_commands"]))
        plan.validate()
        return plan

    def initial_edits(self, task: dict, evidence: dict[str, str]) -> tuple[EditProposal, ...]:
        if task["task_id"] == "tsv-whitespace-002":
            return (EditProposal("src/reader.py",
                "    return [[cell.strip() for cell in row] for row in rows]",
                "    return [[cell.strip() for cell in row] for row in rows]  # faulty TSV behavior"),)
        if task["task_id"] == "adapter-service-003":
            return (EditProposal("src/adapter.py", "    return value",
                                  "    return int(value)  # faulty negative-amount behavior"),)
        if task["task_id"] != "demo-parser-001":
            raise ValueError("recovery mock has no script for task")
        old = "    return value.strip()"
        new = {
            "target_failure": "    return value.strip() if value.strip() else value",
            "regression_failure": "    name = value.strip()\n    if not name:\n        raise ValueError(\"empty\")\n    return \"wrong\"",
            "no_progress": "    return value.strip()  # no behavior change",
        }[self.scenario]
        return (EditProposal("src/parser.py", old, new),)

    def alternative_plan(self, task: dict, evidence: dict[str, str], memory: dict) -> tuple[str, Plan, tuple[EditProposal, ...]]:
        if memory["failure_type"] not in {"target_failure", "regression_failure", "no_progress"}:
            raise ValueError("unsupported recovery memory")
        action = {
            "demo-parser-001": "validate_stripped_name_then_return_it",
            "tsv-whitespace-002": "preserve_tsv_cells_and_trim_csv",
            "adapter-service-003": "reject_negative_at_adapter_boundary",
        }[task["task_id"]]
        edits = super().propose_edits(task, evidence)
        plan = Plan(task["issue"], tuple(edit.path for edit in edits), action,
                    tuple(task["forbidden_paths"]),
                    tuple(task["target_commands"] + task["regression_commands"]))
        plan.validate()
        return action, plan, edits
