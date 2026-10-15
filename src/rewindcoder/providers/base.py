"""Provider responses are proposals; tools and verifier own side effects and PASS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Plan:
    goal: str
    files: tuple[str, ...]
    approach: str
    constraints: tuple[str, ...]
    validation: tuple[str, ...]

    def validate(self) -> None:
        if not self.goal or not self.files or not self.approach or not self.validation:
            raise ValueError("plan needs goal, files, approach and validation")


@dataclass(frozen=True, slots=True)
class EditProposal:
    path: str
    old: str
    new: str


class Provider(Protocol):
    name: str

    def clarify(self, task: dict, evidence: dict[str, str]) -> tuple[str, ...]: ...
    def plan(self, task: dict, evidence: dict[str, str]) -> Plan: ...
    def propose_edits(self, task: dict, evidence: dict[str, str]) -> tuple[EditProposal, ...]: ...
