"""Deterministic recovery taxonomy and bounded decision policy."""

from dataclasses import dataclass
from enum import StrEnum


class RecoveryDecision(StrEnum):
    RETRY = "retry"
    DIAGNOSE = "diagnose"
    REWIND = "rewind"
    STOP = "stop"


class FailureType(StrEnum):
    SECURITY = "security_violation"
    BUDGET = "budget_exhausted"
    UNEXPECTED_EDIT = "unexpected_edit"
    TRANSIENT = "transient_failure"
    TARGET = "target_failure"
    REGRESSION = "regression_failure"
    NO_PROGRESS = "no_progress"
    UNKNOWN = "unknown_failure"


@dataclass(frozen=True, slots=True)
class FailureSignals:
    consecutive_same_failure: int = 0
    test_regression: bool = False
    no_progress_steps: int = 0
    unexpected_edit: bool = False
    security_violation: bool = False
    budget_exhausted: bool = False
    target_failure: bool = False
    transient_failure: bool = False
    retries_used: int = 0
    rewinds_used: int = 0
    max_retries: int = 1
    max_rewinds: int = 1
    elapsed_timeout: bool = False


def classify_failure(signals: FailureSignals) -> FailureType:
    if signals.security_violation:
        return FailureType.SECURITY
    if signals.budget_exhausted or signals.elapsed_timeout:
        return FailureType.BUDGET
    if signals.unexpected_edit:
        return FailureType.UNEXPECTED_EDIT
    if signals.transient_failure:
        return FailureType.TRANSIENT
    if signals.test_regression:
        return FailureType.REGRESSION
    if signals.no_progress_steps >= 2:
        return FailureType.NO_PROGRESS
    if signals.target_failure:
        return FailureType.TARGET
    return FailureType.UNKNOWN


def decide_recovery(signals: FailureSignals) -> RecoveryDecision:
    kind = classify_failure(signals)
    if kind in (FailureType.SECURITY, FailureType.BUDGET, FailureType.UNEXPECTED_EDIT):
        return RecoveryDecision.STOP
    if kind == FailureType.TRANSIENT:
        return RecoveryDecision.RETRY if signals.retries_used < signals.max_retries else RecoveryDecision.STOP
    if signals.consecutive_same_failure >= 2:
        return RecoveryDecision.REWIND if signals.rewinds_used < signals.max_rewinds else RecoveryDecision.STOP
    if kind in (FailureType.TARGET, FailureType.REGRESSION, FailureType.NO_PROGRESS):
        return RecoveryDecision.DIAGNOSE
    return RecoveryDecision.STOP

