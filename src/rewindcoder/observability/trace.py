"""Append validated, versioned execution events to a local JSONL trace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rewindcoder.contracts.trace import TraceEvent, make_trace_event


class JsonlTrace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self, *, run_id: str, task_id: str, node: str, event: str, details: dict[str, Any]
    ) -> TraceEvent:
        payload = make_trace_event(
            run_id=run_id,
            task_id=task_id,
            node=node,
            event=event,
            details=details,
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload.to_dict(), ensure_ascii=False) + "\n")
        return payload
