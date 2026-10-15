# Phase 4 gate report — 2026-10-15

## Decision and boundary

**PASS for deterministic self-recovery in the reviewed, disposable parser fixture.**
This is an offline mock-provider gate. Arbitrary repositories, live models,
general code reasoning, and a measured improvement over the forward-only
baseline remain **NOT_READY**. Automatic restore is restricted to a new fixture
workspace under `artifacts/runs/`; the RewindCoder checkout was not rewound.

The starting project HEAD was `cd6f9c5dcaa13d938cc49d4350d2dcde377f4123`.
Phase 2/3 implementation and reports were already uncommitted before this work.
They were preserved. No reset, deletion, commit, or push was performed.

## Exit gates

| Gate | Result | Executed evidence |
|---|---|---|
| Deterministic taxonomy and policy | PASS | Unit tests cover security and budget STOP, transient bounded RETRY, target/regression/no-progress DIAGNOSE, repeated-failure REWIND, unexpected-edit STOP, max-rewind STOP. Every branch is bounded by the existing step, token, tool and elapsed budgets. |
| Select a recoverable checkpoint | PASS | `CheckpointManager.list_safe()` and `load()` validate archive bytes, manifest, agent state, test evidence and workspace identity; selector additionally compares current Git HEAD. Tests reject corrupt archive, missing evidence, wrong HEAD and no candidate. A metadata `safe=true` flag alone is insufficient. |
| Aligned restore and approval | PASS | Recovery calls the Phase 3 `manual_rewind` path, with fixture-scoped approval. Its independent verifier checks restored manifest, Git diff, agent state/checkpoint ID and checkpoint test. Denied approval and a repository-only restore caused by agent-state write failure terminate without PASS. |
| Structured diagnosis, memory, alternative plan | PASS | JSONL events link test results, Git diff hash/summary and tool observations by trace IDs. Memory contains all required fields, including `source_trace_ids`. The mock replanner receives the public task, repository evidence and this memory. It cannot repeat the failed action or identical edit bytes; negative tests reject both. |
| Final independent verification | PASS | After alternative edit, the verifier checks target and regression tests, evaluator-only hidden acceptance, changed/forbidden paths, unexpected edits, security status, Git HEAD, restore checks and the persisted agent state/checkpoint ID. Provider output alone never sets PASS. |
| Three failure-injection trajectories | PASS | Three fresh demo runs below include a complete checkpoint bundle, failed test observations, DIAGNOSE then REWIND, aligned restore, memory, a different edit and final verifier PASS. The demo command checks artifact existence, trace/patch hashes and state checkpoint alignment. |
| Negative paths terminate | PASS | Integration tests cover forbidden and unexpected edits, step/tool/token/elapsed exhaustion, `max_rewinds=0`, no safe checkpoint, corrupt/missing bundle evidence, HEAD mismatch, denied approval, one-sided restore and repeated alternative action/edit. None reached PASS. |

## Reproducible demo artifacts

Run `python -B scripts/phase4_demo.py` with `PYTHONPATH=src` and
`PYTHONDONTWRITEBYTECODE=1`. The top-level index is
`evals/results/self_recovery/demo-summary.json`. Each run directory below
contains `trace.jsonl`, `manifest.json`, `diff.patch`,
`post-recovery-state.json`, and a `checkpoints/` bundle and rewind trace.

| Injected failure | Final run directory | Checkpoint ID | Final result |
|---|---|---|---|
| Target failure | `evals/results/self_recovery/demo-parser-001/run-f964073604f2410f9fe4b9583596787f/` | `cp-42f8db9261bd45f985631eed1cf217fa` | PASS |
| Regression failure | `evals/results/self_recovery/demo-parser-001/run-accb9da6e45a4f468d3357028e694538/` | `cp-274c2e8d0d0e47389d97eaf318b76825` | PASS |
| No progress/repeated failure | `evals/results/self_recovery/demo-parser-001/run-ade0400fdc1844df8c5b7e1f0df14338/` | `cp-31ecb2087ebc431ca689f334a3965997` | PASS |

