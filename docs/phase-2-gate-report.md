# Phase 2 gate report — 2026-10-15

## Scope and decision

**PASS for the controlled, offline forward-only fixture gate.** General coding ability and safe execution of arbitrary repositories are **NOT_READY**. No rewind path is invoked.

Phase 1 was audited before Phase 2. At the Phase 1 commit `cd6f9c5`, `docs/phase-1-gate-report.md` correctly recorded `NOT_READY`: the three fixture bases and contract tests existed, but no persisted workflow trace/manifest or full-run repeatability evidence existed yet. Phase 2 integration runs now provide that missing evidence. The Phase 1 commit remains a historical foundation checkpoint; the current runner source hash is recorded in each Phase 2 manifest because Phase 2 code is uncommitted.

## Exit gates

| Exit gate | Result | Evidence |
|---|---|---|
| At least one fixture completes end-to-end | PASS | 3/3 CLI runs returned verifier `PASS`, including target, regression, hidden acceptance and changed-file checks |
| All three fixtures terminate under bounds | PASS | 3/3 completed; unit/integration cases cover max steps, token estimate, tool calls, elapsed deadline, provider timeout and controlled stop |
| Every edit and command appears in trace | PASS for fixture path | Each baseline trace has one `edit_file` call; eight command records per run (four fixed bootstrap Git commands, target, regression, Git status, Git diff). Tool result events include exit codes or denial reasons |
| Independent verifier gives final result | PASS | Verifier uses tool-returned test/Git evidence and separate hidden checks; regression, target, hidden-only failure and forbidden-edit tests do not produce PASS |
| Baseline result saved | PASS | Three `diff.patch`, `trace.jsonl`, `manifest.json` sets under `evals/baselines/forward_only/` |

## Baseline runs

| Task | Run ID | Base commit | Verifier | Trace events |
|---|---|---|---|---:|
| Parser | `run-b2b65fced3fd4355bd92b648954d1ccf` | `704e442013b980e52ecb23e9e75ac9ee1dcfe48c` | PASS | 42 |
| TSV | `run-97e0d4585718421f89ebdfb15cdbb489` | `0b51d8d83af987a08654469016e5405423866c0a` | PASS | 42 |
| Adapter/service | `run-6cefe16a1d5a450fb997cccc3da8a47f` | `f260333d5fe5fba4f36776d8ee3bf9d658fecf5d` | PASS | 44 |

All three trace and patch SHA-256 values match their manifests. No trace or manifest contains `evaluator_only`, `gold_patch`, or `hidden_requirements`. The evaluator checks run after implementation and are never supplied in the provider payload or fixture workspace. The test `test_hidden_acceptance_rejects_public_test_only_patch` confirms that passing both public test groups alone is insufficient.

## Commands and actual results

Run from the repository root with `PYTHONPATH=src` and `PYTHONDONTWRITEBYTECODE=1`:

```powershell
python -B scripts/phase1_preflight.py
python -B -m unittest discover -s tests -t .
python -B -m rewindcoder.cli run --task evals/tasks/sample_recovery_task.json
python -B -m rewindcoder.cli run --task evals/tasks/tsv_whitespace.json
python -B -m rewindcoder.cli run --task evals/tasks/adapter_service.json
git diff --check
```

Preflight: 3/3 fixture bases reproduced twice; each base target failed, regression passed, evaluator gold target/regression passed, and a forbidden README edit was detected. Unified test command: **32 tests PASS**. Three CLI commands: **3/3 verifier PASS**. `git diff --check`: **PASS**. Negative integration evidence includes target failure, regression failure, hidden acceptance failure, forbidden edit, invalid plan, provider error/timeout, real elapsed deadline, budget exhaustion and tool I/O error.

## Files changed in Phase 2

- Workflow and CLI: `src/rewindcoder/agent/graph.py`, `src/rewindcoder/cli.py`.
- Provider/budget: `src/rewindcoder/providers/{factory,mock}.py`, `src/rewindcoder/runtime/budget.py`.
- Tool and verifier boundary: `src/rewindcoder/tools/{policy,workspace}.py`, `src/rewindcoder/fixtures.py`, `src/rewindcoder/verification/hidden.py`.
- Run contract: `src/rewindcoder/contracts/manifest.py`, `evals/schemas/run_manifest.schema.json`, task evaluator-only descriptions.
- Evidence and tests: `evals/baselines/forward_only/`, `tests/integration/test_forward_only.py`, `tests/unit/test_phase2_budget_provider.py`.
- Documentation: `README.md`, `docs/{architecture,security,requirements,phase-2-gate-report}.md`.

## Limitations

- The mock provider returns scripted edits for exactly three known fixtures. E2E PASS proves the runner, policy, trace and verifier path, not autonomous code reasoning or live LLM quality.
- The optional environment-selected external provider is a trusted local plugin interface only. No real adapter, LLM server, cloud call or API key was used or tested.
- Tool paths are scoped, but Python tests execute code from a controlled fixture without an OS sandbox. Arbitrary repository execution and a malicious provider module remain NOT_READY.
- Token usage is a deterministic UTF-8 length/4 estimate, not provider-reported tokenizer usage. The elapsed deadline interrupts the waiting workflow; an untrusted external provider needs process isolation to guarantee cancellation.
- `rewindcoder_commit` identifies the Phase 1 commit; `runner_source_sha256` identifies the uncommitted Phase 2 Python source. A fresh checkout replay of Phase 2 is not claimed. No comparison with rewind variants is claimed.
