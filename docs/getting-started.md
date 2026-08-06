# Quickstart

This page takes you from installation to a completed local job. You do not
need an HPC account, a configuration file, or a running daemon.

## Install

molq requires Python 3.12 or newer.

=== "pip"

    ```bash
    pip install molcrafts-molq
    ```

=== "uv"

    ```bash
    uv add molcrafts-molq
    ```

The distribution is named `molcrafts-molq`; the Python package and command are
both named `molq`.

```bash
molq --help
```

## Run a local job

Create a destination, attach a queue to it, and submit an argument vector:

```python
import molq as mq

cluster = mq.Cluster("laptop", "local")

with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "-c", "print('hello from molq')"]
    )
    result = job.wait()

print(result.state.value)
print(result.exit_code)
```

Expected output:

```text
succeeded
0
```

`"laptop"` is a namespace for persisted records. `"local"` selects the
no-batch scheduler. The context manager closes the SQLite connection when the
work is finished; it does not cancel the job.

## Inspect what was submitted

`submit_job()` returns a `JobHandle` immediately:

```python
with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(argv=["sleep", "2"])

    print(job.job_id)            # molq's stable ID
    print(job.scheduler_job_id)  # backend-specific ID
    print(job.status())          # cached state

    job.refresh()                # one scheduler reconciliation pass
    record = job.wait(timeout=30)
```

The final `JobRecord` contains the state, timestamps, exit code, command,
working directory, and artifact paths.

You can inspect the same record from the CLI. Reuse the cluster namespace:

```bash
molq list local --cluster laptop --all
molq status JOB_ID local --cluster laptop
molq inspect JOB_ID local --cluster laptop
```

!!! tip "Keep the namespace stable"

    Job commands filter records by cluster name. If submission used
    `"laptop"`, inspection must also use `--cluster laptop`.

## Run your own program

`argv` is the safest command form because arguments are not interpreted by a
shell:

```python
with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "analysis.py", "--input", "sample.xyz"]
    )
    record = job.wait()
```

Use `command=` only when you intentionally need shell syntax such as pipes or
redirection. Use `script=` for multi-line shell logic. See
[Submit jobs](jobs.md#choose-a-command-form).

## Move the same workflow to SLURM

Use an SSH host alias that already works with `ssh`:

```sshconfig
Host dardel
    HostName dardel.pdc.kth.se
    User alice
```

Then change the destination and add scheduler resources:

```python
import molq as mq

cluster = mq.Cluster("dardel", "slurm", host="dardel")

with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "train.py"],
        resources=mq.JobResources(
            cpu_count=8,
            memory=mq.Memory.gb(32),
            time_limit=mq.Duration.hours(4),
        ),
        scheduling=mq.JobScheduling(
            partition="gpu",
            account="project123",
        ),
    )
    print(job.job_id)
```

molq invokes the system `ssh`, `rsync`, and scheduler clients. Your existing
OpenSSH configuration remains the source of truth for authentication,
ProxyJump, agents, and connection sharing.

!!! warning "Code and inputs must exist remotely"

    `argv=["python", "train.py"]` does not upload `train.py`. Stage files first
    with a [Workspace or Project](remote-files.md), or submit from a working
    directory that already exists on the cluster.

## Where to go next

- [Mental model](concepts.md) explains the small set of objects you just used.
- [Submit jobs](jobs.md) covers resources, execution settings, retries, and
  dependencies.
- [Clusters and schedulers](schedulers.md) covers local, SSH, SLURM, PBS, and
  LSF destinations.
- [Monitor jobs](monitoring.md) covers status, logs, history, and daemon mode.
