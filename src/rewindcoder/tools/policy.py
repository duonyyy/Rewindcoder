"""A narrow command policy for controlled repositories."""

from enum import StrEnum


class Permission(StrEnum):
    AUTO = "auto"
    APPROVAL = "approval"
    DENY = "deny"


AUTO_COMMANDS = {"pytest", "python", "rg", "git diff", "git status"}
APPROVAL_PREFIXES = {"pip install", "git reset", "rm", "del", "git push"}


def command_permission(command: str) -> Permission:
    normalized = command.strip().lower()
    if any(normalized.startswith(prefix) for prefix in APPROVAL_PREFIXES):
        return Permission.APPROVAL
    if any(normalized == item or normalized.startswith(f"{item} ") for item in AUTO_COMMANDS):
        return Permission.AUTO
    return Permission.DENY

