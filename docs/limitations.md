# Limitations and release blockers

- Three locked fixtures support a common scripted failure and replan across
  all six variants; all 18 planned smoke cells have raw evidence. Three
  fixtures cannot stand in for a 10–20 task main evaluation. The Phase 5 TSV
  and adapter task contracts change only `max_rewinds` to 2 for every variant.
- Retry-only, aligned-no-memory and full all pass the three scripted tasks. The
  scripted alternative is fixed. Neither a success advantage over retry-only
  nor a memory benefit is measured. One-sided restore is rejected by the same
  invariant used for PASS, so its failure is an integrity result, not an
  unbiased task-success comparison.
- The mock is deterministic and scripted; seed 0 is one run, not an uncertainty
  estimate. No live coding model/provider is bundled or tested.
- Local fixture tests execute Python code without an OS sandbox. Docker Engine
  was unavailable on the test host. Arbitrary or hostile repository evaluation
  is NOT_READY. External provider modules are trusted local code, not isolated.
- Checkpoints cover Git-visible tracked and non-ignored untracked regular files.
  They do not reverse database, network, cloud, package, deployment or push
  side effects. A partial filesystem failure can leave a workspace changed,
  while the verifier correctly refuses PASS.
- The current Phase 2–5 source includes uncommitted and untracked files absent
  from HEAD. Source hashes protect local run provenance, but a fresh clone of
  HEAD cannot replay these results. Fresh-clone quickstart and full-suite gates
  remain NOT_READY until a reviewable source revision exists and is tested.
- Token usage is estimated from text bytes; elapsed time is local and one run
  per variant. No claims about provider cost, latency distribution, or general
  coding accuracy follow from the smoke run.
