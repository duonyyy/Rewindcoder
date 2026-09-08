"""Framework-neutral routing for the MVP workflow.

An integration adapter may later map these node names to LangGraph nodes.
"""

from enum import StrEnum


class WorkflowNode(StrEnum):
    PARSE_ISSUE = "parse_issue"
    REPO_ONBOARDING = "repo_onboarding"
    CREATE_PLAN = "create_plan"
    CREATE_CHECKPOINT = "create_checkpoint"
    IMPLEMENT = "implement"
    RUN_TESTS = "run_tests"
    VERIFY = "verify"
    DIAGNOSE_FAILURE = "diagnose_failure"
    SELECT_CHECKPOINT = "select_checkpoint"
    RESTORE = "restore"
    REPLAN = "replan"
    FINAL_REVIEW = "final_review"
    END = "end"


def next_after_verification(*, passed: bool, should_rewind: bool) -> WorkflowNode:
    if passed:
        return WorkflowNode.FINAL_REVIEW
    return WorkflowNode.SELECT_CHECKPOINT if should_rewind else WorkflowNode.DIAGNOSE_FAILURE

