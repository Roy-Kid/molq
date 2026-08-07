# Clusters and schedulers

A molq destination has two independent choices:

- **Scheduler** — which queue system accepts the request.
- **Transport** — where scheduler commands and file operations execute.

Keeping them separate lets the same scheduler implementation work on the
current host or through SSH.

## Common destinations

| Goal | Cluster |
|---|---|
| Run a process on this machine | `Cluster("laptop", "local")` |
| Run a process on an SSH workstation | `Cluster("workstation", "local", host="workstation")` |
| Use SLURM installed on this host | `Cluster("hpc", "slurm")` |
| Use a remote SLURM cluster | `Cluster("dardel", "slurm", host="dardel")` |

`host=` accepts the same target you pass to `ssh`, including a
`~/.ssh/config` alias.

```python
import molq as mq

local = mq.Cluster("laptop", "local")
remote = mq.Cluster("dardel", "slurm", host="dardel")
```

The first argument is also the record namespace. Pick a stable name and reuse
it when listing or inspecting jobs.

## Prefer SSH aliases

Put connection details in OpenSSH configuration:

```sshconfig
Host dardel
    HostName dardel.pdc.kth.se
    User alice
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

Verify it outside molq:

```bash
ssh dardel hostname
```

Then let molq use the alias:

```python
cluster = mq.Cluster.from_ssh_alias(
    "dardel",
    scheduler="slurm",
)
```

`from_ssh_alias()` asks `ssh -G` for the effective user, host, port, and
identity file. ProxyJump, agents, and Kerberos continue to be handled by the
system OpenSSH client.

### Connection multiplexing

A single job performs many small remote operations: write the job script,
create the directory, poll for an exit code, read logs. Without a shared
connection each one is a separate TCP and authentication handshake, which
dominates wall-clock time and is painful on sites with Kerberos or hardware
tokens.

molq therefore enables OpenSSH connection multiplexing by default: the first
operation opens a master connection and the rest ride along on it.

#### Sharing a socket with your own `ssh`

A control socket is identified purely by its `ControlPath`. Two clients share
one master connection exactly when both resolve to the same path — so molq
does not impose its own if you already have one.

**If `~/.ssh/config` sets a `ControlPath` for the host**, molq inherits it:

```sshconfig
Host dardel
    HostName dardel.pdc.kth.se
    User alice
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
```

Now `ssh dardel` and molq use the same connection in both directions.
Whichever runs first becomes the master; the other attaches to it. Your
`ControlPersist` is left alone, since it governs a socket you also use.

**If nothing is configured**, molq supplies its own socket at
`~/.ssh/molq-%C`. To let plain `ssh` attach to *that* one, point your config
at the same path:

```sshconfig
Host dardel
    ControlPath ~/.ssh/molq-%C
```

`%C` is a hash of the resolved user, host, and port, so it matches whether
you write `ssh dardel` or `ssh alice@dardel.pdc.kth.se` — unlike
`%r@%h:%p`, which only expands inside a matching `Host` block.

Check what a host resolves to with:

```bash
ssh -G dardel | grep -i control
```

#### Options

Turn multiplexing off for hosts that refuse it:

```python
from molq.options import SshTransportOptions

opts = SshTransportOptions(host="dardel", control_master=False)
```

| Option | Default | Purpose |
|---|---|---|
| `control_master` | `True` | Reuse one SSH connection across operations |
| `control_path` | `None` | Explicit socket path; `None` inherits from ssh_config, else `~/.ssh/molq-%C` |
| `control_persist` | `"60s"` | Idle master lifetime — ignored when inheriting |
| `connect_timeout` | `15` | Seconds before an unreachable host fails |

## Local

The `"local"` scheduler is the no-batch backend. The transport determines
which machine starts the process.

```python
# This machine
cluster = mq.Cluster("laptop", "local")

