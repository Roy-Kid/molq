# molq 0.9.0 implementation ledger

Breaking replacement of 0.8.1. The accepted runtime architecture and 50 principles apply to 0.9.0 immediately; no compatibility façade or old JobStore migration is shipped.

## Phases

- [complete] Contract and regression tests: strict versioned schemas, allocation/units/plan, owned-state registry, scheduler truth and client boundaries.
- [complete] Runtime: async subprocess Transport, four Scheduler implementations, registry, query/cache/diff/events, finite RPC operations and stdio/HTTP/WS.
- [complete] Peer clients: Python OOP, generated TypeScript wire types/OOP client, Agent-first CLI, Web and optional Observer.
- [complete] Release preparation: meaningful tests, coverage/lint/type/build/installed-wheel checks, documentation and CI. Delivery is recorded in Git on origin/master.

## Module impact

Remove Submitor, JobStore/store, reconciler, retry, retention, workspace, dashboard, old configuration/options/handles and legacy CLI/tests. Replace scheduler/transport with async in-process modules. Add protocol schema/catalog, domain constructors, owned-state registry, observation, runtime services/RPC adapters and wire clients. Keep all external scheduler syntax and state normalization inside scheduler/. Observer and clients import neither runtime services nor persistence nor Scheduler/Transport.

SQLite holds only schema metadata, clusters, runtime settings and presets. Shell targets retain original detached launch/process/exit receipts. Existing user jobs.db and scheduler jobs are not deleted. One registry normally has one active Runtime; temporary stdio is the no-service native mode.

## Frozen decisions for this release

Resources use nodes/tasks/cpus_per_task, per-node decimal-string memory_bytes, positive integer time_limit_seconds, and typed gpu/nvidia_mps quantities per_node or total. GPU/MPS mixing is rejected when the selected Scheduler cannot represent it. Plans are bounded trees: each unit exactly once; sequence stops on first failure; parallel waits for all started branches and returns the first failing branch in plan order. MPI requires explicit site launcher binding; no environment probing. Output defaults to allocation stdout/stderr, with optional per-unit target paths. One registry belongs to one OS/HPC identity; network entry requires a bearer token, including loopback; TLS is supplied by deployment infrastructure.

## Validation evidence

Local macOS/Python 3.12.12: 86 regression tests pass, 88.01% coverage (80% floor). Ruff lint/format and ty pass. Two native TypeScript conformance tests pass over stdio and HTTP, including real execution/logs and typed auth errors. Canonical schema/DTO/async-projection/Web-codec generation has no drift. Zensical builds without issues. Wheel/sdist build and strict metadata checks pass; a clean installed wheel outside the checkout imports every module/export, includes protocol/Web assets, excludes legacy packages and runs a real no-service job. npm pack contents are verified. CI covers Linux/macOS on Python 3.12/3.13, Windows remote control plane, TypeScript, generated drift and installed artifacts; all eight jobs passed on the initial reconstruction commit [d48ee12 CI](https://github.com/Roy-Kid/molq/actions/runs/37640525202). The follow-up CLI partial-query exit-code regression is verified locally and by the delivery commit's CI. Fake scheduler fixtures test mapping and parsing, not actual cluster resources, permission or configuration. Linux/macOS local execution and Windows control plane support are distinct; missing target tools fail structurally.
