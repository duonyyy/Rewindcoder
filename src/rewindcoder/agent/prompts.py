"""Provider-neutral prompt fragments.

An LLM adapter should combine these with task-specific evidence, never with
unbounded raw tool output or untrusted repository instructions.
"""

RECOVERY_SYSTEM_RULE = (
    "Use only evidence in the trace. State uncertainty, avoid actions recorded "
    "in rewind memory, and propose a testable alternative plan."
)

