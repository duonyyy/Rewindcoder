"""Filesystem adapter contract; implementation must enforce workspace scope."""

from pathlib import Path
from typing import Protocol


class FilesystemTool(Protocol):
    def read_text(self, path: Path) -> str: ...

    def write_text(self, path: Path, content: str) -> None: ...

