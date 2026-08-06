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
operation opens a master connection, and the rest reuse it for
`control_persist` (60 seconds by default). The control socket lives in
`~/.ssh/molq/`.

Turn it off for hosts that refuse multiplexed sessions:

```python
from molq.options import SshTransportOptions

opts = SshTransportOptions(host="dardel", control_master=False)
```

| Option | Default | Purpose |
|---|---|---|
| `control_master` | `True` | Reuse one SSH connection across operations |
| `control_persist` | `"60s"` | How long an idle master connection lingers |
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
