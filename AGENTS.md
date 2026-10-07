# molq 0.9.0 development contract

The architecture principles in docs/spec/molq-1-0-principles.md and concrete contract in docs/spec/molq-1-0-runtime-spec.md apply to 0.9.0. This is a breaking replacement; do not restore Submitor, JobStore, old plugins/CLI or backward compatibility.

## Ownership and dependencies

Clients (CLI, Python sync/async OOP SDK, TypeScript SDK, Web, Observer) are peers over public RPC. They may share wire codecs and value constructors, but must not wrap another client's façade or import Scheduler, Transport, registry or Runtime services for business operations. CLI Runtime process entry points assemble the service only.

Runtime has one implementation, internally ordinary modules: protocol/domain, registry, planning, observation, services, Scheduler, Transport and RPC adapters. No extra backend/driver/engine/controller abstraction or internal service boundary.

Scheduler is the implementation abstraction. SlurmScheduler/PBSScheduler/LSFScheduler/ShellScheduler own native resource/directive/dependency/launcher mapping, rendering, submit/query/history/cancel and native state normalization. Runtime does not branch on Scheduler names for business logic. Transport is orthogonal and owns bounded target I/O.

No capability inventory, probing, feature negotiation or fallback. Validation proves schema validity and exact representation only; real scheduling resources and permissions remain native decisions.

SQLite persists exactly schema_meta, clusters, settings and presets. No mirrored Job state/history, event, lease or retry tables. Native scheduler/accounting is task truth. Shell launch/exit receipts are original target execution evidence. Clients never open the registry.

Cluster stores destination semantics only: ID/name, Scheduler/Transport binding, SSH alias, target root, defaults and necessary site launcher/dialect configuration. No cadence or notification policies. One registry normally has one active Runtime; temporary stdio is the no-service mode. Independent instances do not share cache/events/cursors.

Runtime owns canonical snapshots/completion and scoped diff/events; Observer chooses cadence/backoff/notification and uses RPC only. Notifications fail open. Subscriptions passively deliver already observed events.

Use asynchronous bounded subprocesses and Cluster/batch concurrency. No permanent Job coroutine/timer/session. OpenSSH owns SSH configuration/multiplexing; invoke system ssh/rsync and never shut down user masters. No retry/workflow/MPS manager.

## Public model and wire contract

Job is one allocation, with independent Resources/Scheduling/Execution. Execution units compose through UnitRef/Sequence/Parallel; each unit appears once. Single-unit argv stays simple. Memory is decimal-string bytes per node. MPI and CPU/task budgets are explicit. nvidia_mps is a formal Scheduler resource; no automatic MPS launch or whole-GPU fallback.

Python request values are frozen dataclasses. Molq/Cluster/Job/JobCollection are RPC-only OOP handles. Protocol major 1 uses JSON-RPC 2.0 with named params, 1 MiB frames, 128-request batches and structured errors. CLI outputs JSON with stable exit semantics.

Edit tools/build_contract.py for schemas and src/molq/client/objects.py for the Python projection. Regenerate protocol/v1.json, protocol/types.py, async_objects.py and TypeScript types; do not edit generated files directly. TypeScript build generates the Web wire codec.

## Required checks

    uv sync --extra dev
    uv run python tools/build_contract.py
    uv run python tools/generate_clients.py
    npm --prefix sdk/typescript ci
    npm --prefix sdk/typescript test
    uv run python tools/check_generated.py
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run ty check src/
    uv run pytest --cov=molq --cov-report=xml
    uv run python -m build

Coverage floor is 80%, including Runtime subprocesses. Tests are in tests/v09. Use real SQLite/temporary files, fake native command fixtures for HPC mappings, real local Shell integration and installed-wheel smoke tests. Do not claim fixture tests prove live HPC resources. Windows checks cover the remote control plane; POSIX/Bash local execution runs on Linux/macOS.

No import side effects. Keep source modules below 800 lines. Preserve user data and accepted native jobs during failures/client exit. Mutation disconnection means uncertain outcome; no automatic resend/fallback.
