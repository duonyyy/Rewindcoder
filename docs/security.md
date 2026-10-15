# Security policy

The target repository, issue text, tests, and tool output are untrusted input.
The default policy is deny. Read/search, status/diff, and bounded test commands
may be automatic; package installation, destructive Git operations, and
deletion require approval. Network commands are denied.

For the Phase 2 fixture runner, unknown and network commands are **DENY**.
Risky commands are classified `APPROVAL` and are never executed by the agent
tool layer. Exact fixture bootstrap Git commands have a separate context-bound
allowlist and run only inside a disposable workspace under `artifacts/`.
Every bootstrap command is recorded in the JSONL trace. Read, search, edit,
test, Git status, and Git diff use the fixture workspace as their boundary;
symlinks, traversal, `.git/` reads, and forbidden edits are denied.

Python fixture tests execute local code; Phase 2 does not provide an OS sandbox
for arbitrary repositories. The CLI accepts only the three locked fixture
templates. External provider plugins are trusted local code and are optional.

For arbitrary repository support in a later phase, command execution needs an
OS sandbox in addition to this workspace path boundary. The trace records
command, permission decision, exit status, and an output summary; it does not
persist full test output.

Phase 3 manual rewind requires `--approve --approver <name>` even for a
disposable fixture. The CLI never rewinds the RewindCoder checkout during its
tests or demo. Checkpoint storage and restored agent-state output must be
outside the target workspace. Snapshot creation rejects symlinks, path
traversal, staged index changes, failed target tests, and evaluator-only fields
in agent state. Restore checks approval, bundle integrity, workspace identity,
and Git HEAD before mutation. The post-restore verifier owns the PASS decision.

Phase 4 automatic restore is limited to a freshly prepared, reviewed parser
fixture under `artifacts/runs/`. Its fixture-scoped approval is recorded in the
run trace and passed through the Phase 3 manual restore executor. The CLI does
not grant this automatic approval to arbitrary repositories. Forbidden and
unexpected edits stop the workflow; no safe bundle, wrong HEAD, denied approval
or partial restore cannot produce PASS.

The Phase 5 fixture-smoke runner extends the same automatic branch to the
reviewed TSV and adapter templates. Their Phase 5 task contracts allow two
rewinds with identical per-task budgets across all six policies. This does not
expand automatic approval to a repository URL or an arbitrary local checkout.

Phase 5 preserves default deny. The one-sided ablation API requires an explicit
fixture-ablation flag and a `run-*` workspace under `artifacts/runs/`; it still
runs the independent post-restore verifier. Agent-only and repository-only
restores terminate `NOT_READY` when the untouched side fails alignment. The
public CLI does not expose this ablation flag. The issue, repository source and
tool output are untrusted; tests feed representative malicious instructions to
the command boundary and exercise path denial. They do not establish
end-to-end resistance of a live model to prompt injection.
Hidden evaluator requirements and gold patches are withheld from provider
payloads and fixture workspaces. Raw traces are checked for those field names.

The existing suite covers unknown/network commands, forbidden paths, traversal,
symlink rejection (real symlink creation may be skipped by Windows permissions),
approval denial, wrong workspace/HEAD, corrupt or missing checkpoints, partial
restore, timeouts and step/tool/token/rewind exhaustion. Arbitrary repository
tests remain unsafe here: `docker version` could not connect to Docker Engine
on 2026-10-15. Do not run untrusted repositories with this local fixture runner.

