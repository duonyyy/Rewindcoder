"""Plan an aligned restore; adapters execute only after approval."""

from dataclasses import dataclass

from rewindcoder.checkpoint.metadata import CheckpointMetadata


@dataclass(frozen=True, slots=True)
class RestorePlan:
    checkpoint_id: str
    restore_agent_state: bool
    restore_repository_state: bool
    requires_approval: bool
    post_restore_checks: tuple[str, ...]


def prepare_restore(checkpoint: CheckpointMetadata) -> RestorePlan:
    if not checkpoint.safe:
        raise ValueError("Unsafe checkpoints cannot be restored")
    return RestorePlan(
        checkpoint_id=checkpoint.checkpoint_id,
        restore_agent_state=True,
        restore_repository_state=True,
        requires_approval=True,
        post_restore_checks=("workspace manifest", "git diff", "target tests"),
    )

