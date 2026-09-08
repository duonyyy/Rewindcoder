# Evaluation plan

Run every system variant against the same frozen task set, repository revision,
model configuration, token budget, timeout, tool policy, and execution image.

Compare at least:

1. forward-only baseline;
2. retry-only baseline;
3. aligned rewind without rewind memory;
4. full RewindCoder.

Report task success, target/regression test pass rate, recovery success,
repeated-failure rate, unnecessary rewind rate, tokens, latency, tool calls,
and checkpoint storage. Preserve the full JSONL trace for each result.

Do not interpret an agent's self-reported success as task success. The
independent verifier and repository tests are the acceptance authority.

