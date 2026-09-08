"""Git adapter contract; destructive operations require approval."""

from typing import Protocol


class GitTool(Protocol):
    def status(self) -> str: ...

    def diff(self) -> str: ...

    def head(self) -> str: ...

