"""Parsed, default-deny command policy for controlled repositories."""

from __future__ import annotations

import re
import shlex
from enum import StrEnum


class Permission(StrEnum):
    AUTO = "auto"
    APPROVAL = "approval"
    DENY = "deny"


_DANGEROUS_TOKENS = (";", "&", "|", "`", "$(", ">", "<", "\n", "\r")
_NETWORK_PROGRAMS = {"curl", "wget", "invoke-webrequest", "iwr", "ssh", "scp"}
_APPROVAL_PROGRAMS = {"rm", "del", "remove-item", "rmdir", "pip", "npm"}


def parse_command(command: str) -> list[str] | None:
    normalized = command.strip()
    if not normalized or any(token in normalized for token in _DANGEROUS_TOKENS):
        return None
    try:
        return shlex.split(normalized, posix=False)
    except ValueError:
        return None


def command_permission(command: str) -> Permission:
    """Classify a single command without executing it.

    Commands with chaining, network clients, unknown executables, or an
    ambiguous parse fail closed. The caller must still enforce workspace paths
    and timeouts before executing an AUTO command.
    """

    parts = parse_command(command)
    if not parts:
        return Permission.DENY
    program = parts[0].lower()
    if program in _NETWORK_PROGRAMS:
        return Permission.DENY
    if program in _APPROVAL_PROGRAMS:
        return Permission.APPROVAL
    if program == "git":
        if parts in (["git", "status"], ["git", "status", "--short"], ["git", "diff", "--no-ext-diff"], ["git", "rev-parse", "HEAD"]):
            return Permission.AUTO
        return Permission.APPROVAL if len(parts) > 1 else Permission.DENY
    if parts == ["pytest", "tests/unit"]:
        return Permission.AUTO
    if program == "python" and parts[1:3] == ["-m", "unittest"] and len(parts) == 4:
        if re.fullmatch(r"tests\.test_[a-z_]+\.[A-Za-z][A-Za-z0-9_]*", parts[3]):
            return Permission.AUTO
    if program == "rg" and len(parts) == 2 and not parts[1].startswith("-"):
        return Permission.AUTO
    if program == "rg" and len(parts) == 3 and not parts[1].startswith("-") and parts[2] in ("src", "tests"):
        return Permission.AUTO
    return Permission.DENY


def fixture_bootstrap_permission(command: str) -> Permission:
    """Allow only fixed Git setup commands in a disposable fixture workspace."""
    parts = parse_command(command)
    if parts in (
        ["git", "init", "-q", "--initial-branch=main"],
        ["git", "add", "--all"],
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture", "base"],
        ["git", "rev-parse", "HEAD"],
    ):
        return Permission.AUTO
    return Permission.DENY
