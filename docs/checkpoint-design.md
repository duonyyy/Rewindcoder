# Phase 3 aligned checkpoint design

`checkpoint/v2` binds one `cp-<uuid>` to serialized `state/v1`, Git HEAD,
tracked and untracked file inventories, SHA-256 content hashes, file modes,
the Git diff hash, passing target-test evidence, verified requirements, and
safety status. `agent_state.current_checkpoint` must equal that ID.

The storage directory must be outside the target Git workspace. A checkpoint
bundle contains `metadata.json`, `manifest.json`, `workspace.zip`,
`agent-state.json`, and `test-evidence.json`. Capture writes to a hidden pending
directory, validates each artifact and its hash, then publishes the entire
directory by rename. `checkpoint list` validates complete bundles and omits
pending, missing, and corrupt ones. A metadata `safe=true` field by itself
cannot make a bundle selectable.

The archive contains actual bytes for existing tracked and untracked files.
Tracked deletions have a null hash. Restore deletes files created after CP1,
recreates deleted files, rewrites changed bytes, and restores file modes. It
does not call `git reset` or `git clean`. Ignored files are outside the
manifest. Staged index changes are rejected at capture because this version
does not snapshot the Git index.

Manual rewind requires an explicit approver, the same workspace identity and
Git HEAD, and a complete validated bundle. Path traversal, symlinks, non-file
entries, and storage inside the target are rejected. The restore executor
writes both repository bytes and a separate agent-state output. The independent
verifier then checks full manifest equality, Git diff hash, exact agent-state
equality and checkpoint ID, and reruns the allowlisted target test. The JSONL
trace and `rewind-run/v1` run manifest record approval, each check and final
conclusion. Any failure ends `NOT_READY`, including a partial I/O failure.

This is a local workspace snapshot. It cannot reverse external side effects,
Git HEAD changes, ignored files, or a mutation that happens concurrently with
restore. Test commands execute local fixture code; there is no OS sandbox for
arbitrary repositories. Phase 4 uses this same bundle validator and restore
executor for its disposable parser fixture branch. Its selector also checks
workspace identity and Git HEAD before choosing a bundle. General automatic
recovery in arbitrary repositories remains outside this implementation.
