# Phase 5 evaluation protocol and interpretation

The machine-readable fixture smoke protocol is [`evals/protocol.json`](../evals/protocol.json).
Its exact bytes are SHA-256 hashed into every recorded run manifest. The current
protocol ID is `phase5-fixture-smoke-v5`. The earlier `v1`–`v4` runs were
exploratory runner development and are excluded. No smoke protocol is a
preregistered main study: `v5` was fixed after seeing exploratory outcomes. No RQ1–RQ3
claim may be inferred from these fixtures.

## Task and variant matrix

The planned smoke matrix is three locked Phase 1 tasks × six variants × seed 0
= 18 cells. Each pair uses the task's locked base commit, public prompt,
target/regression commands, provider configuration, seed, policy and task budget.
The TSV and adapter Phase 5 task contracts raise only `max_rewinds` from 0 to
2; all six variants use the same budget for each task. The evaluation runner
records unsupported cells as `SKIP_UNSUPPORTED`, although all 18 smoke cells
ran in `v5`. The prior Phase 2 forward-only success runs use
a success-scripted provider path and must not be joined to this matrix.

| Variant | Agent restore | Repo restore | Persistent rewind memory | Failure policy |
|---|---:|---:|---:|---|
| `forward_only` | No | No | No | One faulty edit, then independent final verifier |
| `retry_only` | No | No | No | Local correction on damaged workspace, then verifier |
| `agent_state_rewind` | Yes | No | Yes | One-sided fixture ablation; verifier rejects mismatch before replan |
| `repository_only_rewind` | No | Yes | No | One-sided fixture ablation; verifier rejects mismatch before replan |
| `aligned_no_memory` | Yes | Yes | No | Verified restore, replan with failure type only |
| `rewindcoder_full` | Yes | Yes | Yes | Verified restore, structured memory supplied to replan |

All six variants create the same initial checkpoint as common instrumentation.
Forward-only and retry-only never select or restore it. Consequently checkpoint
storage and startup latency include instrumentation cost in those baselines.
The two one-sided policies deliberately violate the aligned restore invariant;
their NOT_READY outcomes test fail-closed integrity, not task-solving quality.
The scripted mock chooses the same successful alternative for both aligned
variants. It cannot establish that memory improves planning.

## Data and validation

`scripts/phase5_evaluate.py` writes a unique run ID, raw JSONL trace, patch,
manifest and checkpoint bundle under `evals/results/raw/<protocol-id>/`. A
cell with an existing run resumes only when protocol, runner/source/task hashes,
seed and variant match. `scripts/phase5_validate.py` enumerates the full matrix
and checks missing/duplicate/mixed cells, schema, trace completion and event
identity, trace/patch hashes, task/base/HEAD, source and protocol hashes,
provider, policy, test and budget equivalence, usage bounds and verifier PASS.
It emits `evals/results/summary/phase5-fixture-smoke.json`. A skipped or invalid
cell stays visible. `scripts/phase5_replay.py <manifest>` recreates a disposable
fixture and compares base, budget, tests, status, verifier and restore outcome.

## Metric definitions

Use only structurally valid runs. `PASS` and `FAIL` are completed final-verifier
runs; `NOT_READY`, invalid and skipped cells remain separately counted. A zero
denominator is N/A, never 0%.

- Task Success Rate = verifier PASS / completed final-verifier runs. Also report
  completed/planned coverage and PASS / all planned cells as a separate yield;
  never silently drop skipped cells. Planned-cell yield is not model accuracy
  because a skipped task was never attempted.
- Recovery Success Rate = final verifier PASS after a restore attempt / restore
  attempts. One-sided rejected attempts remain in this denominator.
- Repeated Failure Rate = post-restore failures repeating the failed action or
  root cause / observed post-restore failures. No such failure was observed in
  the smoke matrix, so its denominator is zero and the metric is N/A.
- Wrong Rewind Rate = policy-invalid or unsafe restore attempts / restore
  attempts. Intentional one-sided ablations count as policy-invalid.
- Restore Integrity Rate = independently verified aligned restores / restore
  attempts; manifest, Git diff, agent state and checkpoint test must pass.
- Regression Rate = final regression-test failures / runs with final regression
  evidence. One-sided runs stopped before final tests are N/A.
- Token usage is the harness's UTF-8 byte/4 estimate, not model token billing.
  Latency is local wall time; tool calls count harness calls. Checkpoint storage
  counts direct bundle files. The summary publishes sums and per-variant
  numerators/denominators.

For a main evaluation, freeze a new protocol before observing its outcomes:
select 10–20 distinct eligible tasks and base commits; use a provider capable
of all six variants; fix model parameters, prompts, tool policy, budgets,
tests, image and seeds; run in a verified sandbox; choose exclusion rules in
advance. Use multiple seeds for nondeterministic providers and report paired
outcomes with uncertainty intervals. Do not change tasks, metrics or PASS rules
after seeing results. The main evaluation remains NOT_READY.

