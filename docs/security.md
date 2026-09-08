# Security policy

The target repository, issue text, tests, and tool output are untrusted input.
The default policy is deny. Read/search, status/diff, and bounded test commands
may be automatic; package installation, destructive Git operations, deletion,
network access, and remote writes require approval.

All eventual command execution must run in a sandbox with an explicit
filesystem scope, masked secrets, and a trace record containing the command,
permission decision, approver when relevant, exit status, and output summary.

