# Submit jobs

This guide covers the request you pass to `Submitor.submit_job()`: command,
resources, scheduling policy, execution environment, retries, and
dependencies.

## Choose a command form

Exactly one command form is required.

| Form | Use it for | Shell interpreted? |
|---|---|---|
| `argv=[...]` | Programs with explicit arguments | No |
| `command="..."` | A one-line shell expression | Yes |
| `script=Script...` | Multi-line or existing shell scripts | Yes |

### Argument vector

Prefer `argv` for ordinary programs:

```python
job = queue.submit_job(
    argv=["python", "train.py", "--epochs", "50"]
)
```

Each item is one argument. Wildcards, `$VARS`, pipes, and redirects are not
expanded.

### Shell command

Use `command` when shell syntax is the point:

```python
job = queue.submit_job(
    command="python analyse.py | gzip > results.txt.gz"
)
```

### Script

Use an inline script for a short multi-step workflow:

```python
import molq as mq

job = queue.submit_job(
    script=mq.Script.inline(
        """\
set -euo pipefail
python preprocess.py
python train.py
"""
    )
)
```

Or submit an existing file:

```python
job = queue.submit_job(script=mq.Script.path("run.sh"))
```

## Describe resources, scheduling, and execution

molq keeps three concerns separate:

| Object | Describes | Typical fields |
|---|---|---|
| `JobResources` | Hardware and time | CPU, memory, GPU, wall time |
| `JobScheduling` | Queue policy | partition, account, QoS, dependency |
| `JobExecution` | Process environment | cwd, name, env, output paths |

```python
import molq as mq

job = queue.submit_job(
    argv=["python", "train.py"],
    resources=mq.JobResources(
        cpu_count=8,
        memory=mq.Memory.gb(32),
        gpu_count=1,
        time_limit=mq.Duration.hours(4),
    ),
    scheduling=mq.JobScheduling(
        partition="gpu",
        account="project123",
        qos="normal",
    ),
    execution=mq.JobExecution(
        cwd="/scratch/alice/project",
        job_name="train-resnet",
        env={"OMP_NUM_THREADS": "8"},
    ),
)
```

Values remain typed in Python:

```python
mq.Memory.parse("32G")
mq.Duration.parse("2h30m")
mq.Duration.parse("04:00:00")
```

The selected scheduler validates unsupported fields before submission. For
example, a local job cannot request a SLURM partition.

## Reuse an allocation you have used before

Every successful submission records its partition / account / QoS /
reservation combination against the cluster. Recalling them is purely local —
no query goes to the scheduler:

```python
for allocation in queue.remembered_allocations(limit=5):
    print(
        allocation.partition,
        allocation.account,
        allocation.use_count,
    )
```

Results come back most-recently-used first. This is what lets a submission UI
offer "the accounts you actually charge to" without asking the cluster, and
it survives retention cleanup — the memory lives apart from the `jobs` table,
so expiring old records does not erase it.

A configuration with none of those four fields set is not worth remembering
and is skipped.

## Set reusable defaults

Defaults belong to the `Submitor`; values supplied to `submit_job()` override
them field by field.

```python
defaults = mq.SubmitorDefaults(
    resources=mq.JobResources(
        cpu_count=4,
        memory=mq.Memory.gb(16),
        time_limit=mq.Duration.hours(2),
    ),
    scheduling=mq.JobScheduling(partition="compute"),
)

with mq.Submitor(target=cluster, defaults=defaults) as queue:
    job = queue.submit_job(
        argv=["python", "analyse.py"],
        resources=mq.JobResources(cpu_count=8),
    )
```

This job uses eight CPUs while inheriting memory, time, and partition.
Configuration profiles can supply the same defaults; see
[Configuration](configuration.md).

## Retry failures

`max_attempts` counts the first submission. A value of `3` means at most two
retries.

```python
policy = mq.RetryPolicy(
    max_attempts=3,
    retry_on_states=(mq.JobState.FAILED, mq.JobState.TIMED_OUT),
    retry_on_exit_codes=(1, 137),
    backoff=mq.RetryBackoff(
        mode="exponential",
        initial_seconds=10,
        maximum_seconds=120,
    ),
)

job = queue.submit_job(
    argv=["python", "train.py"],
    retry=policy,
)
final_record = job.wait()
```

Each retry is a new persisted attempt with its own job ID. The original handle
follows the family to its latest attempt. Inspect all attempts with:

```python
family = queue.get_retry_family(job.job_id)
```

## Add job dependencies

Dependencies use **molq job IDs**, not scheduler IDs. They are supported by
SLURM, PBS, and LSF, but not by the local scheduler.

```python
prepare = queue.submit_job(argv=["python", "prepare.py"])

train = queue.submit_job(
    argv=["python", "train.py"],
    after_success=[prepare.job_id],
)

cleanup = queue.submit_job(
    argv=["python", "cleanup.py"],
    after=[train.job_id],
)
```

| Keyword | Child becomes eligible after the parent… |
|---|---|
| `after_success` | succeeds |
| `after_failure` | fails, is cancelled, times out, or is lost |
| `after_started` | starts running |
| `after` | reaches any terminal state |

Each keyword accepts a list, so a job can wait for several upstream jobs.
For programmatically built schedules, the equivalent representation is a tuple
of `DependencyRef` objects in `JobScheduling.dependencies`.

## Find logs and artifacts

Unless paths are overridden, molq creates a job directory below the resolved
working directory:

```text
<cwd>/.molq/jobs/<job-id>/
```

The resolved paths are stored in `JobRecord.metadata`:

```python
record = job.wait()
print(record.metadata["molq.job_dir"])
print(record.metadata["molq.stdout_path"])
print(record.metadata["molq.stderr_path"])
```

For remote destinations, use `queue.fetch_logs()` or
`queue.fetch_artifacts()` to copy results to the local machine. See
[Monitor jobs](monitoring.md#read-logs).

## A complete HPC submission

```python
import molq as mq

cluster = mq.Cluster("dardel", "slurm", host="dardel")

with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "train.py", "--seed", "42"],
        resources=mq.JobResources(
            cpu_count=8,
            memory=mq.Memory.gb(32),
            gpu_count=1,
            time_limit=mq.Duration.hours(4),
        ),
        scheduling=mq.JobScheduling(
            partition="gpu",
            account="project123",
        ),
        execution=mq.JobExecution(
            cwd="/cfs/klemming/scratch/a/alice/my-run",
            job_name="train-42",
        ),
        retry=mq.RetryPolicy(max_attempts=2),
        metadata={"experiment": "baseline"},
    )

    print(job.job_id)
```
