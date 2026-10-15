"""Prepare disposable fixture Git repositories from reviewed source templates."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from rewindcoder.tools.policy import Permission, fixture_bootstrap_permission


FIXTURE_NAMES = ("parser-empty-name", "tsv-whitespace", "adapter-service")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "RewindCoder Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@rewindcoder.invalid",
    "GIT_COMMITTER_NAME": "RewindCoder Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@rewindcoder.invalid",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00",
}


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str, on_command: Callable[[str, str], None] | None = None) -> str:
    """Trusted fixture bootstrap only; agent commands use the tool policy."""
    command = "git " + " ".join(args)
    permission = fixture_bootstrap_permission(command)
    if permission != Permission.AUTO:
        raise ValueError("fixture bootstrap command policy denied")
    result = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"},
        capture_output=True, text=True, timeout=15, check=True,
    )
    if on_command:
        on_command(command, permission.value)
    return result.stdout.strip()


def prepare_fixture(source: Path, destination: Path, *, on_command: Callable[[str, str], None] | None = None) -> str:
    expected_root = (PROJECT_ROOT / "evals" / "fixtures").resolve(strict=True)
    output_root = (PROJECT_ROOT / "artifacts").resolve(strict=True)
    if source.is_symlink() or source.resolve(strict=True).parent != expected_root or source.name not in FIXTURE_NAMES or not source.is_dir():
        raise ValueError("unknown fixture template")
    if not destination.resolve().is_relative_to(output_root):
        raise ValueError("fixture destination must be under artifacts")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("fixture symlinks are forbidden")
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "fixture-manifest.json"))
    _git(destination, "init", "-q", "--initial-branch=main", on_command=on_command)
    _git(destination, "add", "--all", on_command=on_command)
    _git(destination, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture base", on_command=on_command)
    return _git(destination, "rev-parse", "HEAD", on_command=on_command)
