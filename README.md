# RewindCoder

RewindCoder is a controlled-environment software-engineering agent that can
recover from a failed trajectory by restoring an aligned pair of agent and
repository checkpoints, recording why the previous strategy failed, and
producing an alternative plan.

## MVP claim

The MVP demonstrates one bounded flow:

`issue -> plan -> checkpoint -> failed edit -> diagnose -> rewind -> alternative plan -> passing tests`

It does **not** claim to restore external side effects (network requests,
remote services, databases, package registries, or Git pushes). Those actions
must be blocked or require explicit approval.

## Current scaffold

- Serializable agent state and checkpoint metadata
- Deterministic failure/retry/rewind policy
- Safe-checkpoint ranking and structured rewind memory
- Definition-of-done verifier and JSONL trace sink
- Reusable-skill contracts and a sample evaluation task

## Run the tests

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -t .
```

Read [docs/architecture.md](docs/architecture.md) before adding an LLM,
repository snapshot implementation, or command execution adapter.

