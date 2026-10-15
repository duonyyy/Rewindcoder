import unittest

from rewindcoder.recovery.detector import (
    FailureSignals, FailureType, RecoveryDecision, classify_failure, decide_recovery,
)
from rewindcoder.recovery.memory import RewindMemory, validate_alternative


class Phase4PolicyTests(unittest.TestCase):
    def test_failure_taxonomy_and_priority(self):
        cases = (
            (FailureSignals(security_violation=True, target_failure=True), FailureType.SECURITY, RecoveryDecision.STOP),
            (FailureSignals(budget_exhausted=True, test_regression=True), FailureType.BUDGET, RecoveryDecision.STOP),
            (FailureSignals(elapsed_timeout=True), FailureType.BUDGET, RecoveryDecision.STOP),
            (FailureSignals(unexpected_edit=True), FailureType.UNEXPECTED_EDIT, RecoveryDecision.STOP),
            (FailureSignals(test_regression=True), FailureType.REGRESSION, RecoveryDecision.DIAGNOSE),
            (FailureSignals(target_failure=True), FailureType.TARGET, RecoveryDecision.DIAGNOSE),
            (FailureSignals(no_progress_steps=2), FailureType.NO_PROGRESS, RecoveryDecision.DIAGNOSE),
            (FailureSignals(transient_failure=True), FailureType.TRANSIENT, RecoveryDecision.RETRY),
        )
        for signals, kind, decision in cases:
            with self.subTest(kind=kind):
                self.assertEqual(classify_failure(signals), kind)
                self.assertEqual(decide_recovery(signals), decision)

    def test_repetition_retry_and_rewind_bounds(self):
        self.assertEqual(decide_recovery(FailureSignals(target_failure=True,
            consecutive_same_failure=1)), RecoveryDecision.DIAGNOSE)
        self.assertEqual(decide_recovery(FailureSignals(target_failure=True,
            consecutive_same_failure=2)), RecoveryDecision.REWIND)
        self.assertEqual(decide_recovery(FailureSignals(target_failure=True,
            consecutive_same_failure=2, max_rewinds=0)), RecoveryDecision.STOP)
        self.assertEqual(decide_recovery(FailureSignals(transient_failure=True,
            retries_used=1)), RecoveryDecision.STOP)

    def test_memory_requires_evidence_and_alternative_core_action(self):
        memory = RewindMemory("target_failure", "raw value suffices", ("target exit 1",),
                              ("return_raw",), ("return_raw",), "validate stripped name", 0.8,
                              ("event-0012",))
        self.assertEqual(memory.to_dict()["source_trace_ids"], ("event-0012",))
        with self.assertRaisesRegex(ValueError, "avoid_action"):
            validate_alternative("return_raw", memory)
        validate_alternative("validate_then_return", memory)
        with self.assertRaises(ValueError):
            RewindMemory("target_failure", "raw value suffices", (), ("return_raw",),
                         ("return_raw",), "change", 0.8, ("event-1",))
        with self.assertRaises(ValueError):
            RewindMemory("target_failure", "raw value suffices", ("target exit 1",),
                         ("return_raw",), ("return_raw",), "change", 1.1, ("event-1",))
