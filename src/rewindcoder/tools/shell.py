"""Command adapter contract guarded by `tools.policy`."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class ShellTool(Protocol):
    def run(self, command: str, *, timeout_seconds: int) -> CommandResult: ...

