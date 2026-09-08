"""Test-runner adapter contract."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TestResult:
    passed: bool
    command: str
    summary: str


class TestTool(Protocol):
    def run_target(self) -> TestResult: ...

    def run_regression(self) -> TestResult: ...

