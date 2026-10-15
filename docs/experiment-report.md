# Phase 5 fixture smoke report — 2026-10-16

**Scope: runner and verifier smoke only. RQ1–RQ3: NOT_READY.** Protocol
`phase5-fixture-smoke-v5` has SHA-256
`b7eca02e2af0c12a56125eff85b6ecb000533ba02aec117540cd612ea730f4b6`.
The `v1`–`v4` runs were exploratory development artifacts and are excluded. The
`v5` protocol was fixed after those exploratory outcomes, so it is not a
prospective main-study protocol.

## Paired outcomes

| Task / seed | Forward | Retry | Agent only | Repo only | Aligned no memory | Full |
|---|---|---|---|---|---|---|
| Parser / 0 | FAIL | PASS | NOT_READY | NOT_READY | PASS | PASS |
| TSV / 0 | FAIL | PASS | NOT_READY | NOT_READY | PASS | PASS |
| Adapter / 0 | FAIL | PASS | NOT_READY | NOT_READY | PASS | PASS |

Planned 18 cells; 18 structurally valid run bundles; 0 skipped,
missing, invalid or duplicate after validation. Twelve bundles reached a
final independent verifier outcome (nine PASS, three FAIL); six one-sided
restores stopped `NOT_READY` after post-restore integrity rejection.

| Variant | Task success (completed) | Recovery success | Restore integrity | Wrong rewind | Regression | Est. tokens | Seconds | Tool calls | CP bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Forward | 0/3 | N/A | N/A | N/A | 0/3 | 2395 | 4.303 | 25 | 15091 |
| Retry | 3/3 | N/A | N/A | N/A | 0/3 | 3557 | 5.740 | 40 | 15093 |
| Agent only | N/A | 0/3 | 0/3 | 3/3 | N/A | 2395 | 8.103 | 40 | 15095 |
| Repo only | N/A | 0/3 | 0/3 | 3/3 | N/A | 2395 | 8.379 | 40 | 15093 |
| Aligned no memory | 3/3 | 3/3 | 3/3 | 0/3 | 0/3 | 3863 | 10.155 | 55 | 15093 |
| Full | 3/3 | 3/3 | 3/3 | 0/3 | 0/3 | 4541 | 10.810 | 55 | 15093 |

Repeated Failure Rate is N/A for every variant: there were no observed
post-restore failures, so its denominator is zero. The remaining definitions
and denominator rules are in [evaluation.md](evaluation.md). Timing and token
values describe these local scripted runs only; one seed yields no uncertainty
interval. All variants create an initial checkpoint as instrumentation, even
when no rollback is used.

Planned-cell yield keeps every stopped cell in view: forward 0/3, retry 3/3,
agent only 0/3, repo only 0/3, aligned no memory 3/3 and full 3/3. These
are scripted fixture outcomes, not a general model success estimate.

## What the failure cases show

- Forward-only preserves the injected faulty action and fails target and hidden
  acceptance on all three tasks. Retry-only corrects the damaged workspace
  locally and passes all three. Full also passes all three; **it does not
  outperform retry-only here**. RQ1 has no positive evidence from this smoke.
- Agent-only restore retains the faulty repository bytes; the independent
  workspace-manifest/Git-diff checks fail. Repository-only restore omits the
  agent state; its independent agent-state check fails. Both stop before a new
  plan can claim task success. This is a fail-closed integrity demonstration,
  not a fair estimate of comparative task-solving quality for RQ2.
- Aligned no-memory and full both pass with the same scripted alternative.
  The no-memory variant receives only a failure type; full receives structured
  rewind memory. The mock's fixed alternative cannot test whether memory
  reduces repeated strategies. RQ3 remains unmeasured.

Raw evidence: [`evals/results/raw/phase5-fixture-smoke-v5/`](../evals/results/raw/phase5-fixture-smoke-v5/)
contains one trace, manifest, patch and checkpoint bundle per recorded cell.
The validator output is
[`evals/results/summary/phase5-fixture-smoke.json`](../evals/results/summary/phase5-fixture-smoke.json).
The final verifier, not the provider, sets PASS. One full-run manifest replay
matched base commit, budget, tests, status, verifier result and restore outcome.
