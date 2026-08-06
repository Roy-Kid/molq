# Release notes

Curated highlights per release. Complete history is git tags / GitHub Releases
(no hand-written `CHANGELOG.md`).

## 0.6.1

Released 2026-08-06.

### Fixed

- **CLI job commands no longer invent an SSH connection.** `molq submit local
  echo hello` and every other job command failed in 0.6.0 with
  `remote mkdir failed`, because destination resolution asked `ssh -G` whether
  the cluster name was an SSH host — and `ssh -G` answers "yes" for any
  string, including molq's own `cli_local` namespace. SSH is now used only
  when `--cluster` names a `Host` block actually declared in `~/.ssh/config`.
- `molq workspace` commands reject an unknown `--cluster` alias with the list
  of known aliases instead of failing later inside `rsync`.
- A `Submitor` given a `store=` no longer closes it on `close()`. Sharing one
  `JobStore` across per-cluster Submitors is a documented pattern, and the
  first `close()` used to disconnect all of them.
- Schema versions are compared numerically. As strings, `"10"` sorts before
  `"8"`, so a future database would have been reported as unreadable rather
  than as "upgrade molq".
- Generated job scripts quote the materialized script path, so a working
  directory containing spaces or `$` no longer corrupts the script.
- `JobHandle.wait()` honors its timeout and backoff while a retry attempt is
  being re-targeted.

### Performance

- **SSH connection multiplexing is on by default.** molq performs many small
  remote operations per job; each previously paid a full TCP and
  authentication handshake. A shared master connection now covers them. Opt
  out with `SshTransportOptions(control_master=False)`.
- Local-scheduler submission waits for the job pid in one remote command
  instead of polling from the client — over SSH that removed up to ~250
  connections per submission.
- A reconcile cycle stamps `last_polled` for every active job in a single
  transaction rather than one commit per job.
- SSH connections use a 15-second `ConnectTimeout`, so an unreachable host
  fails promptly instead of hanging.

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
