# Changelog

## 0.9.0

Breaking architecture replacement: one serve process and one RPC contract. CLI, Python sync/async SDK and the TypeScript SDK are peer clients. There is no web UI and no compatibility layer for an older API.

Scheduler/Transport are orthogonal async modules; OpenSSH owns connection configuration and multiplexing. Native scheduler/accounting and original Shell receipts supply task truth. SQLite persists only registry metadata, Clusters, settings and presets. Detached Shell jobs survive client/Runtime exit.

Allocations use separate Resources/Scheduling/Execution, explicit bounded Unit/Sequence/Parallel plans, CPU/task budgets, site-bound MPI and formal nvidia_mps requests. Unsupported mappings fail explicitly. Agent-first JSON output, structured errors and exit codes, and stdio, HTTP and WebSocket entry points replace the old CLI, dashboard and daemon.

Removed Submitor, mirrored job state/history, retry, retention, workspace, plugin host and implicit local destination fallback. Re-register destinations and save registry-qualified native JobRefs. HPC mappings are fixture-tested; local execution is POSIX/Bash, with Windows control-plane checks in CI.
