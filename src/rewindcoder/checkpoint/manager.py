"""Durable metadata store for aligned checkpoints.

Workspace capture/restore is intentionally an adapter boundary; a metadata file
alone must never be represented as a restorable repository snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

from .metadata import CheckpointMetadata


class CheckpointManager:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: CheckpointMetadata) -> Path:
        destination = self.storage_dir / f"{checkpoint.checkpoint_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def load(self, checkpoint_id: str) -> CheckpointMetadata:
        source = self.storage_dir / f"{checkpoint_id}.json"
        return CheckpointMetadata.from_dict(json.loads(source.read_text(encoding="utf-8")))

    def list_safe(self) -> list[CheckpointMetadata]:
        items = [
            CheckpointMetadata.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in self.storage_dir.glob("*.json")
        ]
        return [item for item in items if item.safe]

