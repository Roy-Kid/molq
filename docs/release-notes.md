# Release notes

Curated highlights per release. Complete history is git tags / GitHub Releases
(no hand-written `CHANGELOG.md`).

## 0.7.0

Released 2026-08-07.

Supersedes the unreleased 0.6.1, whose fixes are all included here.

### Fixed

- **CLI job commands no longer invent an SSH connection.** `molq submit local
  echo hello` and every other job command failed in 0.6.0 with
  `remote mkdir failed`, because destination resolution asked `ssh -G` whether
  the cluster name was an SSH host — and `ssh -G` answers "yes" for any
  string, including molq's own `cli_local` namespace. SSH is now used only
  when `--cluster` names a `Host` block actually declared in `~/.ssh/config`.
- **`molq logs` works for remote jobs.** Log paths live on the cluster's
  filesystem, but the command checked and read them locally, so every remote
  job reported a missing log. It now resolves and reads through the cluster
  transport, and `--tail` is evaluated on the far side.
- **Reading files from a macOS host works.** `SshTransport.read_bytes()` ran
  `base64 -- <file>`, which BSD base64 rejects outright — it accepts only
  `-i` or stdin.
- `SshTransport.stat()` and `getsize()` no longer shell out to `python3` on
  the remote. HPC login nodes routinely keep Python behind `module load`, so
  it is absent from a non-interactive session's PATH.
- LSF terminal resolution matches the phrases `bhist -l` actually emits
  instead of searching its prose for "done" or "exit" — a job named
  `rundone.sh` used to be reported as succeeded. Owner-initiated kills now map
  to `CANCELLED` rather than `FAILED`.
- `molq workspace` rejects an unknown `--cluster` alias with the list of known
  ones instead of failing later inside `rsync`.
- A `Submitor` given a `store=` no longer closes it on `close()`. Sharing one
  `JobStore` across per-cluster Submitors is a documented pattern, and the
  first `close()` used to disconnect all of them.
- Schema versions are compared numerically. As strings `"10"` sorts before
  `"8"`, so a future database read as unmigratable garbage rather than
  "upgrade molq".
- Generated job scripts quote the materialized script path, so a working
  directory containing spaces or `$` no longer corrupts the script.
- `JobHandle.wait()` honors its timeout and backoff while a retry attempt is
  being re-targeted.

### Added

- **Profiles can describe a remote destination.** A profile now takes `host`,
  so `Submitor.from_profile("gpu")` and `molq submit slurm --profile gpu`
  reach the cluster the profile names. Previously a profile could only ever
  run locally.
- `ssh_alias_names()` lists the `Host` aliases declared in your SSH config
  without the per-alias `ssh -G` round trip.
- `SshTransportOptions` gained `control_master`, `control_persist`, and
  `connect_timeout`.

### Performance

- **SSH connection multiplexing is on by default.** molq performs many small
  remote operations per job, each previously paying a full TCP and
  authentication handshake. The socket lives at `~/.ssh/molq-<hash>`. Opt out
  with `SshTransportOptions(control_master=False)`.
- **`import molq` went from ~293 ms to ~75 ms.** mollog (and through it
  logfire), rich, and termios now load on first use rather than at import, so
  `molq status` no longer pays for a dashboard it will not draw. As a side
  effect, importing molq no longer requires the Unix-only `termios`.
- Local-scheduler submission waits for the job pid in one remote command
  instead of polling from the client — over SSH that removed up to ~250
  connections per submission.
- A reconcile cycle costs a flat number of queries instead of two or three per
  active job, and stamps `last_polled` for the whole cycle in one transaction.
- Retention cutoffs are applied in SQL. Cleanup used to load every terminal
  record for the cluster and filter in Python.
- `JobStore.list_records()` accepts `limit`, and `watch_jobs()` returns only
  the jobs it waited on rather than the cluster's entire history.

### Changed

- Per-scheduler dependency syntax moved from `Submitor` onto the `Scheduler`
  protocol (`format_dependency` / `format_dependencies`). Adding a backend no
  longer means editing the lifecycle layer.
- `molq.scheduler`, `molq.store`, and `molq.cli` are packages rather than
  single modules, with one file per backend and per command group. Public
  imports are unchanged.

## 0.6.0

Released 2026-07-22.

### Plugin host

- Added the `MolqPlugin` protocol, read-only `PluginContext`, and
  `PluginManager`.
- Official plugins ship with molq; third-party plugins load from the
  `molq.plugins` entry-point group.
- `Submitor` accepts `plugins=` and `plugin_configs=`.
- The official Nerve plugin sends fail-open status rollups to the local Nerve
  menu-bar app.
- Added `molq plugins list`; `molq daemon` defaults to Nerve when no plugin
  table is configured.

### Documentation

- Adopted the packaged MolCrafts Zensical theme.
- Reorganized the manual around runnable tutorials, task guides, and generated
  API reference pages.

## 0.5.0

Released 2026-05-11.

### Configuration and persistence

- The canonical database moved to
  `~/.molcrafts/molq/config/jobs.db`.
- The canonical profile file moved to
  `~/.molcrafts/molq/config/config.toml`.
- Both paths honor `MOLCRAFTS_HOME`.
- `JobStore` now requires an explicit path; `Submitor` still opens the
  canonical store automatically.

Existing files under `~/.molq/` are not migrated automatically.

### SSH and remote workspaces

- SSH config discovery exposes named OpenSSH hosts as cluster candidates.
- `Cluster.from_ssh_alias()` resolves effective connection settings with
  `ssh -G`.
- `Workspace` and `Project` provide transport-backed upload, download,
  listing, and remote submission helpers.

## 0.4.0

Released 2026-05-02.

- `"local"` became the single no-batch scheduler.
- Every scheduler now routes commands through the selected transport.
- A local scheduler can therefore run on this host or an SSH workstation.
- The former `"shell"` scheduler name was removed.

## 0.3.0

Released 2026-04-18.

- Added `molq watch --all`.
- Added profile loading through molcfg.
- Refined job artifact defaults and CLI inspection.

## 0.1.0

Released 2025-06-24.

Initial beta with local, SLURM, PBS, and LSF backends; typed requests; SQLite
persistence; reconciliation; monitoring; and CLI support.
