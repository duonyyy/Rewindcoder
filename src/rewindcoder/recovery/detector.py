"""Use deterministic evidence before requesting an LLM diagnosis."""

from dataclasses import dataclass
from enum import StrEnum


class RecoveryDecision(StrEnum):
    RETRY = "retry"
    DIAGNOSE = "diagnose"
    REWIND = "rewind"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class FailureSignals:
    consecutive_same_failure: int = 0
    test_regression: bool = False
    no_progress_steps: int = 0
    unexpected_edit: bool = False
    security_violation: bool = False
    budget_exhausted: bool = False


def decide_recovery(signals: FailureSignals) -> RecoveryDecision:
    if signals.security_violation or signals.budget_exhausted:
        return RecoveryDecision.STOP
    if signals.unexpected_edit or signals.consecutive_same_failure >= 3:
        return RecoveryDecision.REWIND
    if signals.test_regression or signals.no_progress_steps >= 2:
        return RecoveryDecision.DIAGNOSE
    return RecoveryDecision.RETRY

