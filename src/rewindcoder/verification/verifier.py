"""Return a reviewable result rather than a bare pass/fail flag."""

from dataclasses import dataclass

from .definition_of_done import VerificationInput, definition_of_done


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    failures: tuple[str, ...]


def verify(value: VerificationInput) -> VerificationResult:
    checks = {
        "target tests failed": value.target_tests_passed,
        "regression tests failed": value.regression_tests_passed,
        "forbidden file modified": not value.forbidden_files_modified,
        "requirements not satisfied": value.requirements_satisfied,
        "security rule violated": not value.security_rule_violated,
    }
    failures = tuple(message for message, passed in checks.items() if not passed)
    return VerificationResult(definition_of_done(value), failures)

