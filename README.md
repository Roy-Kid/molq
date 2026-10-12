# molq 0.9.0

molq controls local executions and HPC allocations through one language-independent RPC contract. The CLI, Python SDK, TypeScript SDK and `molq watch` are peer clients. `molq serve` owns the business implementation. Scheduler owns native resource, submission, dependency and state semantics. There is no web UI.

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

## Shared serve process

Put the listen address and token in the configuration file, then start serve:

```json
{"serve": {"host": "127.0.0.1", "port": 17891, "token": "replace-with-your-own-long-secret"}}
```

```sh
molq serve --registry ./registry.db --config ./config.json
```

Clients set `client.endpoint` and `client.token` in that file, or pass them to the SDK constructor. HTTP and WebSocket use the same RPC implementation as stdio. A token is required even on loopback. There is no web UI.

One registry normally has one active serve process. Temporary stdio instances have separate cache, event rings and cursors.

```sh
molq watch --registry ./registry.db --config ./config.json --cluster local
```

`watch` chooses cadence and notification delivery. The serve process computes snapshots, completion and changes.

## Persistence and execution

SQLite persists only registry identity and Cluster definitions. Settings and presets are a JSON or YAML file, by default `~/.molcrafts/molq/config.json`. Job states, history, transitions, events, cursors, leases and retry queues are not persisted. Scheduler accounting is task truth. Shell launch and exit receipts are original execution evidence on the target.

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

See [the architecture spec](docs/spec/molq-1-0-runtime-spec.md) and [documentation](docs/getting-started.md).

## Query names and native history

```sh
molq list Arrhenius --state running
molq history Arrhenius --state failed --since 2026-10-06T00:00:00Z --until 2026-10-08T00:00:00Z
```

Snapshots include native name/comment and available UTC timestamps. Historical
ranges select terminal jobs by ended-at `[since, until)`, defaulting to the past
24 hours for the current target account. This release supports range discovery
on Slurm; other Schedulers explicitly reject ranges and retain ref-based history.
History retention and stored comments depend on the site's native accounting.

Configuration is a JSON or YAML file selected with `--config`. There is no
registry schema older than the current file layout, and a foreign database is
left untouched.
