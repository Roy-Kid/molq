# Mental model

molq separates **where a job runs** from **how that job is tracked**. Most API
decisions become straightforward once those two responsibilities stay
separate.

## The request path

```text
your code
   │
   ▼
Submitor ── submits, persists, reconciles, waits
   │ target
   ▼
Cluster ─── Scheduler: local / SLURM / PBS / LSF
   │
   └──────── Transport: this machine / SSH
```

The scheduler speaks the batch system's language. The transport decides where
those scheduler commands and file operations execute.

## Cluster: the destination

A `Cluster` combines three pieces of destination configuration:

1. A stable name such as `"laptop"` or `"dardel"`.
2. A scheduler kind: `"local"`, `"slurm"`, `"pbs"`, or `"lsf"`.
3. A transport: local subprocesses by default, SSH when `host=` is provided.

```python
import molq as mq

laptop = mq.Cluster("laptop", "local")
dardel = mq.Cluster("dardel", "slurm", host="dardel")
```

A `Cluster` does not own job history. It is cheap to construct and is also the
entry point for destination-side operations:

```python
dardel.get_queue()
dardel.get_workspace("scratch", path="/cfs/klemming/scratch/a/alice")
```

## Submitor: the lifecycle owner

`Submitor` is the queue-facing API. It owns:

- submission and cancellation;
- the SQLite job store;
- scheduler reconciliation;
- blocking waits and retries;
- lifecycle events, plugins, and retention.

Every `Submitor` is bound to one `Cluster`:

```python
with mq.Submitor(target=dardel) as queue:
    job = queue.submit_job(argv=["python", "train.py"])
    record = job.wait()
```

Create one `Submitor` per destination. They use the same default database but
filter records by cluster name.

```python
local_queue = mq.Submitor(target=laptop)
hpc_queue = mq.Submitor(target=dardel)

local_queue.list_jobs()  # only "laptop"
hpc_queue.list_jobs()    # only "dardel"
```

Passing an explicit `store=` to several Submitors is safe: each one closes
only a store it opened itself, so closing one does not disconnect its
siblings.

## Scheduler and transport are independent

These are different questions:

| Question | Object | Examples |
|---|---|---|
| Which queue system accepts the job? | Scheduler | local, SLURM, PBS, LSF |
| Where do its commands execute? | Transport | this host, SSH host |

That produces useful combinations:

| Scheduler | Transport | Meaning |
|---|---|---|
| local | local | Run a normal process on this machine |
| local | SSH | Run a normal process on a remote workstation |
| SLURM | local | Run `sbatch` on the current login node |
| SLURM | SSH | Run `sbatch` on a remote cluster |

See [Clusters and schedulers](schedulers.md) for construction examples.

## A job has three public views

### JobHandle

Returned by `submit_job()`. It is a convenience object for the active
lifecycle:

```python
job.status()
job.refresh()
job.wait(timeout=3600)
job.cancel()
```

### JobRecord

An immutable snapshot stored by molq. It includes the molq job ID, scheduler
ID, state, timestamps, exit information, command metadata, and artifact paths.
Use `queue.get_job()` and `queue.list_jobs()` to read records.

### QueueEntry

One row from the scheduler's live queue:

```python
entries = cluster.get_queue()
```

`QueueEntry` and `JobRecord` answer different questions:

| View | Source | What it represents |
|---|---|---|
| `JobRecord` | molq SQLite database | Jobs molq knows about, including history |
| `QueueEntry` | `squeue`, `qstat`, or `bjobs` | What the scheduler reports right now |

## Lifecycle

A normal job moves through:

```text
created → submitted → queued → running → succeeded
                                      └→ failed
```

Cancellation, timeout, or disappearing scheduler state can instead produce
`cancelled`, `timed_out`, or `lost`. All five final states are terminal.

molq stores transitions; it does not infer the current state merely from an
in-memory object. Reconciliation updates the durable record from scheduler
responses.

## Rules of thumb

- Put destination details on `Cluster`.
- Put resource defaults, retry, and retention on `Submitor`.
- Put one job's requirements in `JobResources`, `JobScheduling`, and
  `JobExecution`.
- Use `JobRecord` for application logic and audit history.
- Use `cluster.get_queue()` only when you need the scheduler's live view.
- Keep cluster names stable whenever you want CLI and API sessions to find the
  same records.
