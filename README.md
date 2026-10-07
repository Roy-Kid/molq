# molq 0.9.0

molq controls local executions and HPC allocations through one language-independent RPC contract. CLI, Python SDK, TypeScript SDK, Web UI and the optional Observer are peer clients. Runtime owns the business implementation; Scheduler owns native resource, submission, dependency and state semantics.

**0.9.0 is a breaking replacement of 0.8.x.** Submitor, JobStore, implicit local destinations, Rich output, retry, workspace and the old daemon/plugin API are removed. Re-register destinations explicitly. Old jobs.db files are neither read nor migrated nor deleted.

## Quickstart

Install Python 3.12 or later:

```sh
pip install molcrafts-molq
molq --registry ./registry.db clusters register --definition '{"name":"local","scheduler":"shell","target_root":"/tmp/molq-target"}'
molq --registry ./registry.db submit local -- echo hello
```

The submit response contains a stable registry-qualified JobRef. Save it and pass it to status, logs, cancel or wait:

```sh
molq --registry ./registry.db status --ref @job-ref.json
molq --registry ./registry.db wait --ref @job-ref.json --timeout 60
molq discover
```

Use the OOP Python client without starting a service:

```python
from molq import Molq

with Molq(registry="registry.db") as mq:
    mq.clusters.register(
        name="local", scheduler="shell", target_root="/tmp/molq-python"
    )
    job = mq.cluster("local").submit(argv=["echo", "hello"])
    print(job.wait(timeout=60)["completion"])
    print(job.logs()["text"])
```

When no endpoint is configured, native clients start a temporary stdio Runtime. Accepted Shell jobs detach from the client and retain original target launch/exit receipts; scheduler jobs already belong to the scheduler. Restarting a client can query a saved JobRef.

## Shared Runtime and Web

```sh
export MOLQ_TOKEN='replace-with-your-own-long-secret'
molq runtime serve --registry ./registry.db --host 127.0.0.1 --port 17891
```

Open http://127.0.0.1:17891/ and enter the token. Connect other clients to that same endpoint using MOLQ_ENDPOINT and MOLQ_TOKEN. HTTP and WebSocket use the same RPC implementation as stdio. A token is required even on loopback; deploy HTTPS/WSS through existing infrastructure.

One registry normally has one active Runtime. Configure an explicit endpoint for shared clients. Temporary stdio instances have separate cache, event rings and cursors; SQLite protects short accidental write overlap, without synchronizing their observations.

Runtime performs finite requested operations. Periodic observation is optional:

```sh
molq --endpoint http://127.0.0.1:17891 observer --cluster local --interval 5
```

Observer chooses cadence and notification delivery; Runtime computes snapshots, completion and changes. Subscriptions passively distribute already observed changes and do not poll a scheduler.

## Persistence and execution

SQLite persists only registry identity/schema, Cluster definitions, Runtime settings and presets. Job states, history, transitions, events, cursors, leases and retry queues are not persisted. Scheduler/accounting is task truth. Shell launch and exit receipts are original execution evidence on the target, not a mirrored job database.

A Job is one allocation. Resources, Scheduling and Execution are independent sections. Execution holds units and explicit Unit/Sequence/Parallel plans. Memory is a decimal string of bytes **per node**; task and CPU budgets are explicit. MPI uses a configured launcher. nvidia_mps is a formal Scheduler resource request with no automatic GPU conversion or MPS server startup.

Slurm, OpenPBS and LSF mappings reject fields they cannot express accurately. This is static request validation, not capability negotiation or a promise that actual resources exist. Native schedulers accept or reject real requests.

OpenSSH owns host aliases, authentication, ProxyJump and multiplexing. molq invokes system ssh/rsync. A Cluster stores an alias and computing semantics, without copying SSH configuration.

## Platform and validation scope

The control plane uses stdio and HTTP/WebSocket on Linux, macOS and Windows. Targets use POSIX/Bash paths and tools. Windows clients can manage remote POSIX targets through OpenSSH or a shared Runtime; native Windows Shell execution is outside this release.

Local Shell execution and all native scheduler mappings have regression tests. HPC tests use command fixtures; no live Slurm/PBS/LSF cluster was available during this reconstruction.

The TypeScript package lives in sdk/typescript. Run npm ci and npm test there; the Node stdio transport starts Runtime directly. The browser client uses HTTP/WebSocket. All methods remain accessible through generic rpc calls.

## Development

```sh
uv sync --extra dev
uv run python tools/build_contract.py
uv run python tools/generate_clients.py
npm --prefix sdk/typescript ci
npm --prefix sdk/typescript test
uv run ruff check src tests tools examples
uv run ruff format --check src tests tools examples
uv run ty check src/
uv run pytest --cov=molq --cov-report=xml
uv run python -m build
```

See [the architecture spec](docs/spec/molq-1-0-runtime-spec.md), [implementation ledger](docs/spec/implementation-0-9-0.md) and [documentation](docs/getting-started.md).
