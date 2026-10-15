# Phase 3 gate report — 2026-10-15

## Decision and scope

**PASS for aligned checkpoint and approved manual rewind in a disposable local
fixture.** The CP1 demonstration below contains a real workspace archive,
serialized agent state, passing test evidence, an approved rewind trace, and
independent post-restore verification. Arbitrary repository execution and
automatic rewind are **NOT_READY**. No restore was run against this project
checkout.

Before implementation, `git rev-parse HEAD` returned
`cd6f9c5dcaa13d938cc49d4350d2dcde377f4123`. The Phase 2 source,
documentation, fixtures and baseline files were present as working-tree
changes. The unified test command passed 32/32 at that point. Those unrelated
changes were preserved. No commit, push or reset was performed.

## Exit gates

| Gate | Status | Executed evidence |
|---|---|---|
| One ID binds agent and repository state | PASS | CP1 metadata, `agent-state.json` and restored state share `cp-2d17220476ea40b68ca77f58655adfc9`; exact state equality and workspace manifest checks passed |
| Recoverable content outside target | PASS | `workspace.zip` is in `artifacts/phase3-demo/.../checkpoints/`, outside the disposable `artifacts/runs/...` target; archive hashes and contents validated |
| Atomic publication and safe listing | PASS | Pending directory is renamed only after complete validation; injected publish/capture failures, missing archive/manifest/test evidence and corrupt archive were not listed as safe |
| Tracked and untracked changes | PASS | Integration restored tracked edits/deletions and untracked creation, edits and deletions; manifest and Git diff hash matched |
| Approval and fail-closed preflight | PASS | Denied approval, wrong workspace identity, Git HEAD mismatch, corrupt bundle, zero timeout, traversal and symlink checks stopped; project checkout was not rewound |
| Independent post-restore verifier | PASS | Manifest, Git diff, exact agent state and target tests all passed for CP1; one-sided restore tests were rejected |
| Manual CLI and evidence | PASS | `checkpoint create/list/inspect` and `rewind --checkpoint` exercised by `scripts/phase3_demo.py`; JSONL trace and run manifest record approval, each step and PASS conclusion |
| Phase 2 regression | PASS | Three mock fixture CLI runs returned PASS; unified suite 45 tests, 1 environment skip; Phase 1 preflight 3/3 PASS |

## CP1 demonstration

Run `python -B scripts/phase3_demo.py` with `PYTHONPATH=src` and
`PYTHONDONTWRITEBYTECODE=1`. The final recorded run is under
`artifacts/phase3-demo/0b304b0e77e2487d922b59c151711edd/`:

- `demo-summary.json`: baseline target test PASS, harmful edit test FAIL,
  restored target test PASS.
- `checkpoints/cp-2d17220476ea40b68ca77f58655adfc9/`: versioned metadata,
  archive, manifest, serialized agent state and test evidence.
- `checkpoints/runs/rewind-5370c4cfe63e47e798348c68d1d49e52/trace.jsonl`
  and `manifest.json`: approval, integrity, HEAD, both restore actions,
  manifest hash, Git diff, agent state and target-test verification all PASS.

The archive and report are ignored local artifacts, so they are available in
this workspace but are not part of the source tree. The trace and run manifest
contained no `evaluator_only`, `hidden_requirements` or `gold_patch` strings.

## Commands and observed results

From the repository root, with `$env:PYTHONPATH='src'` and
`$env:PYTHONDONTWRITEBYTECODE='1'`:

```powershell
python -B scripts/phase1_preflight.py
python -B -m unittest discover -s tests -t .
python -B -m rewindcoder.cli run --task evals/tasks/sample_recovery_task.json --output artifacts/phase3-baseline-regression
python -B -m rewindcoder.cli run --task evals/tasks/tsv_whitespace.json --output artifacts/phase3-baseline-regression
python -B -m rewindcoder.cli run --task evals/tasks/adapter_service.json --output artifacts/phase3-baseline-regression
python -B scripts/phase3_demo.py
git diff --check
```

Preflight: 3/3 fixture bases PASS. Unified suite: **45 tests, OK, 1 skipped**;
the skip is real Windows symlink creation permission, while mock-based symlink
rejection passed. Phase 2 fixture runs: **3/3 PASS** (`run-dfcd8b6d7f404560931561364a2d23c3`,
`run-cb572f00d767429e81962c791e6d5312`,
`run-5e3fdac911424a558fd2e1837a1eaa4d`). CP1 demo: PASS with failed tests
observed between create and rewind. `git diff --check`: exit 0; Git emitted
only existing LF-to-CRLF working-copy warnings.

## Phase 3 files changed

- Checkpoint capture and metadata: `src/rewindcoder/checkpoint/{metadata,manager,repository_snapshot}.py`.
- Manual restore and verifier: `src/rewindcoder/recovery/executor.py`,
  `src/rewindcoder/verification/checkpoint.py`.
- CLI and demo: `src/rewindcoder/cli.py`, `scripts/phase3_demo.py`.
- Tests: `tests/unit/test_phase3_checkpoint_contract.py`,
  `tests/integration/test_phase3_checkpoint.py`.
- Documentation: `docs/{checkpoint-design,architecture,security,phase-3-gate-report}.md`,
  `README.md`.

## Limitations

- This snapshot covers tracked and non-ignored untracked regular files. Ignored
  files and external effects are outside its manifest. Staged index changes
  are rejected; Git HEAD changes stop restore.
- Restore can partially mutate the disposable workspace if a filesystem write
  fails mid-restore; it reports `NOT_READY` and does not mark success. A
  separate transactional rollback of that partial write is not implemented.
- Python target tests execute local code without an OS sandbox. Only the
  controlled fixture was demonstrated; arbitrary or hostile repositories are
  not validated here.
- The `verified_requirements` list is caller supplied metadata. Phase 3 proves
  snapshot integrity and aligned restore, not the truth of every requirement
  claim or live model behavior. Phase 4 failure detection and automatic rewind
  were not implemented.
