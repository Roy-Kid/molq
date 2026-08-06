# Command line

The `molq` CLI submits jobs, reads the same SQLite records as the Python API,
and offers terminal-oriented inspection and monitoring.

```bash
molq --help
molq submit --help
```

## The two identifiers you must keep consistent

Most commands accept both:

- a **scheduler** positional argument: `local`, `slurm`, `pbs`, or `lsf`;
- `--cluster`, the namespace used to store and retrieve records.

```bash
molq submit local --cluster laptop echo hello
molq list local --cluster laptop --all
```

If `--cluster` names a `Host` entry declared in `~/.ssh/config`, molq uses it
as an SSH destination when no profile is active. Any other name — including
the default `cli_<scheduler>` namespace — is a local destination and a pure
record namespace.

!!! note "Why the alias must be declared"

    molq checks the `Host` blocks in your SSH config rather than asking
    `ssh -G`, because `ssh -G` prints a resolved configuration for *any*
    string you hand it and so can never distinguish a real destination from a
    typo.

!!! warning "Use the same namespace later"

    A job submitted with `--cluster dardel` will not appear under the default
    `cli_slurm` namespace.

## Submit

```bash
molq submit SCHEDULER [OPTIONS] COMMAND...
```

Local:

```bash
molq submit local --cluster laptop python analyse.py
```

SLURM:

```bash
molq submit slurm \
  --cluster dardel \
  --cpus 8 \
  --mem 32G \
  --time 4h \
  --gpus 1 \
  --partition gpu \
  --account project123 \
  python train.py
```

Wait before returning:

```bash
molq submit local --cluster laptop --block python analyse.py
```

Retry at most twice after the first attempt:

```bash
molq submit slurm \
  --cluster dardel \
  --retries 3 \
  --retry-on-exit-code 137 \
  python train.py
```

Dependencies accept molq job IDs:

```bash
molq submit slurm \
  --cluster dardel \
  --after-success PARENT_JOB_ID \
  python evaluate.py
```

Repeat `--after-success`, `--after-failure`, `--after-started`, or `--after`
to supply several upstream jobs.

## Inspect and control

| Command | Purpose |
|---|---|
| `list` | Active records; add `--all` for terminal jobs |
| `status` | Refresh and print one job |
| `inspect` | Metadata, attempts, dependencies, and transition timeline |
| `watch` | Wait for one job; add `--all` for every active job |
| `cancel` | Cancel the latest active attempt |
| `logs` | Read local stdout or stderr |
| `history` | Show persisted history |
| `cleanup` | Apply retention policy |

Examples:

```bash
molq list slurm --cluster dardel --all
molq status JOB_ID slurm --cluster dardel
molq inspect JOB_ID slurm --cluster dardel
molq watch JOB_ID slurm --cluster dardel --timeout 3600
molq cancel JOB_ID slurm --cluster dardel
```

## Read logs

For local jobs:

```bash
molq logs JOB_ID local --cluster laptop
molq logs JOB_ID local --cluster laptop --stream stderr --tail 100
molq logs JOB_ID local --cluster laptop --follow
```

The current CLI reads recorded paths from the local filesystem. For an SSH
destination, use `Submitor.fetch_logs()` to transfer them first:

```python
paths = queue.fetch_logs("JOB_ID", dest_dir="./logs")
```

## Watch and monitor

Wait for every active local job in a namespace:

```bash
molq watch --all --cluster laptop
```

Open the cross-namespace dashboard:

```bash
molq monitor
molq monitor --all --limit 500 --refresh 1.5
```

Run background reconciliation:

```bash
molq daemon slurm --cluster dardel
molq daemon slurm --cluster dardel --once
```

When the config has no `[plugins]` table, `daemon` enables the official Nerve
status plugin. See [Plugins and Nerve](plugins.md).

## Discover destinations

List profile destinations and concrete SSH aliases:

```bash
molq clusters list
molq clusters show dardel
```

SSH aliases are resolved with `ssh -G`, so the display reflects effective
OpenSSH settings.

## Sync remote files

```bash
molq workspace sync ./src \
  --cluster dardel \
  --path /remote/project/src

molq workspace sync ./results \
  --pull \
  --cluster dardel \
  --path /remote/project/results

molq workspace list \
  --cluster dardel \
  --path /remote/project
```

See [Remote files](remote-files.md) for the corresponding Python API.

## Use a profile

```bash
molq submit slurm \
  --profile gpu \
  --config ./config.toml \
  python train.py
```

Profiles provide scheduler options, defaults, retry, retention, and job
directory settings. Top-level plugin tables apply to CLI sessions separately.
The default config file is:

```text
~/.molcrafts/molq/config/config.toml
```

Profiles currently do not encode SSH transport settings. For remote CLI
submission without a profile, use an SSH alias with `--cluster`. In Python,
combine a profile with an explicit remote target:

```python
cluster = mq.Cluster("dardel", "slurm", host="dardel")
queue = mq.Submitor.from_profile("gpu", target=cluster)
```

See [Configuration](configuration.md) for the complete TOML shape and
precedence rules.

## List plugins

```bash
molq plugins list
```

The command shows official and third-party plugins and whether the current
config enables them.

## Command map

```text
Jobs        submit  list  status  inspect  watch  cancel  logs
History     history  cleanup
Live        monitor  daemon
Setup       clusters list|show  workspace sync|list  plugins list
```

Use `molq COMMAND --help` as the authoritative option list for the installed
version.
