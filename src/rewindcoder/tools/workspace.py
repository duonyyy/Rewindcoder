"""Workspace-scoped side effects for the forward-only fixture runner."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .policy import Permission, command_permission, parse_command


class ToolDenied(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Observation:
    ok: bool
    value: str
    exit_code: int | None = None


class WorkspaceTools:
    def __init__(self, root: Path, forbidden_paths: tuple[str, ...]) -> None:
        self.root = root.resolve(strict=True)
        self.forbidden_paths = tuple(path.replace("\\", "/").rstrip("/") for path in forbidden_paths)

    def _path(self, relative: str, *, edit: bool = False) -> Path:
        value = Path(relative)
        if value.is_absolute() or ".." in value.parts or not relative.strip():
            raise ToolDenied("path escapes workspace")
        candidate = self.root / value
        if any(part.is_symlink() for part in (candidate, *candidate.parents) if part != self.root):
            raise ToolDenied("symlink path denied")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise ToolDenied("path outside workspace or missing")
        rel = resolved.relative_to(self.root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or "evaluator_only" in rel:
            raise ToolDenied("internal path denied")
        if edit and any(rel == prefix or rel.startswith(prefix + "/") for prefix in self.forbidden_paths):
            raise ToolDenied("forbidden edit")
        return resolved

    def read_file(self, relative: str) -> Observation:
        path = self._path(relative)
        return Observation(True, path.read_text(encoding="utf-8"))

    def search(self, needle: str) -> Observation:
        if not needle or len(needle) > 200:
            raise ToolDenied("invalid search pattern")
        matches = []
        for base in ("src", "tests"):
            for path in sorted((self.root / base).rglob("*.py")):
                rel = path.relative_to(self.root).as_posix()
                content = self.read_file(rel).value
                for number, line in enumerate(content.splitlines(), 1):
                    if needle in line:
                        matches.append(f"{rel}:{number}:{line}")
        return Observation(True, "\n".join(matches[:100]))

    def edit_file(self, relative: str, old: str, new: str) -> Observation:
        path = self._path(relative, edit=True)
        content = path.read_text(encoding="utf-8")
        if not old or content.count(old) != 1 or old == new:
            raise ToolDenied("edit precondition failed")
        path.write_text(content.replace(old, new, 1), encoding="utf-8", newline="\n")
        return Observation(True, relative)

    def run_command(self, command: str, timeout_seconds: float) -> Observation:
        permission = command_permission(command)
        if permission != Permission.AUTO:
            raise ToolDenied(f"command {permission.value}")
        parts = parse_command(command)
        assert parts is not None
        if parts[0] == "python":
            parts[0] = sys.executable
        try:
            result = subprocess.run(
                parts, cwd=self.root, capture_output=True, text=True,
                timeout=max(0.01, timeout_seconds),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""},
            )
            return Observation(result.returncode == 0, (result.stdout + result.stderr)[-4000:], result.returncode)
        except subprocess.TimeoutExpired:
            return Observation(False, "command timeout", 124)
