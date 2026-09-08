import json
import unittest

from rewindcoder.agent.state import RewindCoderState
from rewindcoder.checkpoint.metadata import CheckpointMetadata
from rewindcoder.recovery.detector import FailureSignals, RecoveryDecision, decide_recovery
from rewindcoder.recovery.executor import prepare_restore
from rewindcoder.recovery.selector import CheckpointScore, select_checkpoint
from rewindcoder.tools.policy import Permission, command_permission
from rewindcoder.verification.definition_of_done import VerificationInput
from rewindcoder.verification.verifier import verify


def checkpoint(checkpoint_id: str, *, safe: bool, risk_score: float = 0.2) -> CheckpointMetadata:
    state = RewindCoderState(task_id="task-1", issue="Fix parser").to_dict()
    return CheckpointMetadata(
        checkpoint_id=checkpoint_id,
        node="create_checkpoint",
        git_head="abc123",
        workspace_manifest={"src/parser.py": "sha256:example"},
        agent_state=state,
        test_status={"passed": 4, "failed": 0},
        verified_requirements=("R1",),
        safe=safe,
        risk_score=risk_score,
    )


class RecoveryCoreTests(unittest.TestCase):
    def test_checkpoint_serialization_preserves_both_state_domains(self) -> None:
        original = checkpoint("cp-1", safe=True)
        restored = CheckpointMetadata.from_dict(json.loads(json.dumps(original.to_dict())))
        self.assertEqual(restored.agent_state["task_id"], "task-1")
        self.assertEqual(restored.workspace_manifest["src/parser.py"], "sha256:example")

    def test_repeated_failure_rewinds_but_security_stops(self) -> None:
        self.assertEqual(
            decide_recovery(FailureSignals(consecutive_same_failure=3)),
            RecoveryDecision.REWIND,
        )
        self.assertEqual(
            decide_recovery(FailureSignals(security_violation=True)),
            RecoveryDecision.STOP,
        )

    def test_selector_rejects_unsafe_checkpoint(self) -> None:
        selected = select_checkpoint(
            [
                CheckpointScore(checkpoint("unsafe", safe=False), 1.0, 1.0, 0),
                CheckpointScore(checkpoint("safe", safe=True), 0.8, 1.0, 1),
            ]
        )
        self.assertEqual(selected.checkpoint_id, "safe")

    def test_restore_plan_requires_aligned_restore_and_approval(self) -> None:
        plan = prepare_restore(checkpoint("safe", safe=True))
        self.assertTrue(plan.restore_agent_state)
        self.assertTrue(plan.restore_repository_state)
        self.assertTrue(plan.requires_approval)

    def test_verifier_and_command_policy_are_conservative(self) -> None:
        result = verify(
            VerificationInput(True, True, False, True, False)
        )
        self.assertTrue(result.passed)
        self.assertEqual(command_permission("pytest tests/unit"), Permission.AUTO)
        self.assertEqual(command_permission("git reset --hard"), Permission.APPROVAL)
        self.assertEqual(command_permission("curl https://example.com"), Permission.DENY)
