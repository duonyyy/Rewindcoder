"""Read-only issue adapter contract for the MVP."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Issue:
    identifier: str
    title: str
    body: str


class IssueTool(Protocol):
    def get_issue(self, identifier: str) -> Issue: ...

