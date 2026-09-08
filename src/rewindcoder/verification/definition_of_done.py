"""Deterministic definition-of-done checks for a task."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationInput:
    target_tests_passed: bool
    regression_tests_passed: bool
    forbidden_files_modified: bool
    requirements_satisfied: bool
    security_rule_violated: bool


def definition_of_done(value: VerificationInput) -> bool:
    return (
        value.target_tests_passed
        and value.regression_tests_passed
        and not value.forbidden_files_modified
        and value.requirements_satisfied
        and not value.security_rule_violated
    )