# A remote machine without a queue manager
cluster = mq.Cluster("gpu-box", "local", host="gpu-box")
```

Local jobs do not have a shared scheduler queue, so `cluster.get_queue()`
returns an empty list.

## SLURM

```python
cluster = mq.Cluster(
    "dardel",
    "slurm",
    host="dardel",
    scheduler_options=mq.SlurmSchedulerOptions(
        sbatch_path="sbatch",
        squeue_path="squeue",
        scancel_path="scancel",
        sacct_path="sacct",
        extra_sbatch_flags=("--clusters=gpu",),
    ),
)
```

Default command names normally work. Pass `SlurmSchedulerOptions` only when
binaries or site-wide flags differ.

## PBS

```python
cluster = mq.Cluster(
    "pbs-login",
    "pbs",
    host="pbs-login",
    scheduler_options=mq.PBSSchedulerOptions(
        qsub_path="qsub",
        qstat_path="qstat",
        qdel_path="qdel",
        tracejob_path="tracejob",
    ),
)
```

PBS and Torque use the same backend.

## LSF

```python
cluster = mq.Cluster(
    "lsf-login",
    "lsf",
    host="lsf-login",
    scheduler_options=mq.LSFSchedulerOptions(
        bsub_path="bsub",
        bjobs_path="bjobs",
        bkill_path="bkill",
        bhist_path="bhist",
    ),
)
```

## Customize the SSH transport

Use an explicit transport when an alias is not enough:

```python
from molq.options import SshTransportOptions
from molq.transport import SshTransport

ssh = SshTransport(
    SshTransportOptions(
        host="login.example.org",
        port=2222,
        identity_file="~/.ssh/hpc_key",
        ssh_opts=("-o", "ProxyJump=jump.example.org"),
        rsync_opts=("-a", "--partial", "--inplace"),
        control_master=True,
        control_persist="60s",
        connect_timeout=15,
    )
)

cluster = mq.Cluster("hpc", "slurm", transport=ssh)
```

`host=` and `transport=` are mutually exclusive.

## Submit the same request everywhere

Scheduler-independent values live in the job request:

```python
resources = mq.JobResources(
    cpu_count=8,
    memory=mq.Memory.gb(32),
    gpu_count=1,
    time_limit=mq.Duration.hours(4),
)

scheduling = mq.JobScheduling(
    partition="gpu",
    account="project123",
)
```

The backend translates them into `sbatch`, `qsub`, or `bsub` syntax. It also
rejects unsupported fields before submission. A local job, for example, cannot
request a queue partition.

For the full request model, see [Submit jobs](jobs.md).

## Inspect the live queue

`Cluster.get_queue()` reads the scheduler directly:

```python
for entry in cluster.get_queue():
    print(
        entry.scheduler_job_id,
        entry.state.value,
        entry.partition,
    )
```

| Scheduler | Command family |
|---|---|
| local | none; returns `[]` |
| SLURM | `squeue`, with `sacct` for terminal resolution |
| PBS | `qstat`, with `tracejob` for terminal resolution |
| LSF | `bjobs`, with `bhist` for terminal resolution |

This view is not molq history. See
[Persisted records versus the live queue](monitoring.md#persisted-records-versus-the-live-queue).

## Add a backend

`Scheduler` is a `typing.Protocol`, so a backend is any object implementing
it — no base class, no registration decorator:

| Method | Responsibility |
|---|---|
| `capabilities()` | Which request fields this backend can express |
| `submit(spec, job_dir)` | Dispatch a job, return the scheduler's job id |
| `poll_many(ids)` | Batch state query |
| `cancel(id)` | Kill a job |
| `resolve_terminal(id)` | Final state for a job that left the queue |
| `list_queue(user=...)` | The live queue snapshot |
| `format_dependency(edge)` | One dependency edge in this backend's syntax |
| `format_dependencies(edges)` | The whole set, for the submit directive |

`capabilities()` is what makes molq reject impossible requests up front rather
than after a failed submission — a backend that returns
`supports_gpu_count=False` causes `ConfigError` at submit time.

Dependency syntax belongs to the backend, since only it knows whether waiting
on job 123 reads `afterok:123`, `done(123)`, or something else:

```python
from molq import DependencyEdge

SlurmScheduler().format_dependencies([
    DependencyEdge("after_success", "1"),
    DependencyEdge("after_failure", "2"),
])
# 'afterok:1,afternotok:2'
```

In-tree backends live one per module under `molq/scheduler/`. Everything a
backend needs to express — directives, dependency syntax, queue parsing,
terminal resolution — stays in that one file.

## Diagnose connection failures

Check the layers in order:

1. Does `ssh ALIAS hostname` work?
2. Does `ssh ALIAS which sbatch` (or `qsub` / `bsub`) find the scheduler?
3. Does the remote working directory exist?
4. Are partition, account, and resource values valid for that site?
5. Does `cluster.get_queue()` return a parsed response?

If connections succeed individually but fail under load, retry with
`control_master=False` — a few sites reject multiplexed sessions.

`SchedulerError` carries the failed command and stderr when the backend cannot
communicate with the scheduler.
