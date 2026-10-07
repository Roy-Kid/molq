# Changelog

## 0.9.0

Breaking architecture replacement: one Runtime business implementation and one versioned RPC contract. CLI, Python sync/async OOP SDK, native TypeScript SDK, Web and optional Observer are peer clients. No 0.8 compatibility layer or JobStore migration.

Scheduler/Transport are orthogonal async modules; OpenSSH owns connection configuration and multiplexing. Native scheduler/accounting and original Shell receipts supply task truth. SQLite persists only registry metadata, Clusters, settings and presets. Detached Shell jobs survive client/Runtime exit.

Allocations use separate Resources/Scheduling/Execution, explicit bounded Unit/Sequence/Parallel plans, CPU/task budgets, site-bound MPI and formal nvidia_mps requests. Unsupported mappings fail explicitly. Agent-first JSON output, structured errors/exit codes, stdio/HTTP/WS entry points and a token-authenticated Web client replace the old CLI/dashboard/daemon.

Removed Submitor, mirrored job state/history, retry, retention, workspace, plugin host and implicit local destination fallback. Re-register destinations and save registry-qualified native JobRefs. HPC mappings are fixture-tested; local execution is POSIX/Bash, with Windows control-plane checks in CI.
