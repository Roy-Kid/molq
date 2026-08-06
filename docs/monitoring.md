# Monitor jobs

molq stores job history in SQLite and updates active records by reconciling
them with the selected scheduler. You can observe that state through Python,
the CLI, or the full-screen dashboard.

## Persisted records versus the live queue

These two views are intentionally different:

| View | Source | Best for |
|---|---|---|
| `queue.list_jobs()` | molq's SQLite store | Your submissions, attempts, transitions, and history |
| `cluster.get_queue()` | `squeue`, `qstat`, or `bjobs` | The scheduler's current queue |

```python
records = queue.list_jobs(include_terminal=True)
entries = cluster.get_queue()
```

A scheduler entry may have been submitted outside molq. A completed molq record
may no longer appear in the scheduler queue.

## Follow one job

`JobHandle.status()` reads cached state. Call `refresh()` for scheduler I/O or
`wait()` to reconcile until the job is terminal.

```python
job = queue.submit_job(argv=["python", "train.py"])

print(job.status())
job.refresh()

record = job.wait(timeout=3600)
print(record.state.value, record.exit_code)
```

A timeout raises `MolqTimeoutError`; it does not cancel the job.

## Wait for several jobs

```python
jobs = [
    queue.submit_job(argv=["python", "task.py", str(i)])
    for i in range(4)
]

records = queue.watch_jobs(
    [job.job_id for job in jobs],
    timeout=7200,
)
```

Pass no IDs to `watch_jobs()` to wait for every active job in the current
cluster namespace.

## Job states

```text
created → submitted → queued → running → succeeded
                                      ├→ failed
                                      ├→ cancelled
                                      ├→ timed_out
                                      └→ lost
```

Use `record.state.is_terminal` instead of maintaining your own set of final
states.

## Refresh explicitly

Long-lived services can decide when scheduler I/O occurs:

```python
queue.refresh_jobs()
active = queue.list_jobs()
```

One reconciliation pass:

1. loads active records for this cluster name;
2. batch-queries the scheduler;
3. stores changed state and timestamps;
4. emits lifecycle events;
5. schedules retries when policy allows.

## Read logs

Default stdout and stderr live below the job's resolved working directory:

```text
<cwd>/.molq/jobs/<job-id>/
```

The exact paths are recorded in metadata:

```python
record = queue.get_job(job.job_id)
print(record.metadata["molq.stdout_path"])
print(record.metadata["molq.stderr_path"])
```

For a local destination, the CLI can read those files directly:

```bash
molq logs JOB_ID local --cluster laptop
molq logs JOB_ID local --cluster laptop --stream stderr --tail 50
molq logs JOB_ID local --cluster laptop --follow
```

For SSH destinations, copy logs through the transport:

```python
paths = queue.fetch_logs(
    job.job_id,
    dest_dir="./downloaded-logs",
)
print(paths["stdout"])
```

Copy the complete job directory when the workload writes additional outputs:

```python
directory = queue.fetch_artifacts(
    job.job_id,
    dest_dir="./downloaded-run",
    exclude=("*.tmp",),
)
```

## Inspect history

```python
record = queue.get_job(job_id)
timeline = queue.get_transitions(job_id)
attempts = queue.get_retry_family(job_id)
parents = queue.get_dependencies(job_id)
children = queue.get_dependents(job_id)
```

The CLI combines those views:

```bash
molq history slurm --cluster dardel --all
molq inspect JOB_ID slurm --cluster dardel
```

## Run reconciliation in the background

For a long-running process:

```python
queue.run_daemon(
    interval=5.0,
    run_cleanup=True,
)
```

Or run one pass from the CLI:

```bash
molq daemon slurm --cluster dardel --once
```

The daemon performs reconciliation and optional retention cleanup. It is not
required when application code already calls `wait()`, `refresh_jobs()`, or
CLI commands regularly.

## Open the dashboard

```bash
molq monitor
molq monitor --all --limit 500 --refresh 1.5
```

The dashboard reads persisted jobs across cluster namespaces. Closing it does
not cancel anything.

## Subscribe to lifecycle events

Handlers run synchronously in registration order. Exceptions are logged and
isolated from the monitoring loop.

```python
from molq import EventType


def report(payload):
    print(payload.job_id, payload.record.state.value)


queue.on_event(EventType.JOB_COMPLETED, report)
queue.on_event(EventType.JOB_FAILED, report)

# Later
queue.off_event(EventType.JOB_COMPLETED, report)
```

## Clean up retained data

Preview cleanup first:

```python
plan = queue.cleanup_jobs(dry_run=True)
print(plan["job_dirs"])
print(plan["records"])
```

The default retention keeps job directories for 30 days, terminal records for
90 days, and failed-job directories. Override it with `RetentionPolicy` or a
[configuration profile](configuration.md).
