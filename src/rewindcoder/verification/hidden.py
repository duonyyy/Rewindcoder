"""Evaluator-only acceptance checks; never passed to a provider or tool workspace."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("rewindcoder_fixture_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("hidden check could not load fixture")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_hidden(fixture_name: str, workspace: Path) -> bool:
    if fixture_name == "parser-empty-name":
        parser = _load(workspace / "src/parser.py")
        try:
            parser.parse_name("\t")
        except ValueError:
            return True
        return False
    if fixture_name == "tsv-whitespace":
        reader = _load(workspace / "src/reader.py")
        return reader.read_rows("A\t\n", "\t") == [["A", ""]]
    if fixture_name == "adapter-service":
        adapter = _load(workspace / "src/adapter.py")
        try:
            adapter.normalize_amount(-3)
        except ValueError:
            return True
        return False
    raise ValueError("unknown fixture")
