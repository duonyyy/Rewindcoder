"""Small standard-library validators shared by versioned contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ContractValidationError(ValueError):
    """Raised when external data violates a RewindCoder contract."""


_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "authorization",
    "password",
    "private_key",
    "secret",
)
_SENSITIVE_VALUE_PREFIXES = ("sk-", "ghp_", "github_pat_", "bearer ")


def require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field_name} must be an object")
    return value


def require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    return value


def require_string_list(value: Any, field_name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        suffix = "a non-empty list" if not allow_empty else "a list"
        raise ContractValidationError(f"{field_name} must be {suffix} of strings")
    for index, item in enumerate(value):
        require_non_empty_string(item, f"{field_name}[{index}]")
    return value


def reject_unknown_fields(raw: Mapping[str, Any], allowed: set[str], field_name: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ContractValidationError(f"{field_name} contains unknown fields: {', '.join(unknown)}")


def ensure_no_sensitive_data(value: Any, field_name: str = "payload") -> None:
    """Reject secrets and .env references before they reach logs or manifests."""

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_name = str(key).lower()
            if any(marker in key_name for marker in _SENSITIVE_KEY_MARKERS):
                raise ContractValidationError(f"{field_name}.{key} may not contain sensitive data")
            ensure_no_sensitive_data(nested_value, f"{field_name}.{key}")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_no_sensitive_data(item, f"{field_name}[{index}]")
        return

    if isinstance(value, str):
        normalized = value.strip().lower().replace("\\", "/")
        if normalized == ".env" or normalized.endswith("/.env"):
            raise ContractValidationError(f"{field_name} may not reference a .env file")
        if normalized.startswith(_SENSITIVE_VALUE_PREFIXES):
            raise ContractValidationError(f"{field_name} may not contain a credential-like value")
