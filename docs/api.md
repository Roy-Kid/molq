# Python API

The public API is intentionally small. Most applications import from the
package root:

```python
import molq as mq
```

## Start with these

| Need | API |
|---|---|
| Describe a destination | `mq.Cluster` |
| Submit and track jobs | `mq.Submitor` |
| Follow one submission | `mq.JobHandle` |
| Describe a request | `mq.JobResources`, `mq.JobScheduling`, `mq.JobExecution` |
| Read durable state | `mq.JobRecord`, `mq.JobState` |

The reference is split by responsibility so individual pages stay navigable:

- [Core API](reference/core.md) — `Cluster`, `Submitor`, and `JobHandle`.
- [Job types](reference/types.md) — commands, resources, records, retry,
  retention, and queue entries.
- [Supporting APIs](reference/utilities.md) — workspaces, configuration, SSH
  discovery, callbacks, plugins, and errors.

## Stability boundary

Symbols exported by `molq.__all__` are the supported package-level surface.
Scheduler and transport protocols are useful for advanced integrations but are
implementation-facing; ordinary users should construct them through
`Cluster`.

## Typical flow

```python
import molq as mq

cluster = mq.Cluster("laptop", "local")

with mq.Submitor(target=cluster) as queue:
    job = queue.submit_job(
        argv=["python", "analyse.py"],
        execution=mq.JobExecution(job_name="analysis"),
    )
    record = job.wait()

if record.state is mq.JobState.SUCCEEDED:
    print("done")
```

For task-oriented explanations, start with [Submit jobs](jobs.md) or
[Monitor jobs](monitoring.md).
