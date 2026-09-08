"""Adapter contract for repository snapshot capture and restoration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    checkpoint_id: str
    git_head: str | None
    manifest: dict[str, str]
    archive_path: Path | None


class RepositorySnapshotAdapter(Protocol):
    def capture(self, checkpoint_id: str) -> RepositorySnapshot: ...

    def restore(self, snapshot: RepositorySnapshot) -> None: ...

