# RewindCoder

RewindCoder is a controlled-environment software-engineering agent that can
recover from a failed trajectory by restoring an aligned pair of agent and
repository checkpoints, recording why the previous strategy failed, and
producing an alternative plan.

**Release status: Phase 5 / v1.0 NOT_READY.** A six-policy offline fixture
smoke matrix and validator are available, but the main task set, sandbox and
live provider are not yet available. The source and fixture evidence passed a
fresh-clone check. See
[Phase 5 gate report](docs/phase-5-gate-report.md) and
[limitations](docs/limitations.md).

## Intended MVP claim (later phases)

The MVP demonstrates one bounded flow:

`issue -> plan -> checkpoint -> failed edit -> diagnose -> rewind -> alternative plan -> passing tests`

It does **not** claim to restore external side effects (network requests,
remote services, databases, package registries, or Git pushes). Those actions
must be blocked or require explicit approval.

## Current implementation

- Serializable agent state and checkpoint metadata
- Deterministic failure/retry/rewind policy
- Safe-checkpoint ranking and structured rewind memory
- Definition-of-done verifier and JSONL trace sink
- Reusable-skill contracts and a sample evaluation task
- Versioned task/state/trace/manifest contracts and three locked fixtures
- Phase 2 forward-only workflow with scoped tools and a scripted offline provider
- Phase 3 external workspace snapshots and explicitly approved manual rewind
- Phase 4 bounded self-recovery for three offline failure injections in one disposable fixture

## Run the tests

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -t .
```

## Phase 2 forward-only fixture run

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'
$env:REWINDCODER_PROVIDER = 'mock'
python -B -m rewindcoder.cli run --task evals/tasks/sample_recovery_task.json
```

The command creates a disposable Git workspace under ignored `artifacts/runs/`
and saves `diff.patch`, `trace.jsonl`, and `manifest.json` under
`evals/baselines/forward_only/<task_id>/<run_id>/`. The exit code is zero only
when the independent verifier reports PASS. Use the same test command above for
unit and offline integration tests.

The built-in mock is scripted for the three controlled fixtures. It validates
workflow plumbing and evidence, not general coding ability. To supply a trusted
provider implementation, set `REWINDCODER_PROVIDER=external` and
`REWINDCODER_PROVIDER_MODULE=rewindcoder_external_<name>`; that module must
export `create_provider()` implementing the provider protocol. No real provider
module or model service ships in Phase 2.

## Phase 3 manual checkpoint and rewind

`--workspace` must name a Git root. `--storage` and `--state-output` must be
outside that workspace. Prepare a `state/v1` JSON file, then run:

```powershell
python -B -m rewindcoder.cli checkpoint create --workspace <fixture-git-root> --storage <external-storage> --state <agent-state.json> --target-test "python -m unittest tests.test_parser.ValidNameTests"
python -B -m rewindcoder.cli checkpoint list --workspace <fixture-git-root> --storage <external-storage>
python -B -m rewindcoder.cli checkpoint inspect --workspace <fixture-git-root> --storage <external-storage> --checkpoint <cp-id>
python -B -m rewindcoder.cli rewind --workspace <fixture-git-root> --storage <external-storage> --checkpoint <cp-id> --state-output <external-state.json> --approve --approver <name>
```

The rewind command mutates the named workspace only after explicit approval.
Use `python -B scripts/phase3_demo.py` to reproduce the full CP1 flow in a
disposable fixture; it saves a summary, bundle, trace, and run manifest under
ignored `artifacts/phase3-demo/`. See [docs/checkpoint-design.md](docs/checkpoint-design.md)
for coverage and limits.

## Phase 4 offline recovery demo

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'
python -B scripts/phase4_demo.py
```

The demo saves three trace/manifest/checkpoint bundles and a
`evals/results/self_recovery/demo-summary.json` index. It uses the same
approved, independently verified restore path as Phase 3. The scripted mock
provider and one parser fixture establish workflow evidence only; see
[docs/phase-4-gate-report.md](docs/phase-4-gate-report.md).

## Phase 5 fixture smoke and replay

From the repository root with Python 3.13.2 and Git 2.47.0.windows.2:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B scripts/phase1_preflight.py
python -B -m unittest discover -s tests -t .
python -B scripts/phase5_evaluate.py
python -B scripts/phase5_validate.py
```

The matrix runs three tasks × six variants × one seed. All 18 cells have raw
JSONL traces, manifests, patches and checkpoint bundles are under
`evals/results/raw/phase5-fixture-smoke-v5/`; machine-readable metrics are in
`evals/results/summary/phase5-fixture-smoke.json`. Replay one run with
`python -B scripts/phase5_replay.py <path-to-run-manifest>`.
See [evaluation protocol](docs/evaluation.md),
[environment recipe](docs/reproducibility.md), and
[experiment report](docs/experiment-report.md). The `v1`–`v4` smoke
artifacts were created during runner development and are excluded from the
`v5` summary.

