"""Optional trusted provider plugin selected by environment, with no server built in."""

from __future__ import annotations

import importlib
import os

from .mock import MockProvider


def create_provider():
    selected = os.environ.get("REWINDCODER_PROVIDER", "mock")
    if selected == "mock":
        return MockProvider(os.environ.get("REWINDCODER_MOCK_SCENARIO", "success"))
    if selected == "external":
        module_name = os.environ.get("REWINDCODER_PROVIDER_MODULE", "")
        if not module_name or not module_name.startswith("rewindcoder_external_"):
            raise ValueError("external provider requires a trusted REWINDCODER_PROVIDER_MODULE")
        return importlib.import_module(module_name).create_provider()
    raise ValueError(f"unsupported provider: {selected}")
