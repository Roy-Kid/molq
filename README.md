<div align="center">

<h1>
  <img src=".github/assets/moko.svg" alt="" height="48" align="absmiddle">
  &nbsp;molq
</h1>

<p><strong>Unified job queue — one submission API for local, SLURM, PBS, and LSF</strong></p>

<p>
  <a href="https://github.com/MolCrafts/molq/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/MolCrafts/molq/ci.yml?style=flat-square&logo=githubactions&logoColor=white&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/molcrafts-molq/"><img src="https://img.shields.io/pypi/v/molcrafts-molq?style=flat-square&logo=pypi&logoColor=white&label=PyPI" alt="PyPI"></a>
  <a href="https://pypi.org/project/molcrafts-molq/"><img src="https://img.shields.io/pypi/pyversions/molcrafts-molq?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-18432B?style=flat-square" alt="License"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff"></a>
</p>

<p>
  <a href="https://github.com/MolCrafts/molq/tree/master/docs"><b>Documentation</b></a> &nbsp;&middot;&nbsp;
  <a href="#quick-start"><b>Quick start</b></a> &nbsp;&middot;&nbsp;
  <a href="#molcrafts-ecosystem"><b>Ecosystem</b></a>
</p>

</div>

molq is a unified job queue for Python workloads that need the same submission API on a laptop, a workstation, or an HPC cluster. A `Cluster` says *where* jobs run, a `Submitor` tracks *how* they progress — and the same code runs against local subprocesses or remote schedulers over SSH.

> **Under active development.** Public APIs may change between minor releases.

## Capabilities

| Module | Capability |
|--------|------------|
| `cluster` | `Cluster` — destination spec: scheduler kind × transport × scheduler options, plus live queue snapshots |
| `submitor` | `Submitor` + `JobHandle` — single entry point for submitting, tracking, and waiting on jobs |
| `scheduler` | `Scheduler` protocol with `Shell`, `Slurm`, `PBS`, and `LSF` backends, each routing shell calls through a transport |
| `transport` | `LocalTransport` / `SshTransport` — runs shell and file ops here or on a remote host via OpenSSH |
| `store` | `JobStore` — SQLite persistence with WAL mode, UUID job identity, schema versioning, and v1 auto-migration |
| `reconciler` | `JobReconciler` — batch-queries schedulers, diffs against the store, syncs job state |
| `monitor` | Blocking waits and polling engine driven by pluggable strategies |
| `strategies` | Pluggable polling strategies; exponential backoff by default |
| `callbacks` | `EventBus` — synchronous pub/sub for job lifecycle events with handler isolation |
| `models` | Job data models — `JobRecord`, `RetryPolicy`, `RetentionPolicy`, `JobDependency`, `SubmitorDefaults` |
| `types` | Frozen value types — `Memory`, `Duration`, `Script`, `JobResources`, `JobScheduling`, `JobExecution` |
| `options` | Per-scheduler frozen option dataclasses (`Local`, `Slurm`, `PBS`, `LSF`) — no untyped dicts |
| `config` | Profile and config loading from molcfg (`~/.molcrafts/molq/config/config.toml`, or `MOLCRAFTS_HOME`) |
| `plugin` | `MolqPlugin` host — official builtins + third-party entry points (`molq.plugins`) |
| `plugins` | Official plugins (e.g. `nerve` → local Nerve menu-bar status; fail-open) |
| `workspace` | `Workspace` / `Project` — directory handles over a cluster's filesystem (local or remote) |
| `ssh_config` | Surfaces `~/.ssh/config` hosts as cluster candidates |
| `serde` | Serialization helpers for stored requests and config-driven values |
| `errors` | Unified `MolqError` exception hierarchy with typed context |
| `status` | `JobState` enum with terminal-state semantics |
| `merge` | Pure function that merges per-submit parameters with `Submitor` defaults |
| `dashboard` | Full-screen terminal dashboard for monitoring runs and jobs |
| `testing` | `FakeScheduler` and `make_submitor` for tests and runnable examples without a real cluster |
| `cli` | Typer + Rich CLI: jobs (`submit`/`list`/`status`/`logs`/`cancel`/…), live (`watch`/`monitor`/`daemon`), setup (`clusters`/`workspace`/`plugins`) |

## Install

```bash
pip install molcrafts-molq
```

Requires Python 3.12+. Depends on `typer`, `rich`, `molcrafts-mollog`, and `molcrafts-molcfg`.

## Quick start

```python
import molq as mq

# Cluster = destination (where to run). Submitor = lifecycle (how jobs are tracked).
cluster = mq.Cluster("devbox", "local")

with mq.Submitor(target=cluster) as queue:
    handle = queue.submit_job(
        argv=["python", "-c", "print('hello from molq')"]
    )
    record = handle.wait()

print(record.state)
```

Swap to a cluster by changing one line — `mq.Cluster("hpc", "slurm", host="user@hpc.example.com")` — and the rest of the code is unchanged. See the [docs](https://github.com/MolCrafts/molq/tree/master/docs) for retries, dependencies, profiles, and the CLI.

## Documentation

- [Quickstart](docs/getting-started.md) — install and complete a local job
- [Mental model](docs/concepts.md) — understand destinations, tracking, and records
- [Submit jobs](docs/jobs.md) — commands, resources, retries, and dependencies
- [Clusters and schedulers](docs/schedulers.md) — local, SSH, SLURM, PBS, and LSF
- [Monitor jobs](docs/monitoring.md) — status, logs, history, and dashboards
- [Remote files](docs/remote-files.md) — stage inputs and collect results
- [Command line](docs/cli.md) — task-oriented CLI workflows
- [Plugins and Nerve](docs/plugins.md) — lifecycle observers and menu-bar status
- [Python API](docs/api.md) — generated, responsibility-based reference

## MolCrafts ecosystem

| Project | Role |
|---------|------|
| [molpy](https://github.com/MolCrafts/molpy)     | Python toolkit — the shared molecular data model & workflow layer |
| [molrs](https://github.com/MolCrafts/molrs)     | Rust core — molecular data structures & compute kernels (native + WASM) |
| [molpack](https://github.com/MolCrafts/molpack) | Packmol-grade molecular packing (Rust + Python) |
| [molvis](https://github.com/MolCrafts/molvis)   | WebGL molecular visualization & editing |
| [molexp](https://github.com/MolCrafts/molexp)   | Workflow & experiment-management platform |
| [molnex](https://github.com/MolCrafts/molnex)   | Molecular machine-learning framework |
| **molq**                                        | Unified job queue — local / SLURM / PBS / LSF — this repo |
| [molcfg](https://github.com/MolCrafts/molcfg)   | Layered configuration library |
| [mollog](https://github.com/MolCrafts/mollog)   | Structured logging, stdlib-compatible |
| [molhub](https://github.com/MolCrafts/molhub)   | Molecular dataset hub |
| [molmcp](https://github.com/MolCrafts/molmcp)   | MCP server for the ecosystem |
| [molrec](https://github.com/MolCrafts/molrec)   | Atomistic record specification |

## Contributing

Issues and pull requests are welcome — see the [docs](https://github.com/MolCrafts/molq/tree/master/docs) for development setup.

## License

MIT — see [LICENSE](LICENSE).

<hr>

<div align="center">
<sub>Crafted with 💚 by <a href="https://github.com/MolCrafts">MolCrafts</a></sub>
</div>
