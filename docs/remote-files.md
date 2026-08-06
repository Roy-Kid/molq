# Remote files

molq does not implicitly upload files named in a command. `Workspace` and
`Project` make staging explicit and route every file operation through the
cluster's transport.

## Before you start

Verify both SSH and rsync:

```bash
ssh dardel hostname
rsync --version
```

Create the destination with an SSH alias:

```python
import molq as mq

cluster = mq.Cluster("dardel", "slurm", host="dardel")
```

## Workspace and Project

A `Workspace` is a known base directory on the destination. A `Project` is a
named directory below it.

```python
workspace = cluster.get_workspace(
    "scratch",
    path="/cfs/klemming/scratch/a/alice",
)
project = workspace.get_project("protein-screen")

print(project.path)
# /cfs/klemming/scratch/a/alice/protein-screen
```

Constructing these objects performs no I/O.

## Create and upload

```python
project.ensure()
project.upload("./src", recursive=True)
project.upload("./config.toml")
```

Paths are copied into the remote project directory. Use `exists()` and
`list_files()` to inspect it:

```python
if project.exists():
    for name in project.list_files():
        print(name)
```

## Submit in the project directory

`Project.submit_job()` sets `JobExecution.cwd` to the project path:

```python
with mq.Submitor(target=cluster) as queue:
    job = project.submit_job(
        queue,
        argv=["python", "src/train.py", "--config", "config.toml"],
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

The `Submitor` must target the same `Cluster` instance as the project.

## Read and download results

Read a small remote text file without staging the whole directory:

```python
print(project.read_text("summary.txt"))
print(project.tail(".molq/jobs/JOB_ID/stdout.log", lines=40))
```

Download one result:

```python
project.download("results.csv", "./results.csv")
```

Download a directory recursively:

```python
project.download("outputs", "./outputs", recursive=True)
```

To mirror the entire workspace or project, use `mirror()`:

```python
project.mirror("./local-copy", exclude=("*.tmp", ".cache"))
```

## Sync from the CLI

Push a local directory:

```bash
molq workspace sync ./src \
  --cluster dardel \
  --path /cfs/klemming/scratch/a/alice/protein-screen/src
```

Pull results:

```bash
molq workspace sync ./results \
  --pull \
  --cluster dardel \
  --path /cfs/klemming/scratch/a/alice/protein-screen/results
```

List the remote directory:

```bash
molq workspace list \
  --cluster dardel \
  --path /cfs/klemming/scratch/a/alice/protein-screen
```

`--cluster` is resolved through `~/.ssh/config`.

## Keep staging predictable

- Upload code and inputs before submission.
- Use an absolute remote workspace path.
- Treat `argv` paths as relative to `JobExecution.cwd`.
- Download outputs explicitly; a completed job does not copy them back.
- Keep large reusable datasets outside per-job directories.
- Use `queue.fetch_logs()` for remote log files and
  `queue.fetch_artifacts()` for the generated job bundle.
