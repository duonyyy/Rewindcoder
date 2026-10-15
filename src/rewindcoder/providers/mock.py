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
