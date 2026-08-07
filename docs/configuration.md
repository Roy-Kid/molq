# Configuration

Configuration profiles collect reusable scheduler options, job defaults,
retry rules, and retention policy.

## Default locations

molq uses the MolCrafts configuration root:

| File | Default path |
|---|---|
| Profiles | `~/.molcrafts/molq/config/config.toml` |
| Job database | `~/.molcrafts/molq/config/jobs.db` |

Set `MOLCRAFTS_HOME` to relocate both:

```bash
export MOLCRAFTS_HOME=/srv/molcrafts
```

The project path is then derived below that root. CLI commands accept
`--config` when only the profile file needs an override.

!!! note "Version 0.5 path change"

    Version 0.5 moved both files from `~/.molq/`. It does not migrate old files
    automatically.

## Minimal profile

```toml
[profiles.gpu]
scheduler = "slurm"
cluster_name = "dardel"
```

Load it in Python:

```python
import molq as mq

cluster = mq.Cluster.from_profile("gpu")
queue = mq.Submitor.from_profile("gpu", target=cluster)
```

Or from the CLI:

```bash
molq submit slurm --profile gpu python train.py
```

## Full profile

```toml
[profiles.gpu]
scheduler = "slurm"
cluster_name = "dardel"
jobs_dir = "/scratch/alice/.molq/jobs"

[profiles.gpu.scheduler_options]
sbatch_path = "sbatch"
squeue_path = "squeue"
scancel_path = "scancel"
sacct_path = "sacct"
extra_sbatch_flags = ["--clusters=gpu"]

[profiles.gpu.defaults.resources]
cpu_count = 8
memory = "34359738368"
gpu_count = 1
time_limit = 14400

[profiles.gpu.defaults.scheduling]
partition = "gpu"
account = "project123"
qos = "normal"

[profiles.gpu.defaults.execution]
cwd = "/scratch/alice/project"
job_name = "molq-job"

[profiles.gpu.retry]
max_attempts = 3
retry_on_states = ["failed", "timed_out"]
retry_on_exit_codes = [1, 137]

[profiles.gpu.retry.backoff]
mode = "exponential"
initial_seconds = 10
maximum_seconds = 120
factor = 2

[profiles.gpu.retention]
keep_job_dirs_for_days = 14
keep_terminal_records_for_days = 90
keep_failed_job_dirs = true

[plugins.nerve]
enabled = true
expand_threshold = 8
debounce_seconds = 0.3
ingest_url = "http://127.0.0.1:17890"
show_members = "attention"
```

### Units in TOML

Profile values use the serialized storage representation:

| Field | Unit | Example |
|---|---|---|
| `memory` | bytes, encoded as a string | `"34359738368"` for 32 GiB |
| `time_limit` | seconds | `14400` for four hours |

The Python API and CLI accept friendlier constructors and strings:
`Memory.gb(32)`, `Duration.hours(4)`, `--mem 32G`, and `--time 4h`.

## Profile fields

| Field | Required | Meaning |
|---|---|---|
| `scheduler` | yes | `local`, `slurm`, `pbs`, or `lsf` |
| `cluster_name` | yes | persisted record namespace |
| `host` | no | SSH destination; omit to run on this machine |
| `jobs_dir` | no | base directory for scripts and captured logs |
| `scheduler_options` | no | backend command paths and extra submit flags |
| `defaults.resources` | no | resource defaults |
| `defaults.scheduling` | no | queue policy defaults |
| `defaults.execution` | no | process environment defaults |
| `retry` | no | default retry policy |
| `retention` | no | artifact and terminal-record retention |

Plugin tables are top-level rather than nested below a profile. They apply to
CLI sessions opened from the same config file. `molq daemon` defaults to the
official Nerve plugin only when no plugin table exists; see
[Plugins and Nerve](plugins.md).

## Precedence

For job fields:

```text
submit_job(...) value
        overrides
profile / Submitor default
        overrides
dataclass default
```

Merging happens field by field. A submission can override `cpu_count` while
retaining profile memory and time limits.

## Scheduler options

Each scheduler accepts only its matching option table:

| Scheduler | Option class | Command overrides |
|---|---|---|
| local | `LocalSchedulerOptions` | none |
| SLURM | `SlurmSchedulerOptions` | `sbatch`, `squeue`, `scancel`, `sacct` |
| PBS | `PBSSchedulerOptions` | `qsub`, `qstat`, `qdel`, `tracejob` |
| LSF | `LSFSchedulerOptions` | `bsub`, `bjobs`, `bkill`, `bhist` |

Using options for the wrong scheduler raises an error.

## Remote profiles

Set `host` to make the profile describe a remote destination. It accepts
anything `ssh` accepts, including a `~/.ssh/config` alias:

```toml
[profiles.gpu]
scheduler = "slurm"
cluster_name = "dardel"
host = "dardel"

[profiles.gpu.defaults.resources]
cpu_count = 8
memory = "32G"
```

Both halves of the profile then load together — destination and lifecycle:

```python
import molq as mq

with mq.Submitor.from_profile("gpu") as queue:
    job = queue.submit_job(argv=["python", "train.py"])
```

Omit `host` and the profile runs on the current machine.

To apply a profile's resource defaults to a destination you build yourself,
pass an explicit target — it wins over the profile's `host`:

```python
cluster = mq.Cluster("dardel", "slurm", host="dardel-backup")

with mq.Submitor.from_profile("gpu", target=cluster) as queue:
    job = queue.submit_job(argv=["python", "train.py"])
```

The CLI picks the host up automatically:

```bash
molq submit slurm --profile gpu python train.py
```

## Use an isolated database

Applications and tests can construct a store explicitly:

```python
from molq import Cluster, Submitor
from molq.store import JobStore

store = JobStore("./state/jobs.db")
queue = Submitor(
    target=Cluster("test", "local"),
    store=store,
)
```

`JobStore` requires a path. `Submitor(store=None)` is the convenience path that
opens the canonical MolCrafts database automatically.
