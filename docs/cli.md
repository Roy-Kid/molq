# CLI Reference

`molq` is a Typer + Rich CLI for submitting, inspecting, monitoring, and cleaning
up jobs on local and HPC schedulers.

```bash
molq --help          # command groups
molq submit --help   # options for one command
molq -h              # short alias
```

## Command groups

| Group | Commands |
|---|---|
| **Jobs** | `submit` · `list` · `status` · `logs` · `watch` · `cancel` · `inspect` |
| **History** | `history` · `allocations` · `cleanup` |
| **Live** | `monitor` · `daemon` |
| **Setup** | `clusters` · `workspace` · `plugins` |

Most job commands take:

- `SCHEDULER` — `local` | `slurm` | `pbs` | `lsf`
- `--cluster` — namespace (default from profile or `cli_<scheduler>`)
- `--profile` — named profile from `config.toml`
- `--config` — path to config file

---

## `molq submit`

```bash
molq submit SCHEDULER [COMMAND]... [OPTIONS]
```

**Resources:** `--cpus` · `--mem` · `--time` · `--gpus` · `--gpu-type`
**Scheduling:** `--partition` · `--account`
**Execution:** `--name` · `--workdir`
**Retry:** `--retries` · `--retry-on-exit-code`
**Dependencies** (molq job IDs, not scheduler IDs):
`--after` · `--after-started` · `--after-success` · `--after-failure` (repeatable)
**Other:** `--cluster` · `--profile` · `--config` · `--block`

```bash
molq submit local echo hello
molq submit slurm --cpus 8 --mem 32G --time 4h python train.py
molq submit slurm --after-success $JOB1 python eval.py
```

---

## Inspect & control

| Command | Purpose |
|---|---|
| `list [SCHEDULER]` | Active jobs (`--all` includes terminal) |
| `status JOB_ID` | Current state (refreshes scheduler first) |
| `logs JOB_ID` | stdout/stderr (`--stream` · `--tail` · `-f/--follow`) |
| `watch JOB_ID` | Block until done (`--all` · `--timeout`) |
| `cancel JOB_ID` | Cancel on scheduler + store |
| `inspect JOB_ID` | Metadata, deps, transition timeline |
| `history` | Table with attempt / times / exit |
| `allocations` | Remembered partition/account/qos |
| `cleanup` | Retention purge (`-n/--dry-run`) |

---

## Live

| Command | Purpose |
|---|---|
| `monitor` | Full-screen dashboard (all clusters; `q` to quit) |
| `daemon` | Reconcile loop; loads plugins (default: nerve) |

### Daemon & Nerve

With no `[plugins]` section, `daemon` enables the official **nerve** plugin
(push job status to `http://127.0.0.1:17890`, fail-open).

```toml
[plugins.nerve]
enabled = true          # or false to disable
expand_threshold = 8
show_members = "attention"
```

---

## Setup

```bash
molq clusters list
molq clusters show NAME
molq workspace sync ./src --cluster HOST -p /remote/path
molq workspace sync --pull ./out --cluster HOST -p /remote/path
molq workspace list --cluster HOST -p /remote/path
molq plugins list
```

---

## Config location

Default config path is resolved via molcfg (`~/.molcrafts/molq/…`, or
`$MOLCRAFTS_HOME/molq/…`). Override with `--config`.
