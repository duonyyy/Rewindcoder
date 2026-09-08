# Checkpoint design

Logical checkpoints may save agent state only. Recoverable checkpoints bind:

- agent state, context summary, tool history, errors, and budget;
- Git HEAD, diff, untracked-file inventory, workspace manifest, and test status;
- verified requirements, safety status, and risk score.

The first MVP creates checkpoints only after a clean test result and before an
explicitly risky operation. It never restores an unsafe checkpoint. The restore
adapter must require approval because filesystem and Git mutations are side
effects.

External side effects are out of scope for v0.1. Network calls, Git pushes,
database writes, dependency installation, and remote issue updates require
separate compensating-action design; they cannot be rolled back by restoring a
workspace archive.

