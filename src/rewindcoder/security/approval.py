"""Represent a human decision as traceable data."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    approved: bool
    approver: str | None
    reason: str