The first faulty action is respectively `return_raw_name`,
`replace_valid_name_with_constant`, and `annotate_unchanged_behavior`.
Each run chooses `validate_stripped_name_then_return_it` after restore; the
actual edit bytes differ from the failed edit. The two failed public-test
observations share a failure fingerprint before REWIND. The no-progress case
reruns tests without an intervening edit, making that lack of progress explicit.
The post-restore state and repository bundle share the listed checkpoint ID.
The rewind trace records `verify_workspace_manifest`, `verify_git_diff`,
`verify_agent_state` and `verify_target_tests` as passed. The final run manifest
records target, regression and hidden checks as passed and no forbidden edit.

The checkpoint uses the passing **regression** test as evidence because the
unfixed fixture intentionally fails the target test. This proves a recoverable
clean base, not that the task was already solved at checkpoint time.

## Commands and observed results

From the repository root:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest discover -s tests -t .
python -B scripts/phase1_preflight.py
python -B -m rewindcoder.cli run --task evals/tasks/sample_recovery_task.json --output artifacts/phase4-baseline-after
python -B -m rewindcoder.cli run --task evals/tasks/tsv_whitespace.json --output artifacts/phase4-baseline-after
python -B -m rewindcoder.cli run --task evals/tasks/adapter_service.json --output artifacts/phase4-baseline-after
python -B scripts/phase3_demo.py
python -B scripts/phase4_demo.py
git diff --check
```

- Unified suite: **53 tests, OK, 1 skipped**. The skip is Windows symlink
  creation permission; the mock-based symlink rejection path remains tested.
- Phase 1 preflight: **3/3 fixtures passed** base/gold repeatability and
  forbidden-edit detection.
- Three Phase 2 CLI baseline reruns: **3/3 verifier PASS**, run IDs
  `run-7206736c5e8d43baa6f7dce782d3b090`,
  `run-969e651cc0e44944b0358a5c0ef9f3b4`, and
  `run-10f44b7ff34542648a9d931e3006f181`.
- Phase 3 manual demo: **PASS** at
  `artifacts/phase3-demo/ac983e33538340c6a1c1418885ef387d/`:
  clean target test passed, harmful edit failed, approved aligned rewind restored
  the passing test.
- Phase 4 demo: **3/3 verifier PASS**, with each final failure taxonomy matching
  the injected scenario. `git diff --check`: exit 0; Git emitted only existing
  LF-to-CRLF working-copy warnings.

Unit policy tests establish decision logic; integration tests exercise the
actual fixture workspace, checkpoint and restore; the saved demo artifacts are
offline fixture E2E evidence. None is evidence for live model quality or a
production repository restore.

## Phase 4 files changed

- Recovery policy, selector, memory and workflow:
  `src/rewindcoder/recovery/{detector,selector,memory,workflow}.py`.
- Existing workflow/CLI and mock provider:
  `src/rewindcoder/agent/graph.py`, `src/rewindcoder/cli.py`,
  `src/rewindcoder/providers/mock.py`.
- Run manifest contract and schema:
  `src/rewindcoder/contracts/manifest.py`,
  `evals/schemas/run_manifest.schema.json`.
- Evidence, tests and report: `scripts/phase4_demo.py`,
  `tests/unit/test_phase4_policy.py`,
  `tests/integration/test_phase4_recovery.py`,
  `evals/results/self_recovery/`, `docs/phase-4-gate-report.md`.
- Updated usage/boundary documentation: `README.md`,
  `docs/{architecture,security,checkpoint-design}.md`.

## Remaining limits

- The mock provider uses scripted faulty and alternative edits on one parser
  fixture. Three failure modes are covered, but diverse repository tasks are
  untested. The no-progress scenario is a repeated test observation, not a
  general semantic progress detector.
- Checkpoint storage and demo artifacts are local. The snapshot excludes
  ignored files and external side effects; a filesystem write failure can
  leave a partial workspace, but it stops without PASS. Python fixture tests
  have no OS sandbox for hostile repositories.
- Token accounting is an estimate. The timeout bounds waiting in the harness;
  it does not provide process isolation for arbitrary external providers.
- Phase 5 must perform a fair, paired evaluation before claiming that rewind
  improves completion rate over forward-only or retry-only.
