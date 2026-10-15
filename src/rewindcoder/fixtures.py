"""Prepare disposable fixture Git repositories from reviewed source templates."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


FIXTURE_NAMES = ("parser-empty-name", "tsv-whitespace", "adapter-service")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "RewindCoder Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@rewindcoder.invalid",
    "GIT_COMMITTER_NAME": "RewindCoder Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@rewindcoder.invalid",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00",
}


def _git(root: Path, *args: str) -> str:
    """Trusted fixture bootstrap only; agent commands use the tool policy."""
    result = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV},
        capture_output=True, text=True, timeout=15, check=True,
    )
    return result.stdout.strip()


def prepare_fixture(source: Path, destination: Path) -> str:
    if source.name not in FIXTURE_NAMES or not source.is_dir():
        raise ValueError("unknown fixture template")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("fixture symlinks are forbidden")
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "fixture-manifest.json"))
    _git(destination, "init", "-q", "--initial-branch=main")
    _git(destination, "add", "--all")
    _git(destination, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture base")
    return _git(destination, "rev-parse", "HEAD")
