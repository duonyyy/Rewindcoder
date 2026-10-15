# RewindCoder Phase 1 Requirements

This document defines only the contracts needed to close WP1. It does not claim that fixtures, an LLM provider, repository restoration, or automatic rewind are implemented.

## Version identifiers

| Contract | Version | Canonical implementation |
|---|---|---|
| Evaluation task | `task/v1` | `rewindcoder.contracts.task` |
| Agent state | `state/v1` | `rewindcoder.contracts.state` |
| Trace event | `trace/v1` | `rewindcoder.contracts.trace` |
| Run manifest | `run-manifest/v1` | `rewindcoder.contracts.manifest` |

Version changes are breaking until an explicit migration is added and tested. `RewindCoderState.from_dict()` accepts a missing version only for state objects produced by the pre-WP1 scaffold; all newly serialized state includes `state/v1`.

## Requirements and verification

| ID | Requirement | Verification |
|---|---|---|
| R-C1 | A task includes a version, repository base commit, issue, explicit requirements, target/regression commands, forbidden paths, and a bounded budget. | `test_task_contract_validates_sample_and_rejects_missing_base_commit` |
| R-C2 | Agent-facing task data never contains evaluator-only hidden requirements, gold patches, or expected results. | `test_task_contract_hides_evaluator_only_fields_from_agent` |
| R-C3 | Checkpointed agent state round-trips through JSON and retains its version. | `test_state_round_trip_preserves_version_and_data` |
| R-C4 | Every trace event has UTC time, run ID, task ID, node, event, details, and `trace/v1`. | `test_trace_contract_requires_task_id_and_rejects_sensitive_details` |
| R-C5 | Every run manifest records task/base revision, runtime mode, command/result evidence, policy version, status, and `run-manifest/v1`. | `test_manifest_supports_not_run_without_claiming_success` |
| R-C6 | Trace and manifest reject credential-shaped keys/values and `.env` references. | `test_sensitive_data_is_rejected_from_trace_and_manifest` |
| R-C7 | Contracts reject unknown fields so a typo cannot silently change evaluator or agent behavior. | `test_contracts_reject_unknown_fields_and_versions` |
| R-F1 | Three disposable fixtures have stable Git base commits and base/gold/forbidden-edit evidence. | `python -B scripts/phase1_preflight.py` |
| R-P1 | Unknown and network commands fail closed; workspace reads/edits stay inside the fixture. | `tests.unit.test_phase1_foundation` |

## Safety boundary

- `evaluator_only` is stored in the full evaluation task but omitted from `TaskContract.to_agent_payload()`.
- Schema files document the interoperable JSON shape. Standard-library validators provide runtime enforcement in WP1; no third-party JSON-schema library is required.
- A schema validates structure, not patch correctness, command policy, fixture reproducibility, or recovery behavior. Those belong to WP2-WP4.

## Current WP1 scope status

| Area | Status |
|---|---|
| Versioned contracts and validators | In progress until unit tests pass |
| Fixture repositories | Not started (WP2) |
| Offline mock provider and run harness | Not started (WP3) |
| Phase 1 G1-G8 gate report | Not started (WP4) |
